from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.adapters import registry as reg
from app.models.schemas import (
    PipelineRequest,
    ReportGenerateRequest,
    ReportResponse,
    SafetyResponse,
    SafetyScreenRequest,
    WorkflowRunResponse,
)
from app.services import audit, pipeline
from app.storage import db

router = APIRouter(prefix="/api", tags=["workflow"])


@router.post("/workflow/run-real-pipeline", response_model=WorkflowRunResponse)
def run_real_pipeline(req: PipelineRequest):
    return pipeline.run_pipeline(req.model_dump())


@router.post("/workflow/run-target-discovery", response_model=WorkflowRunResponse)
def run_target_discovery(req: PipelineRequest):
    payload = req.model_dump()
    payload["create_reinvent_config"] = False
    payload["run_vina_fixture"] = False
    return pipeline.run_pipeline(payload)


@router.post("/workflow/run-molecule-screening", response_model=WorkflowRunResponse)
def run_molecule_screening(req: PipelineRequest):
    payload = req.model_dump()
    payload["create_reinvent_config"] = True
    return pipeline.run_pipeline(payload)


@router.get("/workflow/runs/{run_id}")
def get_run(run_id: str):
    run = db.get("workflow_runs", run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    run["audit_events"] = db.list_records("audit_events", project_id=run.get("project_id"), limit=300, order="ASC")
    return run


@router.get("/audit/events")
def audit_events(project_id: str | None = None, limit: int = 200):
    return {"events": audit.list_events(project_id=project_id, limit=limit)}


@router.post("/safety/screen", response_model=SafetyResponse)
def safety_screen(req: SafetyScreenRequest):
    out = reg.safety.execute(req.model_dump(), project_id=req.project_id)
    return SafetyResponse(**out)


@router.post("/report/generate", response_model=ReportResponse)
def report_generate(req: ReportGenerateRequest):
    rep = reg.report.generate(req.project_id, req.workflow_run_id, req.title)
    return ReportResponse(**rep)


@router.get("/report/{report_id}", response_model=ReportResponse)
def get_report(report_id: str):
    rep = db.get("reports", report_id)
    if not rep:
        raise HTTPException(status_code=404, detail=f"Report {report_id} not found")
    # Report records come in two shapes: workflow reports carry a `json_audit`
    # payload, while agentic/hybrid reports (rep-en-<run_id> / rep-ko-<run_id>)
    # store their provenance as discrete fields instead. Fall back to the stored
    # provenance so both retrieve cleanly (no fabricated audit, markdown untouched).
    json_audit = rep.get("json_audit")
    if not isinstance(json_audit, dict):
        json_audit = {k: rep[k] for k in
                      ("workflow_run_id", "language", "type", "safety_lint",
                       "export_safe", "source_type") if k in rep}
    return ReportResponse(
        report_id=rep.get("id", report_id), title=rep.get("title", ""),
        created_at=rep.get("created_at", ""), markdown=rep.get("markdown", ""),
        json_audit=json_audit, format="markdown",
    )


@router.get("/reports")
def list_reports(project_id: str | None = None):
    reps = db.list_records("reports", project_id=project_id, limit=50)
    return {"reports": [{"report_id": r["id"], "title": r["title"], "created_at": r["created_at"],
                         "project_id": r.get("project_id")} for r in reps]}
