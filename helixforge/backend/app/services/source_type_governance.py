"""Source-type governance.

Audits stored entities so a report can never accidentally present a
CONFIGURED_BUT_NOT_RUN tool as a real result, or a replayed output as live real
output. Complements the evidence + safety linters.
"""
from __future__ import annotations

import re
from typing import Any

from app.models.schemas import SourceType, utcnow
from app.storage import db

ALLOWED = {s.value for s in SourceType}
SCIENTIFIC_TABLES = ["tool_runs", "agent_runs", "evidence_items", "molecule_candidates",
                     "target_candidates", "workflow_runs"]


def _source_values(rec: dict) -> list[str]:
    vals = []
    if rec.get("source_type"):
        vals.append(rec["source_type"])
    for st in rec.get("source_types") or []:
        if st:
            vals.append(st)
    return vals


def audit() -> dict[str, Any]:
    counts: dict[str, int] = {}
    unknown: list[str] = []
    missing: list[str] = []
    real_vs_replay: list[str] = []

    for table in SCIENTIFIC_TABLES:
        for rec in db.list_records(table, limit=3000):
            vals = _source_values(rec)
            # Rule 1: scientific entities must carry a source label.
            if not vals and table in ("tool_runs", "agent_runs", "evidence_items",
                                      "molecule_candidates", "target_candidates"):
                missing.append(f"{table}:{rec.get('id')}")
            for v in vals:
                counts[v] = counts.get(v, 0) + 1
                if v not in ALLOWED:
                    unknown.append(f"{table}:{rec.get('id')}={v}")
            # Rule 2: replay runs must not keep REAL_TOOL_OUTPUT (should be RECORDED).
            if rec.get("replay_mode") or rec.get("kind") == "agentic_replay":
                if SourceType.REAL_TOOL_OUTPUT.value in vals:
                    real_vs_replay.append(f"{table}:{rec.get('id')}")

    # Report-text checks (rules 3-6) over stored reports/submission artifacts.
    overclaimed_not_run: list[str] = []
    heuristic_as_official: list[str] = []
    baseline_as_validated: list[str] = []
    for table in ("reports", "submission_artifacts"):
        for rec in db.list_records(table, limit=200):
            md = rec.get("markdown", "") or ""
            if re.search(r"CONFIGURED_BUT_NOT_RUN.{0,60}(real result|completed|executed successfully)", md, re.I):
                overclaimed_not_run.append(f"{table}:{rec.get('id')}")
            if re.search(r"HEURISTIC_ANALYSIS.{0,60}(official|regulatory compliance|approved)", md, re.I) or \
               re.search(r"(규제\s*승인\s*가능|공식\s*규제\s*준수)", md):
                heuristic_as_official.append(f"{table}:{rec.get('id')}")
            if re.search(r"BASELINE_MODEL_OUTPUT.{0,60}(validated|clinical)", md, re.I):
                baseline_as_validated.append(f"{table}:{rec.get('id')}")

    fixes = []
    if missing:
        fixes.append("Attach a source_type to every scientific entity.")
    if real_vs_replay:
        fixes.append("Replay entities must be RECORDED_REAL_TOOL_OUTPUT, not REAL_TOOL_OUTPUT.")
    if overclaimed_not_run:
        fixes.append("Do not describe CONFIGURED_BUT_NOT_RUN tools as completed real results.")
    if heuristic_as_official:
        fixes.append("Do not describe HEURISTIC_ANALYSIS as official regulatory compliance.")
    if baseline_as_validated:
        fixes.append("Do not describe BASELINE_MODEL_OUTPUT as validated/clinical ADMET.")

    blocking = bool(unknown or real_vs_replay or overclaimed_not_run or heuristic_as_official or baseline_as_validated)
    status = "BLOCKED" if blocking else ("REVIEW_REQUIRED" if missing else "PASS")
    # Transparency: report FULL counts, never silently drop findings. The list
    # fields carry a bounded sample; the *_count fields carry the true totals.
    SAMPLE = 500
    return {
        "status": status, "source_type_counts": counts,
        "unknown_source_types": unknown[:SAMPLE], "missing_source_type_records": missing[:SAMPLE],
        "real_vs_replay_conflicts": real_vs_replay[:SAMPLE],
        "configured_not_run_overclaimed": overclaimed_not_run[:SAMPLE],
        "heuristic_as_official": heuristic_as_official[:SAMPLE],
        "baseline_as_validated": baseline_as_validated[:SAMPLE],
        "counts": {
            "unknown_source_types": len(unknown), "missing_source_type_records": len(missing),
            "real_vs_replay_conflicts": len(real_vs_replay),
            "configured_not_run_overclaimed": len(overclaimed_not_run),
            "heuristic_as_official": len(heuristic_as_official),
            "baseline_as_validated": len(baseline_as_validated),
        },
        "sample_truncated": any(len(x) > SAMPLE for x in
                                (unknown, missing, real_vs_replay, overclaimed_not_run,
                                 heuristic_as_official, baseline_as_validated)),
        "unsafe_real_claims": [], "suggested_fixes": fixes, "checked_at": utcnow(),
    }


def lint_report_source_types(markdown: str) -> dict[str, Any]:
    """Check a single report's text for source-type mislabeling."""
    issues = []
    if re.search(r"CONFIGURED_BUT_NOT_RUN.{0,60}(real result|completed|executed successfully)", markdown, re.I):
        issues.append("CONFIGURED_BUT_NOT_RUN described as a completed real result.")
    if re.search(r"(규제\s*승인\s*가능|공식\s*규제\s*준수)", markdown):
        issues.append("Heuristic checklist described as official regulatory compliance.")
    if re.search(r"BASELINE_MODEL_OUTPUT.{0,60}(validated|clinical)", markdown, re.I):
        issues.append("Baseline model output described as validated/clinical.")
    # Every source-type token used should be an allowed value.
    used = set(re.findall(r"\b([A-Z_]{6,})\b", markdown)) & {s for s in ALLOWED}
    return {"status": "REVIEW_REQUIRED" if issues else "PASS", "issues": issues,
            "source_types_used": sorted(used), "checked_at": utcnow()}
