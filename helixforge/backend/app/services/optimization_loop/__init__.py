"""Deterministic in-silico optimization loop (self-contained package).

This package runs a small, safe, and fully deterministic candidate-optimization
loop over a workflow run's molecule candidates. It never produces synthesis
routes, reagents, reaction conditions, dosing, or any procedural chemistry —
every candidate is an in-silico suggestion queued for computational review only.

Generation strategies (see :mod:`local_generator`):

* ``SELECTION_LOOP`` — optimization by selection: re-rank the existing candidate
  pool under deterministically perturbed weights. No new structures.
* ``LOCAL_HEURISTIC_GENERATION`` — conservative RDKit single-atom substituent
  analogs, each validated and safety-screened. Returns nothing rather than junk
  when it cannot generate robustly.
* ``REINVENT4_EXTERNAL`` — never executed here; when REINVENT4 is not configured
  the loop honestly reports ``CONFIGURED_BUT_NOT_RUN`` and falls back to a local
  strategy (it never fabricates generative output).

The public entry point is :func:`run`.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import SourceType, utcnow
from app.storage import db

from . import (
    loop_trace,
    local_generator,
    reinvent_bridge,
    safety_gate,
    scoring_loop,
    seed_selector,
)

__all__ = [
    "run",
    "seed_selector",
    "local_generator",
    "safety_gate",
    "scoring_loop",
    "loop_trace",
    "reinvent_bridge",
]

_ALLOWED_MODES = {
    "SELECTION_LOOP",
    "LOCAL_HEURISTIC_GENERATION",
    "REINVENT4_EXTERNAL",
    "CONFIGURED_BUT_NOT_RUN",
}

_SAFETY_NOTE = (
    "In-silico suggestions only for computational review; no procedural "
    "chemistry, no laboratory instructions, no dosing, and no wet-lab guidance "
    "are produced."
)
_MAX_GENERATIONS = 3


def _new_id() -> str:
    return f"optloop-{uuid.uuid4().hex[:12]}"


def _smiles_of(rec: dict) -> str:
    return rec.get("canonical_smiles") or rec.get("smiles") or ""


def _persist(payload: dict) -> None:
    try:
        db.insert("optimization_loop_runs", payload)
    except Exception:  # pragma: no cover - persistence is best-effort
        pass


def _front_summary(front: list[dict]) -> list[dict]:
    return [
        {
            "id": c.get("id"),
            "label": c.get("label"),
            "smiles": c.get("smiles"),
            "score": c.get("score"),
            "applicability_status": c.get("applicability_status"),
            "recommendation": c.get("recommendation"),
        }
        for c in front
    ]


def _process_generation(
    index: int, source: str, candidates: list[dict], reference_smiles: list[str]
) -> dict[str, Any]:
    """Validate, safety-screen, score, and pareto-rank one generation."""
    scored: list[dict] = []
    rejected_invalid = 0
    rejected_safety = 0

    for cand in candidates:
        smiles = _smiles_of(cand)
        gate = safety_gate.screen(smiles)
        if not gate["ok"]:
            if gate.get("reason") == "safety_block":
                rejected_safety += 1
            else:
                rejected_invalid += 1
            continue
        scored.append(scoring_loop.score_candidate(cand, reference_smiles))

    front = scoring_loop.pareto_front(scored)
    record = loop_trace.generation_record(
        index, source, candidates, scored, rejected_invalid, rejected_safety
    )
    best_score = max((float(s.get("score", 0.0)) for s in scored), default=0.0)
    return {
        "scored": scored,
        "front": front,
        "record": record,
        "rejected_invalid": rejected_invalid,
        "rejected_safety": rejected_safety,
        "candidate_count": len(candidates),
        "valid_count": len(scored),
        "best_score": best_score,
    }


def _improvement_summary(best_scores: list[float]) -> str:
    if not best_scores:
        return "No generations produced scored candidates."
    if len(best_scores) == 1:
        return (
            f"Single generation evaluated; best in-silico priority score "
            f"{best_scores[0]}. No cross-generation comparison available."
        )
    first, last = best_scores[0], best_scores[-1]
    delta = round(last - first, 3)
    if delta > 0:
        trend = f"improved by {delta}"
    elif delta < 0:
        trend = f"declined by {abs(delta)}"
    else:
        trend = "unchanged"
    return (
        f"Best in-silico priority score {trend} from generation 0 ({first}) to "
        f"generation {len(best_scores) - 1} ({last}). Prioritization only; not a "
        "claim of efficacy."
    )


def _empty_payload(
    run_id: str | None, target_id: str | None, limitations: list[str]
) -> dict[str, Any]:
    payload = {
        "id": _new_id(),
        "run_id": run_id,
        "target_id": target_id,
        "mode": "CONFIGURED_BUT_NOT_RUN",
        "generations": 0,
        "candidate_count_by_generation": [],
        "valid_count_by_generation": [],
        "rejected_count_by_generation": [],
        "safety_block_count": 0,
        "best_score_by_generation": [],
        "pareto_front_by_generation": [],
        "improvement_summary": "No candidate molecules available for this run; nothing to optimize.",
        "limitations": limitations + ["Run had no molecule candidates."],
        "generation_records": [],
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
        "created_at": utcnow(),
    }
    _persist(payload)
    return payload


def run(
    run_id: str | None = None,
    target_id: str | None = None,
    mode: str | None = None,
    generations: int = 2,
) -> dict[str, Any]:
    """Run the deterministic in-silico optimization loop for a workflow run.

    Parameters
    ----------
    run_id:
        Workflow run id. Defaults to the most recent run.
    target_id:
        Optional target identifier, echoed into the report.
    mode:
        Requested generation strategy (``"SELECTION_LOOP"`` or
        ``"LOCAL_HEURISTIC_GENERATION"``). Defaults to ``SELECTION_LOOP``.
        REINVENT4 is never executed here.
    generations:
        Number of generations to attempt (clamped to 1..3).

    Returns
    -------
    dict
        An ``OptimizationLoopRun`` record (also persisted).
    """
    generations = max(1, min(int(generations or 1), _MAX_GENERATIONS))

    runs = db.list_records("workflow_runs", limit=200)
    run_rec = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    run_rec = run_rec or {}
    rid = run_rec.get("id")
    pid = run_rec.get("project_id")
    mols = (
        db.list_records("molecule_candidates", project_id=pid, limit=500) if pid else []
    )

    limitations: list[str] = [_SAFETY_NOTE]
    reinvent = reinvent_bridge.status()
    if reinvent.get("mode") == "CONFIGURED_BUT_NOT_RUN":
        limitations.append(
            "REINVENT4 not installed; the loop used a local deterministic strategy "
            "and did not fabricate generative output."
        )

    if not mols:
        return _empty_payload(rid, target_id, limitations)

    reference_smiles = [s for s in (_smiles_of(m) for m in mols) if s]

    # --- Generation 0: seed selection ---
    seeds = seed_selector.select_seeds(mols, k=8)
    seed_smiles = [s["smiles"] for s in seeds if s.get("smiles")]
    gen0 = _process_generation(0, "SEED_SELECTION", seeds, reference_smiles)

    generation_records = [gen0["record"]]
    candidate_count_by_generation = [gen0["candidate_count"]]
    valid_count_by_generation = [gen0["valid_count"]]
    rejected_count_by_generation = [gen0["rejected_invalid"] + gen0["rejected_safety"]]
    best_score_by_generation = [gen0["best_score"]]
    pareto_front_by_generation = [_front_summary(gen0["front"])]
    safety_block_count = gen0["rejected_safety"]

    # --- Decide loop mode for subsequent generations ---
    requested = (mode or "").upper()
    loop_mode = "SELECTION_LOOP"
    pre_analogs: list[dict] = []
    if requested == "LOCAL_HEURISTIC_GENERATION":
        pre_analogs = local_generator.local_heuristic_analogs(seed_smiles)
        if pre_analogs:
            loop_mode = "LOCAL_HEURISTIC_GENERATION"
        else:
            limitations.append(
                "Local heuristic generation was unavailable for these seeds; "
                "used SELECTION_LOOP instead."
            )

    # --- Subsequent generations ---
    prev_smiles = seed_smiles
    for g in range(1, generations):
        if loop_mode == "LOCAL_HEURISTIC_GENERATION":
            children = (
                pre_analogs
                if g == 1 and pre_analogs
                else local_generator.local_heuristic_analogs(prev_smiles)
            )
            gen_source = "LOCAL_HEURISTIC_GENERATION"
        else:
            children = local_generator.resample_and_reweight(mols, seed=g)
            gen_source = "SELECTION_LOOP"

        if not children:
            break

        gen = _process_generation(g, gen_source, children, reference_smiles)
        generation_records.append(gen["record"])
        candidate_count_by_generation.append(gen["candidate_count"])
        valid_count_by_generation.append(gen["valid_count"])
        rejected_count_by_generation.append(gen["rejected_invalid"] + gen["rejected_safety"])
        best_score_by_generation.append(gen["best_score"])
        pareto_front_by_generation.append(_front_summary(gen["front"]))
        safety_block_count += gen["rejected_safety"]

        next_smiles = [c["smiles"] for c in gen["scored"] if c.get("smiles")]
        if next_smiles:
            prev_smiles = next_smiles

    payload = {
        "id": _new_id(),
        "run_id": rid,
        "target_id": target_id,
        "mode": loop_mode if loop_mode in _ALLOWED_MODES else "SELECTION_LOOP",
        "generations": len(generation_records),
        "candidate_count_by_generation": candidate_count_by_generation,
        "valid_count_by_generation": valid_count_by_generation,
        "rejected_count_by_generation": rejected_count_by_generation,
        "safety_block_count": safety_block_count,
        "best_score_by_generation": best_score_by_generation,
        "pareto_front_by_generation": pareto_front_by_generation,
        "improvement_summary": _improvement_summary(best_score_by_generation),
        "limitations": limitations,
        "generation_records": generation_records,
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
        "created_at": utcnow(),
    }
    _persist(payload)
    return payload
