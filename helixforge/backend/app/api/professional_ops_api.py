from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal

from app.services import (
    admet_validation, expert_review_board, identity_normalization,
    professional_release, red_team_pro,
)
from app.storage import db

router = APIRouter(prefix="/api", tags=["professional-ops"])


def _persisted_result(table: str, run_id: str | None = None, **empty_fields):
    if run_id is not None and not db.get("workflow_runs", run_id):
        raise HTTPException(status_code=404, detail="workflow run not found")
    records = db.list_records(table, workflow_run_id=run_id, limit=1)
    if records:
        return records[0]
    return {
        "status": "NOT_COMPUTED", "run_id": run_id, "workflow_run_id": run_id,
        **empty_fields,
    }


# ---- Professional release scorecard (§20) ----
@router.get("/release-readiness/professional/latest")
def professional_release_latest(run_id: str | None = None):
    return _persisted_result(
        "professional_evaluations", run_id, categories=[], blocking_count=0,
    )


@router.post("/release-readiness/professional")
def professional_release_compute(run_id: str | None = None):
    try:
        return professional_release.persist(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---- Expert review board (§14) ----
@router.post("/expert-review/generate-from-run")
def expert_review_generate(run_id: str | None = None):
    try:
        return expert_review_board.generate_from_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/expert-review/items")
def expert_review_items(role: str | None = None, status: str | None = None,
                        run_id: str | None = None):
    return expert_review_board.list_items(role, status, run_id)


class DecisionRequest(BaseModel):
    decision: Literal[
        "APPROVE_FOR_PROPOSAL", "APPROVE_FOR_DEMO_ONLY", "NEEDS_MORE_EVIDENCE",
        "REJECT", "ESCALATE", "NOT_APPLICABLE",
    ]
    comment: str = ""


@router.post("/expert-review/items/{item_id}/decision")
def expert_review_decision(item_id: str, req: DecisionRequest):
    # Reviewer identity/role are derived server-side.  Accepting those fields
    # from a browser would let any caller forge a privileged sign-off.
    try:
        return expert_review_board.record_decision(
            item_id, req.decision, reviewer_name="authenticated-api-user", comment=req.comment
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/expert-review/summary/{run_id}")
def expert_review_summary(run_id: str):
    if not db.get("workflow_runs", run_id):
        raise HTTPException(status_code=404, detail="workflow run not found")
    return expert_review_board.summary_for_run(run_id)


# ---- Identity normalization (§18) ----
@router.post("/identity/normalize-run")
def identity_normalize_run(run_id: str | None = None):
    try:
        return identity_normalization.normalize_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/identity/run/{run_id}")
def identity_run(run_id: str):
    return _persisted_result(
        "identity_normalizations", run_id, targets=[], molecules=[], trials=[],
        duplicate_molecules=[],
    )


class NormalizeTargetRequest(BaseModel):
    target: dict


@router.post("/identity/normalize-target")
def identity_normalize_target(req: NormalizeTargetRequest):
    return identity_normalization.normalize_target(req.target)


class NormalizeMoleculeRequest(BaseModel):
    molecule: dict


@router.post("/identity/normalize-molecule")
def identity_normalize_molecule(req: NormalizeMoleculeRequest):
    return identity_normalization.normalize_molecule(req.molecule)


class NormalizeDiseaseRequest(BaseModel):
    condition: str


@router.post("/identity/normalize-disease")
def identity_normalize_disease(req: NormalizeDiseaseRequest):
    return identity_normalization.normalize_disease(req.condition)


# ---- ADMET validation (§7) ----
class ADMETTrainRequest(BaseModel):
    dataset_name: str = "demo_logP"
    task: str = "regression"
    split_strategy: str = "scaffold"


@router.post("/admet/validation/train")
def admet_train(req: ADMETTrainRequest):
    return admet_validation.run_validation(dataset_name=req.dataset_name, task=req.task,
                                           split_strategy=req.split_strategy)


@router.get("/admet/validation/models")
def admet_models():
    return {"models": admet_validation.models()}


# ---- Professional red-team 2.0 (§17) ----
@router.post("/red-team/professional/run")
def red_team_professional_run():
    return red_team_pro.run_suite()


@router.get("/red-team/professional/latest")
def red_team_professional_latest():
    return red_team_pro.run_suite()
