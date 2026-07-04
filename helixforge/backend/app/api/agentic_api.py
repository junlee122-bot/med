from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.agents.orchestrator import OrchestratorAgent
from app.models.agent_schemas import (
    AgenticPipelineRequest, ErrorInjectionDemoRequest, SafetyLintRequest, SafetyLintResponse,
)
from app.services import agent_engine
from app.services.agent_engine import AGENT_SEQUENCE
from app.services.run_manifest import build_manifest
from app.services.safety_lint import lint_report
from app.storage import db

router = APIRouter(prefix="/api", tags=["agentic"])


def _agent_catalog() -> list[dict]:
    catalog = []
    for cls in [OrchestratorAgent] + list(AGENT_SEQUENCE):
        a = cls()
        catalog.append({
            "name": a.name, "role": a.role, "stage": a.stage,
            "stage_index": a.stage_index, "allowed_tools": a.allowed_tools,
        })
    return catalog


@router.get("/agents")
def list_agents():
    return {"agents": _agent_catalog(), "count": len(AGENT_SEQUENCE) + 1}


@router.get("/agents/runs")
def list_agent_runs(project_id: str | None = None, limit: int = 200):
    return {"agent_runs": db.list_records("agent_runs", project_id=project_id, limit=limit)}


@router.get("/agents/runs/{agent_run_id}")
def get_agent_run(agent_run_id: str):
    rec = db.get("agent_runs", agent_run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="agent run not found")
    return rec


@router.post("/workflow/run-agentic-pipeline")
def run_agentic_pipeline(req: AgenticPipelineRequest):
    return agent_engine.run_agentic_pipeline(req.model_dump())


@router.post("/workflow/run-error-injection-demo")
def run_error_injection_demo(req: ErrorInjectionDemoRequest):
    valid = {"invalid_smiles", "fake_citation", "tool_failure", "safety_flag", "overclaim", "contradictory_evidence"}
    if req.scenario not in valid:
        raise HTTPException(status_code=400, detail=f"scenario must be one of {sorted(valid)}")
    return agent_engine.run_error_injection_demo(req.scenario, req.condition, req.target_query)


@router.get("/workflow/runs/{run_id}/agents")
def run_agents(run_id: str):
    runs = [r for r in db.list_records("agent_runs", limit=1000) if r.get("workflow_run_id") == run_id]
    runs.sort(key=lambda r: r.get("stage_index", 0))
    return {"run_id": run_id, "agent_runs": runs}


@router.get("/workflow/runs/{run_id}/revisions")
def run_revisions(run_id: str):
    revs = [r for r in db.list_records("revision_events", limit=1000) if r.get("workflow_run_id") == run_id]
    return {"run_id": run_id, "revision_events": revs}


@router.get("/workflow/runs/{run_id}/manifest")
def run_manifest(run_id: str):
    if not db.get("workflow_runs", run_id):
        raise HTTPException(status_code=404, detail="run not found")
    return build_manifest(run_id)


@router.post("/safety/lint-report", response_model=SafetyLintResponse)
def safety_lint_report(req: SafetyLintRequest):
    md = req.markdown
    if md is None and req.report_id:
        rep = db.get("reports", req.report_id)
        if not rep:
            raise HTTPException(status_code=404, detail="report not found")
        md = rep.get("markdown", "")
    if md is None:
        raise HTTPException(status_code=400, detail="provide markdown or report_id")
    return SafetyLintResponse(**lint_report(md))
