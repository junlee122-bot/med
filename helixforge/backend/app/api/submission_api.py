from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import ai_interaction_ledger as ledger
from app.services import release_readiness, submission_pack
from app.services.submission_pack import ARTIFACT_TYPES
from app.storage import db

router = APIRouter(prefix="/api", tags=["submission"])


class GenerateRequest(BaseModel):
    artifact_type: str = "korean_proposal"
    run_id: str | None = None


class ManualNoteRequest(BaseModel):
    run_id: str
    note: str
    author: str = "human"


# ---- Submission Center ----
@router.post("/submission/generate")
def submission_generate(req: GenerateRequest):
    run = db.get("workflow_runs", req.run_id) if req.run_id else None
    if req.run_id and not run:
        raise HTTPException(status_code=404, detail="workflow run not found")
    if req.artifact_type == "all":
        return {"artifacts": submission_pack.generate_all(run=run)}
    if req.artifact_type not in ARTIFACT_TYPES:
        raise HTTPException(status_code=400, detail=f"artifact_type must be one of {ARTIFACT_TYPES + ['all']}")
    return submission_pack.generate_artifact(req.artifact_type, run=run)


@router.get("/submission/artifacts")
def submission_artifacts(run_id: str | None = None):
    try:
        artifacts = submission_pack.list_artifacts(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"artifacts": artifacts, "types": ARTIFACT_TYPES}


@router.get("/submission/artifacts/{artifact_id}")
def submission_artifact(artifact_id: str, run_id: str | None = None):
    try:
        a = submission_pack.get_artifact(artifact_id, run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not a:
        raise HTTPException(status_code=404, detail="artifact not found")
    return a


@router.get("/submission/bundle")
def submission_bundle(run_id: str | None = None):
    try:
        return submission_pack.bundle(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/submission/check")
def submission_check(run_id: str | None = None):
    try:
        return submission_pack.check(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---- Release readiness ----
@router.get("/release-readiness")
def release_readiness_get(run_id: str | None = None):
    try:
        return release_readiness.compute(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/release-readiness/run")
def release_readiness_run(run_id: str | None = None):
    try:
        return release_readiness.compute(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---- AI interaction ledger ----
@router.get("/ai-ledger")
def ai_ledger(run_id: str | None = None, limit: int = 500):
    if run_id and not db.get("workflow_runs", run_id):
        raise HTTPException(status_code=404, detail="workflow run not found")
    return {"interactions": ledger.list_interactions(run_id, limit)}


@router.get("/ai-ledger/runs/{run_id}")
def ai_ledger_run(run_id: str):
    if not db.get("workflow_runs", run_id):
        raise HTTPException(status_code=404, detail="workflow run not found")
    return {"summary": ledger.summary_for_run(run_id), "interactions": ledger.list_interactions(run_id)}


@router.post("/ai-ledger/manual-note")
def ai_ledger_note(req: ManualNoteRequest):
    if not db.get("workflow_runs", req.run_id):
        raise HTTPException(status_code=404, detail="workflow run not found")
    return ledger.manual_note(req.run_id, req.note, req.author)
