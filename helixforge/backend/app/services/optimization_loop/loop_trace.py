"""Per-generation trace records for the optimization loop.

A generation record is a compact, auditable summary of what happened in one
generation: how many candidates were proposed, how many were valid, how many
were rejected (invalid structure or safety block), the best candidate, the
median score, and a diversity proxy. All text is neutral — never procedural.
"""
from __future__ import annotations

import statistics
from typing import Any


def _diversity_score(scored: list[dict]) -> float:
    """Fraction of distinct SMILES among the scored candidates (0-1)."""
    if not scored:
        return 0.0
    smiles = [c.get("smiles") for c in scored if c.get("smiles")]
    if not smiles:
        return 0.0
    return round(len(set(smiles)) / len(smiles), 3)


def generation_record(
    index: int,
    source: str,
    candidates: list[dict],
    scored: list[dict],
    rejected_invalid: int,
    rejected_safety: int,
) -> dict[str, Any]:
    """Build the trace record for a single generation.

    Returns a dict with: generation_index, source, candidate_count, valid_count,
    rejected_count, safety_block_count, best_candidate, median_score,
    diversity_score, notes.
    """
    scores = [float(c.get("score", 0.0)) for c in scored]
    best_candidate: dict[str, Any] | None = None
    if scored:
        best = max(
            scored, key=lambda c: (float(c.get("score", 0.0)), str(c.get("id") or ""))
        )
        best_candidate = {
            "id": best.get("id"),
            "label": best.get("label"),
            "smiles": best.get("smiles"),
            "score": best.get("score"),
            "recommendation": best.get("recommendation"),
            "applicability_status": best.get("applicability_status"),
        }
    median_score = round(statistics.median(scores), 3) if scores else 0.0

    notes = (
        f"Generation {index} via {source}: {len(candidates)} proposed, "
        f"{len(scored)} valid and scored, {rejected_invalid} rejected as invalid, "
        f"{rejected_safety} rejected by the safety gate. In-silico prioritization "
        "for computational review only."
    )

    return {
        "generation_index": index,
        "source": source,
        "candidate_count": len(candidates),
        "valid_count": len(scored),
        "rejected_count": rejected_invalid + rejected_safety,
        "safety_block_count": rejected_safety,
        "best_candidate": best_candidate,
        "median_score": median_score,
        "diversity_score": _diversity_score(scored),
        "notes": notes,
    }
