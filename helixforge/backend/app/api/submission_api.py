from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import ai_interaction_ledger as ledger
from app.services import release_readiness, submission_pack
from app.services.submission_pack import ARTIFACT_TYPES

router = APIRouter(prefix="/api", tags=["submission"])


class GenerateRequest(BaseModel):
    artifact_type: str = "korean_proposal"


class ManualNoteRequest(BaseModel):
    run_id: str
    note: str
    author: str = "human"


# ---- Submission Center ----
@router.post("/submission/generate")
def submission_generate(req: GenerateRequest):
    if req.artifact_type == "all":
        return {"artifacts": submission_pack.generate_all()}
    if req.artifact_type not in ARTIFACT_TYPES:
        raise HTTPException(status_code=400, detail=f"artifact_type must be one of {ARTIFACT_TYPES + ['all']}")
    return submission_pack.generate_artifact(req.artifact_type)


@router.get("/submission/artifacts")
def submission_artifacts():
    return {"artifacts": submission_pack.list_artifacts(), "types": ARTIFACT_TYPES}


@router.get("/submission/artifacts/{artifact_id}")
def submission_artifact(artifact_id: str):
    a = submission_pack.get_artifact(artifact_id)
    if not a:
        raise HTTPException(status_code=404, detail="artifact not found")
    return a


@router.get("/submission/bundle")
def submission_bundle():
    return submission_pack.bundle()


@router.post("/submission/check")
def submission_check():
    return submission_pack.check()


# ---- Release readiness ----
@router.get("/release-readiness")
def release_readiness_get():
    return release_readiness.compute()


@router.post("/release-readiness/run")
def release_readiness_run():
    return release_readiness.compute()


# ---- AI interaction ledger ----
@router.get("/ai-ledger")
def ai_ledger(run_id: str | None = None, limit: int = 500):
    return {"interactions": ledger.list_interactions(run_id, limit)}


@router.get("/ai-ledger/runs/{run_id}")
def ai_ledger_run(run_id: str):
    return {"summary": ledger.summary_for_run(run_id), "interactions": ledger.list_interactions(run_id)}


@router.post("/ai-ledger/manual-note")
def ai_ledger_note(req: ManualNoteRequest):
    return ledger.manual_note(req.run_id, req.note, req.author)
