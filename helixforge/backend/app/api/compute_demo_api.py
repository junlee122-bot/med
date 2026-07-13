"""Compute demos, GPU worker contracts, and compute record/replay endpoints
(Phase 8, Sections 19, 22, 23, 24). No GPU, no LLM key, no paid job."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.compute import gpu_worker_contracts
from app.services import compute_snapshot, cpu_demo

router = APIRouter(prefix="/api", tags=["compute-demo"])


# ---- GPU worker contracts ----
@router.get("/compute/worker-contracts")
def worker_contracts():
    return gpu_worker_contracts.list_contracts()


@router.get("/compute/worker-contracts/{job_type}")
def worker_contract(job_type: str):
    c = gpu_worker_contracts.get_contract(job_type)
    if c.get("status") == "UNKNOWN_JOB_TYPE":
        raise HTTPException(status_code=404, detail="unknown job type")
    return c


# ---- CPU scientific demo ----
class DemoRequest(BaseModel):
    condition: str = "non-small cell lung cancer"
    target: str = "EGFR"


@router.post("/demo/run-cpu-scientific-demo")
def run_cpu_demo(req: DemoRequest):
    return cpu_demo.run_cpu_scientific_demo(condition=req.condition, target=req.target)


class GpuDryRunRequest(BaseModel):
    target: str = "EGFR"
    pricing_profile_id: str | None = None


@router.post("/demo/run-gpu-readiness-dry-run")
def run_gpu_dry_run(req: GpuDryRunRequest):
    try:
        return cpu_demo.run_gpu_readiness_dry_run(
            target=req.target, pricing_profile_id=req.pricing_profile_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


# ---- Compute record/replay ----
@router.post("/snapshots/create-compute-from-run/{run_id}")
def create_compute_snapshot(run_id: str):
    try:
        return compute_snapshot.create_from_run(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.post("/snapshots/{snapshot_id}/replay-compute")
def replay_compute_snapshot(snapshot_id: str):
    try:
        return compute_snapshot.replay(snapshot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/snapshots/{snapshot_id}/compute-manifest")
def compute_manifest(snapshot_id: str):
    try:
        return compute_snapshot.manifest(snapshot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/snapshots/{snapshot_id}/compute-cost-summary")
def compute_cost_summary(snapshot_id: str):
    try:
        return compute_snapshot.cost_summary(snapshot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# ---- Compute evaluation + release readiness (Section 28) ----
@router.get("/evaluation/compute-summary/{run_id}")
def evaluation_compute_summary(run_id: str):
    from app.services import compute_evaluation
    try:
        return compute_evaluation.compute_summary(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/evaluation/compute-summary")
def evaluation_compute_summary_latest():
    from app.services import compute_evaluation
    return compute_evaluation.compute_summary(None)


@router.get("/release-readiness/compute")
def release_readiness_compute(run_id: str | None = None):
    from app.services import compute_evaluation
    try:
        return compute_evaluation.release_categories(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---- Compute submission artifacts (Section 27) ----
class ComputeArtifactRequest(BaseModel):
    kind: str = "cpu_scientific_capability"
    run_id: str | None = None


@router.post("/compute/artifacts/generate")
def generate_compute_artifact(req: ComputeArtifactRequest):
    from app.services import compute_reports
    try:
        if req.kind == "all":
            return {"artifacts": compute_reports.generate_all(req.run_id)}
        return compute_reports.generate(req.kind, req.run_id)
    except ValueError as exc:
        status = 404 if str(exc) == "workflow run not found" else 400
        raise HTTPException(status_code=status, detail=str(exc)) from exc
