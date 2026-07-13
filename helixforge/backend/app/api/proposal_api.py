from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import data_rights, proposal_writer

router = APIRouter(prefix="/api", tags=["proposal"])

PROPOSAL_KINDS = ["full_proposal_ko", "peer_one_pager_ko", "qa_defense_ko"]


class GenerateRequest(BaseModel):
    kind: str = "full_proposal_ko"
    run_id: str | None = None


@router.post("/proposal/generate")
def proposal_generate(req: GenerateRequest):
    if req.kind not in PROPOSAL_KINDS:
        if req.kind != "all":
            raise HTTPException(status_code=400, detail=f"kind must be one of {PROPOSAL_KINDS + ['all']}")
    try:
        if req.kind == "all":
            return {"artifacts": proposal_writer.generate_all(req.run_id)}
        return proposal_writer.generate(req.kind, req.run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/proposal/latest")
def proposal_latest(run_id: str | None = None):
    try:
        return {"artifacts": proposal_writer.list_artifacts(run_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/proposal/export")
def proposal_export(run_id: str | None = None):
    """Export already-generated artifacts without mutating state on GET."""
    try:
        return {"artifacts": proposal_writer.list_artifacts(run_id)}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---- Data rights ----
@router.get("/data-rights")
def data_rights_list():
    return data_rights.list_records()


@router.get("/data-rights/snapshot/{snapshot_id}")
def data_rights_snapshot(snapshot_id: str):
    try:
        return data_rights.snapshot_data_rights(snapshot_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/data-rights/check-submission")
def data_rights_check_submission():
    return data_rights.check_submission()
