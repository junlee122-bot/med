"""CPU multi-objective decision layer (Phase 8, Section 13).

Thin extension over the existing Pareto service (services/pareto_optimization.py):
adds an explicit decision-policy label per candidate and a backend-comparison view
(CPU front vs recorded-GPU front). Does NOT fork Pareto logic. Never declares a
single universal "best molecule" unless all objectives + constraints justify it.
"""
from __future__ import annotations

from typing import Any

from app.models.schemas import SourceType, utcnow
from app.services import pareto_optimization as pareto


def _decision_policy(candidate: dict[str, Any]) -> str:
    """Map a Pareto candidate to a decision-policy role. Conservative + honest."""
    ov = candidate.get("objective_values", {}) or {}
    role = candidate.get("recommended_role", "")
    rank = candidate.get("pareto_rank", 99)
    safety = ov.get("safety_score")
    applic = ov.get("applicability_confidence")
    novelty = ov.get("novelty")
    missing = candidate.get("missing_objectives", [])

    if safety is not None and safety < 0.4:
        return "DO_NOT_ADVANCE"
    if len(missing) >= 4:
        return "DATA_ACQUISITION_CANDIDATE"
    if rank == 1:
        if safety is not None and safety >= 0.75 and (applic or 0) >= 0.6:
            return "SAFETY_PRIORITY_CANDIDATE"
        if (novelty or 0) >= 0.7:
            return "NOVELTY_EXPLORATION_CANDIDATE"
        return "BALANCED_CANDIDATE"
    if "ACTIVITY" in str(role).upper():
        return "ACTIVITY_PRIORITY_CANDIDATE"
    return "DO_NOT_ADVANCE" if rank > 2 else "BALANCED_CANDIDATE"


def analyze(molecules: list[dict[str, Any]], backend: str = "CPU_SELECTION") -> dict[str, Any]:
    """Run Pareto + attach decision policy. `backend` is a provenance label only."""
    base = pareto.compute(molecules)
    candidates = base.get("all_candidates", [])
    for c in candidates:
        c["decision_policy"] = _decision_policy(c)
    policy_counts: dict[str, int] = {}
    for c in candidates:
        policy_counts[c["decision_policy"]] = policy_counts.get(c["decision_policy"], 0) + 1
    # Only name a single best when the base analysis found one strict dominator
    # and the sole rank-1 candidate has complete objective data.
    rank1 = [c for c in candidates if c.get("pareto_rank") == 1]
    single_best = None
    if not base.get("no_single_best", True) and len(rank1) == 1 and not rank1[0].get("missing_objectives"):
        single_best = rank1[0].get("molecule_id")
    return {
        **base, "backend": backend, "backend_source_type": SourceType.COMPUTE_FALLBACK_OUTPUT.value
        if backend.startswith("CPU") else SourceType.RECORDED_GPU_OUTPUT.value,
        "pareto_front_size": len(base.get("front", [])),
        "decision_policy_counts": policy_counts, "single_best_molecule": single_best,
        "single_best_note": ("A single best was named only because one rank-1 candidate dominates with "
                             "complete objective data." if single_best else
                             "No single 'best molecule' — tradeoffs across objectives are presented instead."),
        "analyzed_at": utcnow(),
    }


def compare_backends(molecules: list[dict[str, Any]],
                     recorded_gpu_molecules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Compare a CPU-only Pareto front with a recorded-GPU front (if provided)."""
    cpu = analyze(molecules, backend="CPU_SELECTION")
    gpu = analyze(recorded_gpu_molecules, backend="RECORDED_GPU") if recorded_gpu_molecules else None
    return {
        "cpu_front": {"pareto_front_size": cpu.get("pareto_front_size"),
                      "decision_policy_counts": cpu["decision_policy_counts"],
                      "source_type": cpu["backend_source_type"]},
        "recorded_gpu_front": ({"pareto_front_size": gpu.get("pareto_front_size"),
                                "decision_policy_counts": gpu["decision_policy_counts"],
                                "source_type": gpu["backend_source_type"]} if gpu else None),
        "note": ("Recorded-GPU front shown only when recorded artifacts are supplied; "
                 "CPU front is always available and clearly labeled."),
        "objective_completeness_matters": True, "compared_at": utcnow(),
    }
