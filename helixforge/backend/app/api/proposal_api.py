from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import data_rights, proposal_writer
from app.storage import db

router = APIRouter(prefix="/api", tags=["proposal"])

PROPOSAL_KINDS = ["full_proposal_ko", "peer_one_pager_ko", "qa_defense_ko"]


class GenerateRequest(BaseModel):
    kind: str = "full_proposal_ko"


@router.post("/proposal/generate")
def proposal_generate(req: GenerateRequest):
    if req.kind == "all":
        return {"artifacts": proposal_writer.generate_all()}
    if req.kind not in PROPOSAL_KINDS:
        raise HTTPException(status_code=400, detail=f"kind must be one of {PROPOSAL_KINDS + ['all']}")
    return proposal_writer.generate(req.kind)


@router.get("/proposal/latest")
def proposal_latest():
    arts = [a for a in db.list_records("submission_artifacts", limit=200)
            if a.get("kind") in PROPOSAL_KINDS]
    return {"artifacts": arts[:10]}


@router.get("/proposal/export")
def proposal_export():
    return {"artifacts": proposal_writer.generate_all()}


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
