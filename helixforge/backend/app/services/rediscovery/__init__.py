"""Retrospective chemotype-recovery package.

This package performs a **retrospective recovery** / **sanity check against
known drug classes**: given a workflow run's candidate molecules, it measures
how strongly they re-find already-known small-molecule chemotypes for the
target. It NEVER claims de novo discovery, efficacy, or clinical use, and it
gracefully declines (modality mismatch) for biologic-heavy targets rather than
forcing a molecule comparison.

Top-level entry point: :func:`run`.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.models.schemas import SourceType, utcnow
from app.storage import db

from . import chemotype_recovery, comparator_library, rediscovery_metrics

# Keyword -> scenario id mapping used to derive a scenario from a run's
# free-text target query. Order matters: earlier, more specific keys win.
_TARGET_KEYWORDS: list[tuple[str, str]] = [
    ("egfr", "egfr_nsclc"),
    ("erbb1", "egfr_nsclc"),
    ("braf", "braf_melanoma"),
    ("alk", "alk_nsclc"),
    ("jak2", "jak2_mpn"),
    ("jak", "jak2_mpn"),
    ("her2", "her2_breast"),
    ("erbb2", "her2_breast"),
    ("pcsk9", "pcsk9_hchol"),
    ("tnf", "tnf_ra"),
]

_DEFAULT_SCENARIO = "egfr_nsclc"

_SIM_THRESHOLD = 0.7


def _derive_scenario(target_query: Optional[str]) -> str:
    """Map a run's target query to the closest scenario id (default egfr_nsclc)."""
    q = (target_query or "").lower()
    for keyword, scenario_id in _TARGET_KEYWORDS:
        if keyword in q:
            return scenario_id
    return _DEFAULT_SCENARIO


def _candidate_smiles_and_scores(
    mols: list[dict[str, Any]]
) -> tuple[list[str], list[float], list[dict[str, Any]]]:
    """Extract (smiles, composite_score, raw_record) triples from candidates."""
    smiles: list[str] = []
    scores: list[float] = []
    kept: list[dict[str, Any]] = []
    for m in mols:
        smi = m.get("canonical_smiles") or m.get("smiles")
        if not smi:
            continue
        smiles.append(smi)
        raw = m.get("composite_score")
        try:
            scores.append(float(raw) if raw is not None else 0.0)
        except (TypeError, ValueError):
            scores.append(0.0)
        kept.append(m)
    return smiles, scores, kept


