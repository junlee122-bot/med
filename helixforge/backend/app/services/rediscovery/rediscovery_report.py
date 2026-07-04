"""Human-readable Markdown report for a retrospective chemotype-recovery run.

The wording is deliberately conservative: this is a RETROSPECTIVE RECOVERY /
sanity check against known drug classes. It does not prove de novo discovery and
does not imply clinical efficacy. A qualified human remains responsible for any
interpretation or decision.
"""
from __future__ import annotations

from typing import Any


def _fmt(value: Any) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def build_report(result: dict[str, Any]) -> str:
    """Render a ``RediscoveryResult`` dict as a careful Markdown report."""
    r = result or {}
    lines: list[str] = []

    lines.append("# Retrospective Chemotype Recovery Report")
    lines.append("")
    lines.append(
        "_This is a **retrospective recovery** analysis: a **sanity check against "
        "known drug classes**. It asks whether the pipeline's candidate molecules "
        "resemble already-approved / known chemotypes for the stated target. It "
        "**does not prove de novo discovery** and **does not imply clinical "
        "efficacy** or safety._"
    )
    lines.append("")

    # --- Summary ---------------------------------------------------------
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Scenario: `{_fmt(r.get('scenario_id'))}`")
    lines.append(f"- Target: **{_fmt(r.get('target'))}**")
    lines.append(f"- Conclusion: **{_fmt(r.get('conclusion'))}**")
    lines.append(f"- Modality mismatch: {_fmt(r.get('modality_mismatch'))}")
    lines.append(f"- Comparators (public reference structures): {_fmt(r.get('comparator_count'))}")
    lines.append(
        f"- Candidates: {_fmt(r.get('candidate_count'))} "
        f"(valid: {_fmt(r.get('valid_candidate_count'))})"
    )
    lines.append("")

    # --- Modality-mismatch short-circuit --------------------------------
    if r.get("modality_mismatch"):
        lines.append("## Not applicable — modality mismatch")
        lines.append("")
        lines.append(
            "This target is not primarily addressed by small molecules, so a "
            "small-molecule chemotype recovery is **not applicable**. No "
            "molecule-level comparison was forced. Small-molecule candidates (if "
            "any) were not benchmarked against a biologic drug class."
        )
        lines.append("")
    else:
        # --- Recovery metrics -------------------------------------------
        lines.append("## Recovery metrics")
        lines.append("")
        lines.append(f"- Exact chemotype matches: {_fmt(r.get('exact_match_count'))}")
        lines.append(f"- Best Tanimoto similarity to any comparator: {_fmt(r.get('best_similarity'))}")
        lines.append(f"- hit@1 / hit@5 / hit@10: "
                     f"{_fmt(r.get('hit_at_1'))} / {_fmt(r.get('hit_at_5'))} / {_fmt(r.get('hit_at_10'))}")
        lines.append(f"- Bemis-Murcko scaffold recovery rate: {_fmt(r.get('scaffold_recovery_rate'))}")
        lines.append(f"- Enrichment factor (top fraction): {_fmt(r.get('enrichment_factor'))}")
        if r.get("sample_size_warning"):
            lines.append(
                "- Note: sample size is small; the enrichment factor is not "
                "statistically reliable."
            )
        lines.append("")

    # --- Interpretation --------------------------------------------------
    lines.append("## What this does and does not mean")
    lines.append("")
    lines.append(
        "- A high similarity or an exact match means a candidate **resembles a "
        "known drug chemotype** — a retrospective sanity check that the pipeline "
        "can re-find established classes."
    )
    lines.append(
        "- It **does not prove de novo discovery**, **does not imply clinical "
        "efficacy**, and says nothing about safety, potency, selectivity, or "
        "developability."
    )
    lines.append(
        "- Comparator structures are public reference chemotypes only, provided "
        "for benchmarking; no synthesis routes, reaction conditions, or dosing "
        "are included."
    )
    lines.append("")

    # --- Limitations -----------------------------------------------------
    lines.append("## Limitations")
    lines.append("")
    limitations = r.get("limitations") or [
        "Retrospective benchmark against a small, curated public reference set; "
        "absence of recovery does not mean a candidate is novel or valuable.",
        "Similarity/scaffold overlap are structural proxies, not biological "
        "activity; they do not measure efficacy or safety.",
        "Comparator coverage is incomplete and modality-dependent.",
    ]
    for lim in limitations:
        lines.append(f"- {lim}")
    lines.append("")

    # --- Human responsibility -------------------------------------------
    lines.append("## Human responsibility")
    lines.append("")
    lines.append(
        "All results are rule-based structural analytics and require review by a "
        "qualified human expert (medicinal chemistry / regulatory). No claim of "
        "discovery, therapeutic benefit, or clinical use should be made on the "
        "basis of this retrospective sanity check. The human reviewer remains "
        "responsible for any decision or downstream interpretation."
    )
    lines.append("")

    return "\n".join(lines)
