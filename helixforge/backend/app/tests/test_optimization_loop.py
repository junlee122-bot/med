"""Phase 7 — deterministic in-silico optimization loop.

Covers seed selection, safe local generation (selection + heuristic analogs),
the safety gate, provenance honesty for REINVENT4, and the assembled
OptimizationLoopRun report. All fixtures use fixed, valid SMILES so the loop is
fully deterministic.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.schemas import utcnow
from app.services import optimization_loop
from app.services.optimization_loop import (
    local_generator,
    reinvent_bridge,
    safety_gate,
)
from app.storage import db

_ALLOWED_MODES = {
    "SELECTION_LOOP",
    "LOCAL_HEURISTIC_GENERATION",
    "REINVENT4_EXTERNAL",
    "CONFIGURED_BUT_NOT_RUN",
}

# (smiles, descriptors) for a few real, valid molecules.
_MOLS = [
    ("CCO", {"mol_weight": 46.07, "logp": 0.0, "hbd": 1, "hba": 1, "tpsa": 20.23, "qed": 0.407}, 6.1),
    ("CC(=O)Oc1ccccc1C(=O)O", {"mol_weight": 180.16, "logp": 1.31, "hbd": 1, "hba": 3, "tpsa": 63.6, "qed": 0.55}, 7.4),
    ("c1ccccc1O", {"mol_weight": 94.11, "logp": 1.39, "hbd": 1, "hba": 1, "tpsa": 20.23, "qed": 0.515}, 5.2),
    ("CCN(CC)CC", {"mol_weight": 101.19, "logp": 1.32, "hbd": 0, "hba": 1, "tpsa": 3.24, "qed": 0.45}, 6.8),
]


def _seed_run(extra_mols: list[dict] | None = None) -> str:
    """Insert a workflow run + valid molecule candidates. Return the run id."""
    project_id = f"proj-{uuid.uuid4().hex[:8]}"
    run_id = f"run-{uuid.uuid4().hex[:8]}"
    db.insert(
        "workflow_runs",
        {
            "id": run_id,
            "project_id": project_id,
            "kind": "optimization_loop_test",
            "target_query": "EGFR",
            "created_at": utcnow(),
        },
    )
    for smiles, descriptors, pchembl in _MOLS:
        db.insert(
            "molecule_candidates",
            {
                "id": f"mol-{uuid.uuid4().hex[:8]}",
                "project_id": project_id,
                "canonical_smiles": smiles,
                "smiles": smiles,
                "molecule_chembl_id": f"CHEMBL_{uuid.uuid4().hex[:6]}",
                "label": f"seed-{smiles}",
                "descriptors": descriptors,
                "pchembl_value": pchembl,
                "valid": True,
                "safety_status": "PASS",
                "composite_score": round(50 + 8 * pchembl, 1),
                "source_type": "REAL_TOOL_OUTPUT",
                "created_at": utcnow(),
            },
        )
    for m in extra_mols or []:
        m.setdefault("project_id", project_id)
        m.setdefault("created_at", utcnow())
        db.insert("molecule_candidates", m)
    return run_id


@pytest.mark.unit
@pytest.mark.local_tool
def test_optimization_loop_selection_mode_runs():
    run_id = _seed_run()
    result = optimization_loop.run(run_id=run_id)
    assert isinstance(result, dict)
    assert result["generations"] >= 1
    assert result["mode"] in _ALLOWED_MODES
    assert isinstance(result["best_score_by_generation"], list)
    # Full record contract is present.
    for key in (
        "id", "run_id", "target_id", "mode", "generations",
        "candidate_count_by_generation", "valid_count_by_generation",
        "rejected_count_by_generation", "safety_block_count",
        "best_score_by_generation", "pareto_front_by_generation",
        "improvement_summary", "limitations", "generation_records",
        "source_type", "created_at",
    ):
        assert key in result


@pytest.mark.unit
@pytest.mark.local_tool
def test_optimization_loop_no_synthesis_output():
    run_id = _seed_run()
    banned = [
        "reflux", "reagent", "reaction condition", "dissolve", "heat to",
        "step 1", "yield %", "synthesis route",
    ]
    for mode in (None, "LOCAL_HEURISTIC_GENERATION"):
        text = str(optimization_loop.run(run_id=run_id, mode=mode)).lower()
        for phrase in banned:
            assert phrase not in text, f"forbidden phrase '{phrase}' leaked (mode={mode})"


@pytest.mark.unit
@pytest.mark.local_tool
def test_generated_candidates_labeled_heuristic():
    analogs = local_generator.local_heuristic_analogs(["CCO", "c1ccccc1O"])
    if analogs:
        for a in analogs:
            assert a["source_type"] == "LOCAL_HEURISTIC_GENERATED"
            assert a["valid"] is True
            assert "smiles" in a and a["smiles"]
            assert "parent" in a
    else:
        # Returning [] (mode unavailable) is explicitly acceptable.
        pytest.skip("local heuristic generation returned [] — acceptable")


@pytest.mark.unit
@pytest.mark.local_tool
def test_invalid_generated_candidates_rejected():
    # 1) An invalid SMILES is rejected directly by the safety gate.
    assert safety_gate.screen("not_a_valid_smiles_XYZ")["ok"] is False

    # 2) Injecting an invalid candidate into the run makes the loop count a rejection.
    invalid = {
        "id": f"mol-bad-{uuid.uuid4().hex[:8]}",
        "canonical_smiles": "not_a_valid_smiles_XYZ",
        "smiles": "not_a_valid_smiles_XYZ",
        "label": "injected-invalid",
        "descriptors": {},
        "valid": True,  # mislabeled valid on purpose; the gate must still reject it
        "safety_status": "PASS",
        "composite_score": 999.0,  # forces selection as a seed
        "source_type": "REAL_TOOL_OUTPUT",
    }
    run_id = _seed_run(extra_mols=[invalid])
    result = optimization_loop.run(run_id=run_id)
    assert sum(result["rejected_count_by_generation"]) >= 1


@pytest.mark.unit
@pytest.mark.local_tool
def test_safety_blocked_not_recommended():
    # Neutral descriptor text of a real molecule passes.
    assert safety_gate.screen("CC(=O)Oc1ccccc1C(=O)O")["ok"] is True
    # Injecting blocked (actionable) content makes the lint gate reject it.
    blocked = safety_gate.screen("CCO", context="reagent list and reaction conditions")
    assert blocked["ok"] is False
    assert blocked["reason"] == "safety_block"


@pytest.mark.unit
@pytest.mark.local_tool
def test_optimization_report_distinguishes_selection_vs_generation():
    run_id = _seed_run()
    selection = optimization_loop.run(run_id=run_id, mode="SELECTION_LOOP")
    assert selection["mode"] == "SELECTION_LOOP"

    generation = optimization_loop.run(run_id=run_id, mode="LOCAL_HEURISTIC_GENERATION")
    assert "mode" in generation
    assert generation["mode"] in _ALLOWED_MODES
    # With valid seeds the heuristic strategy should engage.
    assert generation["mode"] in ("LOCAL_HEURISTIC_GENERATION", "SELECTION_LOOP")


@pytest.mark.unit
def test_reinvent_not_faked_when_uninstalled():
    status = reinvent_bridge.status()
    assert status["mode"] == "CONFIGURED_BUT_NOT_RUN"
    assert status.get("executed") is False
    assert not local_generator.reinvent_available()