def _source_type_summary(mols: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize provenance: analysis label, comparator label, candidate counts."""
    candidate_types: dict[str, int] = {}
    for m in mols:
        st = str(m.get("source_type") or "UNKNOWN")
        candidate_types[st] = candidate_types.get(st, 0) + 1
    return {
        "analysis": SourceType.HEURISTIC_ANALYSIS.value,
        "comparators": "public reference structure",
        "candidates": candidate_types,
    }


def _base_limitations() -> list[str]:
    return [
        "Retrospective recovery / sanity check against known drug classes only; "
        "it does not prove de novo discovery and does not imply clinical efficacy.",
        "Comparators are a small, curated set of public reference structures; "
        "coverage is incomplete and modality-dependent.",
        "Tanimoto similarity and Bemis-Murcko scaffold overlap are structural "
        "proxies, not measures of biological activity, potency, or safety.",
        "Results are rule-based structural analytics (HEURISTIC_ANALYSIS) and "
        "require review by a qualified human expert.",
        "No synthesis routes, reaction conditions, or dosing are provided or implied.",
    ]


def _conclusion(
    valid_count: int, exact_count: int, best_sim: float
) -> str:
    if valid_count == 0:
        return "INSUFFICIENT_DATA"
    if best_sim >= 0.8 or exact_count > 0:
        return "STRONG_CHEMOTYPE_RECOVERY"
    if best_sim >= 0.5:
        return "PARTIAL_CHEMOTYPE_RECOVERY"
    return "EVIDENCE_RETRIEVAL_ONLY"


def _persist(result: dict[str, Any], project_id: Optional[str]) -> None:
    """Best-effort persistence into the ``rediscovery_runs`` table."""
    try:
        payload = dict(result)
        if project_id:
            payload["project_id"] = project_id
        db.insert("rediscovery_runs", payload)
    except Exception:
        pass


def run(scenario_id: str | None = None, run_id: str | None = None) -> dict[str, Any]:
    """Run retrospective chemotype recovery for a workflow run.

    Resolves the run (given ``run_id`` else the latest) and its candidate
    molecules, chooses a scenario (explicit arg, else derived from the run's
    target query, else the EGFR default), and:

    * for biologic-heavy / empty-comparator scenarios returns a
      ``NOT_APPLICABLE_MODALITY_MISMATCH`` result without forcing any molecule
      comparison, otherwise
    * computes exact / similarity / scaffold / enrichment recovery and returns a
      ``RediscoveryResult`` dict with a fixed key set.

    The result is persisted (best-effort) to ``rediscovery_runs``.
    """
    runs = db.list_records("workflow_runs", limit=200)
    run_rec = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    if run_id and not run_rec:
        raise ValueError("workflow run not found")
    run_rec = run_rec or {}
    resolved_run_id = run_rec.get("id")
    pid = run_rec.get("project_id")

    mols: list[dict[str, Any]] = []
    if pid and resolved_run_id:
        mols = db.list_records(
            "molecule_candidates", project_id=pid,
            workflow_run_id=resolved_run_id, limit=500,
        )

    chosen_scenario = scenario_id or _derive_scenario(run_rec.get("target_query"))
    block = comparator_library.get_comparators(chosen_scenario)
    target = block.get("target", "")
    modality = block.get("modality", "")
    comparators = list(block.get("comparators", []))

    smiles, scores, kept = _candidate_smiles_and_scores(mols)
    candidate_count = len(smiles)
    source_summary = _source_type_summary(kept)
    created_at = utcnow()
    result_id = f"redisc-{uuid.uuid4().hex[:8]}"

    # --- Modality mismatch: do NOT force a molecule comparison ----------
    if modality == "biologic_or_mixed" or not comparators:
        limitations = _base_limitations() + [
            f"Scenario '{chosen_scenario}' targets {target or 'a target'} that is "
            "not primarily a small-molecule modality; small-molecule chemotype "
            "recovery is not applicable and was not attempted.",
        ]
        result = {
            "id": result_id,
            "run_id": resolved_run_id,
            "scenario_id": chosen_scenario,
            "target": target,
            "comparator_count": 0,
            "candidate_count": candidate_count,
            "valid_candidate_count": 0,
            "exact_match_count": 0,
            "best_similarity": None,
            "hit_at_1": None,
            "hit_at_5": None,
            "hit_at_10": None,
            "scaffold_recovery_rate": None,
            "enrichment_factor": None,
            "sample_size_warning": None,
            "modality_mismatch": True,
            "conclusion": "NOT_APPLICABLE_MODALITY_MISMATCH",
            "limitations": limitations,
            "source_type_summary": source_summary,
            "created_at": created_at,
        }
        _persist(result, pid)
        return result

    # --- Small-molecule recovery ----------------------------------------
    valid_smiles = [s for s in smiles if chemotype_recovery._canonical(s) is not None] \
        if chemotype_recovery.RDKIT else list(smiles)
    valid_candidate_count = len(valid_smiles)

    exact = chemotype_recovery.exact_matches(smiles, comparators)
    exact_match_count = len(exact)

    sim = chemotype_recovery.similarity_recovery(
        smiles, comparators, scores=scores, k_list=(1, 5, 10), sim_threshold=_SIM_THRESHOLD
    )
    best_similarity = sim.get("best_similarity", 0.0)
    hit_at_k = sim.get("hit_at_k", {})
    per_candidate = sim.get("per_candidate", [])

    scaf = chemotype_recovery.scaffold_recovery(smiles, comparators)
    scaffold_recovery_rate = scaf.get("scaffold_recovery_rate", 0.0)

    # known-like flag per (valid) candidate for enrichment.
    is_known_like = [pc.get("similarity", 0.0) >= _SIM_THRESHOLD for pc in per_candidate]
    ef = rediscovery_metrics.enrichment_factor(scores, is_known_like, top_frac=0.1)

    conclusion = _conclusion(valid_candidate_count, exact_match_count, best_similarity or 0.0)

    result = {
        "id": result_id,
        "run_id": resolved_run_id,
        "scenario_id": chosen_scenario,
        "target": target,
        "comparator_count": len(comparators),
        "candidate_count": candidate_count,
        "valid_candidate_count": valid_candidate_count,
        "exact_match_count": exact_match_count,
        "best_similarity": best_similarity,
        "hit_at_1": bool(hit_at_k.get(1, False)),
        "hit_at_5": bool(hit_at_k.get(5, False)),
        "hit_at_10": bool(hit_at_k.get(10, False)),
        "scaffold_recovery_rate": scaffold_recovery_rate,
        "enrichment_factor": ef.get("enrichment_factor"),
        "sample_size_warning": bool(ef.get("sample_size_warning", False)),
        "modality_mismatch": False,
        "conclusion": conclusion,
        "limitations": _base_limitations(),
        "source_type_summary": source_summary,
        "created_at": created_at,
    }
    _persist(result, pid)
    return result
