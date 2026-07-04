from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.models.agent_schemas import AgenticPipelineRequest
from app.services import agent_engine, evaluation
from app.storage import db

router = APIRouter(prefix="/api/evaluation", tags=["evaluation"])


@router.get("/summary")
def evaluation_summary(project_id: str | None = None, limit: int = 500):
    rows = db.list_records("evaluation_results", project_id=project_id, limit=limit)
    modules: dict[str, list] = {}
    for r in rows:
        modules.setdefault(r.get("module", "other"), []).append(
            {"metric": r.get("metric_name"), "value": r.get("value"), "status": r.get("status")})
    # Most recent agentic run's metrics, if available.
    runs = [r for r in db.list_records("workflow_runs", project_id=project_id, limit=50) if r.get("kind") == "agentic"]
    latest = runs[0] if runs else None
    return {"modules": modules, "module_count": len(modules), "metric_count": len(rows),
            "latest_run": latest.get("id") if latest else None,
            "latest_metrics": (latest or {}).get("metrics", {})}


@router.get("/runs/{run_id}")
def evaluation_run(run_id: str):
    rows = [r for r in db.list_records("evaluation_results", limit=1000) if r.get("workflow_run_id") == run_id]
    if not rows:
        raise HTTPException(status_code=404, detail="no evaluation metrics for run")
    run = db.get("workflow_runs", run_id) or {}
    return {"run_id": run_id, "metrics_flat": rows, "metrics": run.get("metrics", {})}


@router.post("/run-retrospective")
def run_retrospective(req: AgenticPipelineRequest):
    """Run the EGFR/NSCLC retrospective rediscovery benchmark end to end."""
    payload = req.model_dump()
    payload["evaluation_mode"] = "retrospective_rediscovery"
    result = agent_engine.run_agentic_pipeline(payload)
    metrics = result.get("metrics", {})
    retro = metrics.get("retrospective") or evaluation.retrospective_success(metrics, req.target_query)
    return {"run_id": result["run_id"], "retrospective": retro, "metrics": metrics,
            "report_id": result.get("report_id"), "ko_report_id": result.get("ko_report_id"),
            "disclaimer": result.get("disclaimer")}
