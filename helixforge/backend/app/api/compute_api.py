"""Compute Center API (Phase 8, Priority 1): capabilities, jobs, providers, costs,
artifacts, security, and compute decisions. CPU-first; GPU optional & governed."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.compute import (
    artifact_registry, capability_detector, cost_guard, job_manager, security,
)
from app.compute.provider_registry import get_provider, list_providers
from app.services import compute_aware_planner
from app.storage import db

router = APIRouter(prefix="/api/compute", tags=["compute"])


# ---- Capabilities ----
@router.get("/capabilities")
def capabilities(mode: str = "local"):
    return capability_detector.detect(mode)


# ---- Compute-aware planning ----
class PlanRequest(BaseModel):
    workflow_run_id: str | None = None
    requested_capabilities: list[str] | None = None
    budget_usd: float | None = None
    presentation_safe: bool = True


@router.post("/plan")
def plan(req: PlanRequest):
    if req.workflow_run_id and not db.get("workflow_runs", req.workflow_run_id):
        raise HTTPException(status_code=404, detail="workflow run not found")
    caps = capability_detector.detect("local")
    return compute_aware_planner.plan_compute(
        caps, requested_capabilities=req.requested_capabilities,
        workflow_run_id=req.workflow_run_id, budget_usd=req.budget_usd,
        presentation_safe=req.presentation_safe)


# ---- Jobs ----
class JobSpecRequest(BaseModel):
    spec: dict = Field(default_factory=dict)
    pricing_profile_id: str | None = None


@router.post("/jobs")
def create_job(req: JobSpecRequest):
    try:
        return job_manager.create_job(req.spec, requested_by_agent="api-administrator",
                                      pricing_profile_id=req.pricing_profile_id)
    except ValueError as exc:
        status = 404 if "workflow run not found" in str(exc) else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.post("/jobs/dry-run")
def dry_run(req: JobSpecRequest):
    try:
        return job_manager.dry_run(req.spec, pricing_profile_id=req.pricing_profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/jobs")
def list_jobs(project_id: str | None = None, limit: int = 100):
    return {"jobs": job_manager.list_jobs(project_id=project_id, limit=limit)}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="job not found")
    return job


class ApproveRequest(BaseModel):
    pass


@router.post("/jobs/{job_id}/approve")
def approve_job(job_id: str, req: ApproveRequest):
    try:
        return job_manager.approve_job(job_id, approved_by="api-administrator")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/approve-cost")
def approve_cost(job_id: str, req: ApproveRequest):
    return approve_job(job_id, req)


@router.post("/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    try:
        return job_manager.cancel_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/retry")
def retry_job(job_id: str):
    try:
        return job_manager.retry_job(job_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs/{job_id}/artifacts")
def job_artifacts(job_id: str):
    return {"artifacts": artifact_registry.list_artifacts(job_id)}


# ---- Cost planning ----
class EstimateRequest(BaseModel):
    spec: dict = Field(default_factory=dict)
    pricing_profile_id: str | None = None


@router.post("/estimate")
def estimate(req: EstimateRequest):
    from app.compute import job_spec as JS
    v = JS.validate_gpu_job_spec(req.spec)
    try:
        est = cost_guard.estimate_gpu_job_cost(v["normalized"], req.pricing_profile_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    budget = cost_guard.check_budget(est["estimated_cost_usd"], v["normalized"]["resource_request"]["max_cost_usd"])
    return {"validated": v["valid"], "errors": v["errors"], "estimate": est, "budget": budget}


@router.get("/costs")
def costs():
    return cost_guard.costs_summary()


@router.get("/pricing-profiles")
def pricing_profiles():
    return cost_guard.list_pricing_profiles()


class PricingProfileRequest(BaseModel):
    id: str = Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9._-]+$")
    gpu_class: str = ""
    price_per_gpu_hour: float = Field(default=2.0, ge=0.0, le=100_000.0)
    storage_per_gb_month: float = Field(default=0.1, ge=0.0, le=100_000.0)
    currency: str = "USD"


@router.post("/pricing-profiles")
def create_pricing_profile(req: PricingProfileRequest):
    from app.models.schemas import utcnow
    rec = {"id": f"pricing-profile-{req.id}", "profile_id": req.id,
           "event_type": "pricing_profile", "created_at": utcnow(),
           "pricing_snapshot": req.model_dump()}
    db.insert("compute_cost_events", rec)
    return {"saved": True, "profile": req.model_dump(),
            "disclaimer": cost_guard.PRICING_DISCLAIMER}


# ---- Providers ----
@router.get("/providers")
def providers():
    return list_providers()


@router.get("/providers/{provider_id}/health")
def provider_health(provider_id: str, live: bool = False):
    return get_provider(provider_id).health_check(live=live)


@router.post("/providers/{provider_id}/test")
def provider_test(provider_id: str):
    # A "test" is a local dry health-check — never a paid call.
    return get_provider(provider_id).health_check(live=False)


# ---- Artifacts ----
@router.get("/artifacts")
def artifacts():
    return {"artifacts": artifact_registry.list_artifacts()}


@router.get("/artifacts/types")
def compute_artifact_types():
    """List submission-report types before the dynamic artifact-id route."""
    from app.services import compute_reports
    return {"types": compute_reports.ARTIFACT_TYPES}


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: str):
    art = artifact_registry.get_artifact(artifact_id)
    if not art:
        raise HTTPException(status_code=404, detail="artifact not found")
    return art


# ---- Security ----
@router.post("/security/audit")
def security_audit():
    return security.security_audit()


@router.get("/security/policies")
def security_policies():
    return security.security_policies()


# ---- Compute-planner agent (Section 25) ----
class PlanAgentRequest(BaseModel):
    workflow_run_id: str
    project_id: str | None = None
    condition: str = "non-small cell lung cancer"
    target_query: str = "EGFR"


@router.post("/plan-agent")
def plan_agent(req: PlanAgentRequest):
    from app.agents.base import AgentContext
    from app.agents.compute_planner_agent import ComputePlannerAgent
    run = db.get("workflow_runs", req.workflow_run_id)
    if not run:
        raise HTTPException(status_code=404, detail="workflow run not found")
    project_id = run.get("project_id")
    if not project_id:
        raise HTTPException(status_code=409, detail="workflow run has no project")
    if req.project_id is not None and req.project_id != project_id:
        raise HTTPException(status_code=404, detail="workflow run not found")
    ctx = AgentContext(project_id=project_id,
                       workflow_run_id=req.workflow_run_id,
                       condition=req.condition, target_query=req.target_query)
    out = ComputePlannerAgent().run(ctx)
    return {
        "agent": "ComputePlannerAgent", "workflow_run_id": req.workflow_run_id,
        "compute_profile": ctx.shared.get("compute_profile"),
        "output_summary": out.output_summary, "rationale": out.rationale,
        "assumptions": out.assumptions, "uncertainty_notes": out.uncertainty_notes,
        "next_action": out.next_action, "confidence": out.confidence,
        "validation_checks": out.validation_checks, "source_types": out.source_types,
        "compute_decisions": ctx.shared.get("compute_decisions", []),
    }


# ---- Compute decisions for a run ----
@router.get("/runs/{run_id}/decisions")
def run_decisions(run_id: str):
    if not db.get("workflow_runs", run_id):
        raise HTTPException(status_code=404, detail="workflow run not found")
    return {"run_id": run_id, "compute_decisions": compute_aware_planner.get_decisions(run_id)}


# ---- Config ----
@router.get("/config")
def compute_config():
    from app.compute.config import get_compute_config
    return get_compute_config().public_dict()
