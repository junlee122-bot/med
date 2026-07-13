from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.provenance import redact_secrets
from app.services.run_manifest import build_manifest
from app.services.safety_lint import lint_report
from app.storage import db

router = APIRouter(prefix="/api/export", tags=["export"])


def _by_run(table: str, run_id: str, project_id: str | None) -> list[dict]:
    return db.list_records(
        table, project_id=project_id, workflow_run_id=run_id, limit=2000
    )


def _report_for_run(report_id: str | None, run_id: str, project_id: str | None) -> dict:
    if not report_id:
        return {}
    report = db.get("reports", report_id) or {}
    if (report.get("project_id") != project_id
            or report.get("workflow_run_id") != run_id):
        return {}
    return report


@router.get("/run/{run_id}")
def export_run(run_id: str):
    """Self-contained JSON bundle for a run: report, audit, agents, tools,
    evidence, targets, molecules, evaluation, safety lint, and manifest."""
    run = db.get("workflow_runs", run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    project_id = run.get("project_id")
    report = _report_for_run(run.get("report_id"), run_id, project_id)
    ko_report = _report_for_run(run.get("ko_report_id"), run_id, project_id)
    md = report.get("markdown", "")
    evidence = _by_run("evidence_items", run_id, project_id)
    targets = _by_run("target_candidates", run_id, project_id)
    molecules = _by_run("molecule_candidates", run_id, project_id)
    agent_runs = _by_run("agent_runs", run_id, project_id)
    revisions = _by_run("revision_events", run_id, project_id)
    manifest = build_manifest(run_id)
    # The generic manifest builder historically reports project totals. An
    # exported run must describe only the records included in this bundle.
    manifest.update({
        "evidence_count": len(evidence),
        "target_count": len(targets),
        "molecule_count": len(molecules),
        "agent_run_count": len(agent_runs),
        "revision_count": len(revisions),
    })
    bundle = {
        "run": run,
        "manifest": manifest,
        "report_markdown": md,
        "ko_report_markdown": ko_report.get("markdown", ""),
        "safety_lint": lint_report(md) if md else {"status": "PASS", "findings": []},
        "agent_runs": agent_runs,
        "revision_events": revisions,
        "audit_events": _by_run("audit_events", run_id, project_id),
        "tool_runs": _by_run("tool_runs", run_id, project_id),
        "evidence_items": evidence,
        "target_candidates": targets,
        "molecule_candidates": molecules,
        "evaluation_results": _by_run("evaluation_results", run_id, project_id),
        "disclaimer": "Research decision support only. Final responsibility belongs to the human research team.",
    }
    # Defensive: recursively sanitize every entity, not only report Markdown.
    return redact_secrets(bundle)
