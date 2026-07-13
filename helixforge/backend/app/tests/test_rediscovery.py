"""Tests for the retrospective chemotype-recovery package.

Covers: comparator library integrity (all SMILES parse in RDKit), exact /
Tanimoto / scaffold recovery, the modality-mismatch short-circuit, and the
safety wording of the Markdown report (no de-novo-discovery or efficacy
overclaim). RDKit-dependent tests are marked ``local_tool`` and skip cleanly
when RDKit is absent.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.schemas import utcnow
from app.services import rediscovery
from app.services.rediscovery import (
    chemotype_recovery,
    comparator_library,
    rediscovery_report,
)
from app.storage import db

# Fixed key contract for a RediscoveryResult.
_RESULT_KEYS = {
    "id", "run_id", "scenario_id", "target", "comparator_count",
    "candidate_count", "valid_candidate_count", "exact_match_count",
    "best_similarity", "hit_at_1", "hit_at_5", "hit_at_10",
    "scaffold_recovery_rate", "enrichment_factor", "sample_size_warning",
    "modality_mismatch", "conclusion", "limitations", "source_type_summary",
    "created_at",
}


@pytest.mark.local_tool
def test_comparator_library_loads_egfr():
    if not comparator_library.RDKIT:
        pytest.skip("RDKit not available")
    from rdkit import Chem

    block = comparator_library.get_comparators("egfr_nsclc")
    comps = block["comparators"]
    assert len(comps) >= 3
    for comp in comps:
        assert Chem.MolFromSmiles(comp["smiles"]) is not None, comp["name"]


@pytest.mark.local_tool
def test_comparator_smiles_all_valid():
    if not comparator_library.RDKIT:
        pytest.skip("RDKit not available")
    from rdkit import Chem

    checked = 0
    for scenario in comparator_library.list_scenarios():
        if scenario["modality"] != "small_molecule":
            continue
        for comp in comparator_library.all_comparator_smiles(scenario["id"]):
            assert Chem.MolFromSmiles(comp["smiles"]) is not None, \
                f"{scenario['id']}/{comp['name']}"
            checked += 1
    assert checked >= 3
    # Sanity: the library self-validation agrees.
    assert all(comparator_library.validate_library().values())


@pytest.mark.local_tool
def test_rediscovery_exact_match_if_same_smiles():
    if not chemotype_recovery.RDKIT:
        pytest.skip("RDKit not available")
    comps = comparator_library.all_comparator_smiles("egfr_nsclc")
    candidate = comps[0]["smiles"]
    hits = chemotype_recovery.exact_matches([candidate], comps)
    assert len(hits) >= 1
    assert hits[0]["comparator_name"] == comps[0]["name"]


@pytest.mark.local_tool
def test_rediscovery_tanimoto_similarity():
    if not chemotype_recovery.RDKIT:
        pytest.skip("RDKit not available")
    comps = comparator_library.all_comparator_smiles("egfr_nsclc")
    candidate = comps[1]["smiles"]
    sim = chemotype_recovery.similarity_recovery(
        [candidate], comps, scores=[1.0], k_list=(1, 5, 10)
    )
    assert sim["available"] is True
    assert sim["best_similarity"] == pytest.approx(1.0, abs=1e-6)
    assert sim["hit_at_k"][1] is True


@pytest.mark.local_tool
def test_rediscovery_scaffold_recovery():
    if not chemotype_recovery.RDKIT:
        pytest.skip("RDKit not available")
    comps = comparator_library.all_comparator_smiles("egfr_nsclc")
    # A candidate identical to a comparator necessarily shares its scaffold.
    candidate = comps[0]["smiles"]
    scaf = chemotype_recovery.scaffold_recovery([candidate], comps)
    assert scaf["available"] is True
    assert scaf["scaffold_recovery_rate"] > 0


@pytest.mark.unit
def test_rediscovery_modality_mismatch_pcsk9_or_tnf():
    result = rediscovery.run(scenario_id="pcsk9_hchol")
    assert result["conclusion"] == "NOT_APPLICABLE_MODALITY_MISMATCH"
    assert result["modality_mismatch"] is True
    assert set(result.keys()) == _RESULT_KEYS
    # TNF behaves the same way.
    tnf = rediscovery.run(scenario_id="tnf_ra")
    assert tnf["conclusion"] == "NOT_APPLICABLE_MODALITY_MISMATCH"
    assert tnf["modality_mismatch"] is True


@pytest.mark.unit
def test_rediscovery_no_discovery_overclaim():
    result = {
        "scenario_id": "egfr_nsclc", "target": "EGFR", "conclusion": "PARTIAL_CHEMOTYPE_RECOVERY",
        "modality_mismatch": False, "comparator_count": 5, "candidate_count": 4,
        "valid_candidate_count": 4, "exact_match_count": 0, "best_similarity": 0.62,
        "hit_at_1": False, "hit_at_5": True, "hit_at_10": True,
        "scaffold_recovery_rate": 0.2, "enrichment_factor": None, "sample_size_warning": True,
        "limitations": ["structural proxy only"],
    }
    md = rediscovery_report.build_report(result).lower()
    assert "does not prove" in md
    assert "does not prove de novo discovery" in md
    for forbidden in ("discovered a drug", "proven efficacy", "cure"):
        assert forbidden not in md, f"forbidden phrase present: {forbidden!r}"


@pytest.mark.unit
def test_rediscovery_report_contains_limitations():
    md = rediscovery_report.build_report({"scenario_id": "egfr_nsclc"}).lower()
    assert "limitation" in md
    assert "sanity check against known drug classes" in md


@pytest.mark.local_tool
def test_rediscovery_run_smoke_exact_match():
    if not chemotype_recovery.RDKIT:
        pytest.skip("RDKit not available")
    egfr = comparator_library.all_comparator_smiles("egfr_nsclc")
    known_smiles = egfr[0]["smiles"]

    pid = f"proj-redisc-{uuid.uuid4().hex[:8]}"
    rid = f"run-redisc-{uuid.uuid4().hex[:8]}"
    db.insert("workflow_runs", {
        "id": rid, "project_id": pid, "created_at": utcnow(),
        "kind": "real_pipeline", "target_query": "EGFR",
        "condition": "non-small cell lung cancer",
    })
    db.insert("molecule_candidates", {
        "id": f"mol-{uuid.uuid4().hex[:8]}", "project_id": pid,
        "workflow_run_id": rid, "created_at": utcnow(),
        "canonical_smiles": known_smiles, "smiles": known_smiles,
        "molecule_chembl_id": "CHEMBL-TEST-1", "label": "known-egfr",
        "composite_score": 0.9, "valid": True, "source_type": "HEURISTIC_ANALYSIS",
    })
    db.insert("molecule_candidates", {
        "id": f"mol-{uuid.uuid4().hex[:8]}", "project_id": pid,
        "workflow_run_id": rid, "created_at": utcnow(),
        "canonical_smiles": "CCO", "smiles": "CCO",
        "molecule_chembl_id": "CHEMBL-TEST-2", "label": "ethanol",
        "composite_score": 0.1, "valid": True, "source_type": "HEURISTIC_ANALYSIS",
    })

    result = rediscovery.run(run_id=rid)
    assert set(result.keys()) == _RESULT_KEYS
    assert result["run_id"] == rid
    assert result["scenario_id"] == "egfr_nsclc"
    assert result["modality_mismatch"] is False
    assert result["exact_match_count"] >= 1
    assert result["conclusion"] == "STRONG_CHEMOTYPE_RECOVERY"
    # Persisted into rediscovery_runs.
    assert db.get("rediscovery_runs", result["id"]) is not None
