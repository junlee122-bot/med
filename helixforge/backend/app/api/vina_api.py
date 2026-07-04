from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.adapters import registry as reg
from app.models.schemas import VinaDockRequest, VinaResponse

router = APIRouter(prefix="/api/vina", tags=["vina"])


@router.post("/fixture-dock", response_model=VinaResponse)
def fixture_dock(req: VinaDockRequest):
    out = reg.vina.execute(req.model_dump(), project_id=req.project_id)
    return VinaResponse(**out)


@router.post("/score", response_model=VinaResponse)
def score(req: VinaDockRequest):
    # Scoring uses the same fixture engine (single-pose scoring path).
    payload = req.model_dump()
    payload["exhaustiveness"] = 1
    out = reg.vina.execute(payload, project_id=req.project_id)
    return VinaResponse(**out)


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = reg.vina.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Vina job {job_id} not found")
    return job
