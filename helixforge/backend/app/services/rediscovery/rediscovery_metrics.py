"""Enrichment metric for retrospective chemotype recovery.

Enrichment factor (EF) measures how much more concentrated the "known-like"
candidates are at the top of the score-ranked list than they would be by chance.
It is a retrospective quality signal only — it does not establish discovery,
efficacy, or safety.
"""
from __future__ import annotations

from typing import Any


def enrichment_factor(
    candidate_scores: list[float],
    is_known_like: list[bool],
    top_frac: float = 0.1,
) -> dict[str, Any]:
    """Enrichment factor at the top ``top_frac`` of score-ranked candidates.

    EF = (fraction of known-like among the top ``top_frac``) / (fraction of
    known-like overall). EF > 1 means the scoring concentrates known-like
    chemotypes near the top; EF == 1 is chance-level.

    For a small sample (< 10 candidates) EF is statistically meaningless, so we
    return ``{"sample_size_warning": True, "enrichment_factor": None}``.
    """
    n = min(len(candidate_scores), len(is_known_like))
    if n < 10:
        return {
            "sample_size_warning": True,
            "enrichment_factor": None,
            "top_frac": top_frac,
            "sample_size": n,
            "warnings": ["sample size < 10; enrichment factor not computed"],
        }

    scores = list(candidate_scores[:n])
    known = list(is_known_like[:n])
    total_known = sum(1 for k in known if k)

    if total_known == 0:
        # No known-like actives → EF undefined (no positive baseline).
        return {
            "sample_size_warning": False,
            "enrichment_factor": None,
            "top_frac": top_frac,
            "sample_size": n,
            "top_n": max(1, round(top_frac * n)),
            "hits_in_top": 0,
            "total_known": 0,
            "warnings": ["no known-like candidates; enrichment factor undefined"],
        }

    order = sorted(range(n), key=lambda i: (-(scores[i] if scores[i] is not None else 0.0), i))
    top_n = max(1, round(top_frac * n))
    top_idx = order[:top_n]

    hits_in_top = sum(1 for i in top_idx if known[i])
    frac_top = hits_in_top / top_n
    frac_overall = total_known / n
    ef = round(frac_top / frac_overall, 4) if frac_overall > 0 else None

    return {
        "sample_size_warning": False,
        "enrichment_factor": ef,
        "top_frac": top_frac,
        "sample_size": n,
        "top_n": top_n,
        "hits_in_top": hits_in_top,
        "total_known": total_known,
        "warnings": [],
    }
