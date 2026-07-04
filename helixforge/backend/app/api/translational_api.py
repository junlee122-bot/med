from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import (
    clinical_precedent_review, docking_protocol, pareto_optimization,
    target_biology_review, translational_readiness,
)
from app.storage import db

router = APIRouter(prefix="/api", tags=["translational"])


# ---- Target biology review (§3) ----
@router.post("/target-biology/review-run")
def target_biology_review_run(run_id: str | None = None):
    return target_biology_review.review_run(run_id)


@router.get("/target-biology/run/{run_id}")
def target_biology_run(run_id: str):
    return target_biology_review.review_run(run_id)


@router.get("/target-biology/target/{target_id}")
def target_biology_target(target_id: str):
    tgt = db.get("target_candidates", target_id)
    if not tgt:
        return {"error": "target not found"}
    pid = tgt.get("project_id")
    ev = db.list_records("evidence_items", project_id=pid, limit=1000) if pid else []
    return target_biology_review.review_target(tgt, ev)


# ---- Translational readiness (§11) ----
@router.post("/translational/readiness/run")
def translational_readiness_run(run_id: str | None = None):
    return translational_readiness.assess_run(run_id)


@router.get("/translational/readiness/{run_id}")
def translational_readiness_get(run_id: str):
    return translational_readiness.assess_run(run_id)


# ---- Clinical precedent review (§12) ----
@router.post("/clinical/precedent-review")
def clinical_precedent(run_id: str | None = None):
    return clinical_precedent_review.review_run(run_id)


@router.get("/clinical/precedent-review/{run_id}")
def clinical_precedent_get(run_id: str):
    return clinical_precedent_review.review_run(run_id)


# ---- Pareto optimization (§9) ----
@router.post("/optimization/pareto/run")
def pareto_run(run_id: str | None = None):
    return pareto_optimization.run(run_id)


@router.get("/optimization/pareto/run/{run_id}")
def pareto_run_get(run_id: str):
    return pareto_optimization.run(run_id)


# ---- Docking protocol governance (§8) ----
class DockingProtocolRequest(BaseModel):
    run_id: str | None = None
    receptor_identifier: str | None = None
    box_center: list | None = None
    box_size: list | None = None
    exhaustiveness: int | None = None
    mode: str = "NOT_CONFIGURED"
    score: float | None = None


@router.post("/docking/protocol/create")
def docking_protocol_create(req: DockingProtocolRequest):
    return docking_protocol.create_protocol(
        run_id=req.run_id, receptor_identifier=req.receptor_identifier,
        box_center=req.box_center, box_size=req.box_size,
        exhaustiveness=req.exhaustiveness, mode=req.mode, score=req.score)


@router.get("/docking/protocol/run/{run_id}")
def docking_protocol_run(run_id: str):
    return docking_protocol.run(None if run_id == "latest" else run_id)


class DockingLintRequest(BaseModel):
    record: dict


@router.post("/docking/protocol/lint")
def docking_protocol_lint(req: DockingLintRequest):
    return docking_protocol.lint_protocol(req.record)
