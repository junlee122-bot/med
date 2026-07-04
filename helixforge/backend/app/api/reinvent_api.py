from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.adapters import registry as reg
from app.models.schemas import ReinventConfigRequest, ReinventResponse, ReinventRunRequest
from app.services import audit
from app.models.schemas import SourceType, ValidationStatus

router = APIRouter(prefix="/api/reinvent", tags=["reinvent"])


@router.post("/create-config", response_model=ReinventResponse)
def create_config(req: ReinventConfigRequest):
    out = reg.reinvent.create_config(req.model_dump())
    audit.record_tool_run(
        tool_name="REINVENT4", tool_category="chemistry",
        source_type=SourceType(out["source_type"]), input_summary=out["input_summary"],
        output_summary=out["output_summary"], validation_status=ValidationStatus(out["validation_status"]),
        project_id=req.project_id,
    )
    return ReinventResponse(**out)


@router.post("/run", response_model=ReinventResponse)
def run(req: ReinventRunRequest):
    out = reg.reinvent.execute(req.model_dump(), project_id=req.project_id)
    return ReinventResponse(**out)


@router.post("/parse-results", response_model=ReinventResponse)
def parse_results(payload: dict):
    out = reg.reinvent.parse_results(payload)
    return ReinventResponse(**out)


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = reg.reinvent.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"REINVENT4 job {job_id} not found")
    return job
