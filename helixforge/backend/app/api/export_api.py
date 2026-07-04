from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.services.provenance import redact_secrets
from app.services.run_manifest import build_manifest
from app.services.safety_lint import lint_report
from app.storage import db

router = APIRouter(prefix="/api/export", tags=["export"])


def _by_run(table: str, run_id: str, project_id: str | None) -> list[dict]:
    rows = db.list_records(table, project_id=project_id, limit=2000)
    return [r for r in rows if r.get("workflow_run_id") == run_id] or rows


@router.get("/run/{run_id}")
def export_run(run_id: str):
    """Self-contained JSON bundle for a run: report, audit, agents, tools,
    evidence, targets, molecules, evaluation, safety lint, and manifest."""
    run = db.get("workflow_runs", run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    project_id = run.get("project_id")
    report = db.get("reports", run.get("report_id") or "") or {}
    ko_report = db.get("reports", run.get("ko_report_id") or "") or {}
    md = report.get("markdown", "")
    bundle = {
        "run": run,
        "manifest": build_manifest(run_id),
        "report_markdown": md,
        "ko_report_markdown": ko_report.get("markdown", ""),
        "safety_lint": lint_report(md) if md else {"status": "PASS", "findings": []},
        "agent_runs": _by_run("agent_runs", run_id, project_id),
        "revision_events": _by_run("revision_events", run_id, project_id),
        "audit_events": [e for e in db.list_records("audit_events", project_id=project_id, limit=2000)
                         if e.get("workflow_run_id") == run_id],
        "tool_runs": [t for t in db.list_records("tool_runs", project_id=project_id, limit=2000)
                      if t.get("workflow_run_id") == run_id],
        "evidence_items": db.list_records("evidence_items", project_id=project_id, limit=500),
        "target_candidates": db.list_records("target_candidates", project_id=project_id, limit=200),
        "molecule_candidates": db.list_records("molecule_candidates", project_id=project_id, limit=500),
        "evaluation_results": _by_run("evaluation_results", run_id, project_id),
        "disclaimer": "Research decision support only. Final responsibility belongs to the human research team.",
    }
    # Defensive: never leak secrets in the report text.
    bundle["report_markdown"] = redact_secrets(bundle["report_markdown"])
    return bundle
