from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import (
    clinical_precedent_review, docking_protocol, pareto_optimization,
    target_biology_review, translational_readiness,
)
from app.storage import db

router = APIRouter(prefix="/api", tags=["translational"])


def _resolve_run_id(run_id: str) -> str | None:
    if run_id == "latest":
        runs = db.list_records("workflow_runs", limit=1)
        return runs[0].get("id") if runs else None
    if not db.get("workflow_runs", run_id):
        raise HTTPException(status_code=404, detail="workflow run not found")
    return run_id


def _persisted_run_result(table: str, run_id: str, **empty_fields):
    resolved = _resolve_run_id(run_id)
    if resolved is None:
        return {
            "status": "NOT_COMPUTED", "run_id": None, "workflow_run_id": None,
            **empty_fields,
        }
    records = db.list_records(table, workflow_run_id=resolved, limit=1)
    if records:
        return records[0]
    return {
        "status": "NOT_COMPUTED", "run_id": resolved, "workflow_run_id": resolved,
        **empty_fields,
    }


# ---- Target biology review (§3) ----
@router.post("/target-biology/review-run")
def target_biology_review_run(run_id: str | None = None):
    try:
        return target_biology_review.review_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/target-biology/run/{run_id}")
def target_biology_run(run_id: str):
    return _persisted_run_result(
        "target_biology_reviews", run_id, reviews=[], count=0, status_distribution={},
    )


@router.get("/target-biology/target/{target_id}")
def target_biology_target(target_id: str):
    tgt = db.get("target_candidates", target_id)
    if not tgt:
        return {"error": "target not found"}
    pid = tgt.get("project_id")
    rid = tgt.get("workflow_run_id") or tgt.get("run_id")
    ev = db.list_records("evidence_items", project_id=pid, workflow_run_id=rid, limit=1000) if pid and rid else []
    return target_biology_review.review_target(tgt, ev)


# ---- Translational readiness (§11) ----
@router.post("/translational/readiness/run")
def translational_readiness_run(run_id: str | None = None):
    try:
        return translational_readiness.assess_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/translational/readiness/{run_id}")
def translational_readiness_get(run_id: str):
    return _persisted_run_result(
        "translational_assessments", run_id,
        readiness_level=None, blocking_gaps=[], recommended_next_actions=[],
    )


# ---- Clinical precedent review (§12) ----
@router.post("/clinical/precedent-review")
def clinical_precedent(run_id: str | None = None):
    try:
        return clinical_precedent_review.review_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/clinical/precedent-review/{run_id}")
def clinical_precedent_get(run_id: str):
    return _persisted_run_result(
        "clinical_precedent_reviews", run_id,
        trials=[], precedent_strength="NOT_COMPUTED",
    )


# ---- Pareto optimization (§9) ----
@router.post("/optimization/pareto/run")
def pareto_run(run_id: str | None = None):
    try:
        return pareto_optimization.run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/optimization/pareto/run/{run_id}")
def pareto_run_get(run_id: str):
    return _persisted_run_result(
        "pareto_analyses", run_id, front=[], all_candidates=[], objective_names=[],
    )


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


@router.post("/docking/protocol/run/{run_id}")
def docking_protocol_compute_run(run_id: str):
    resolved = _resolve_run_id(run_id)
    if resolved is None:
        raise HTTPException(status_code=404, detail="workflow run not found")
    try:
        return docking_protocol.run(resolved)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/docking/protocol/run/{run_id}")
def docking_protocol_run(run_id: str):
    record = _persisted_run_result("docking_protocols", run_id, protocol=None, lint=None)
    if record.get("status") == "NOT_COMPUTED":
        return record
    return {
        "run_id": record.get("run_id") or record.get("workflow_run_id"),
        "protocol": record,
        "lint": record.get("lint"),
        "checked_at": (record.get("lint") or {}).get("checked_at") or record.get("created_at"),
    }


class DockingLintRequest(BaseModel):
    record: dict


@router.post("/docking/protocol/lint")
def docking_protocol_lint(req: DockingLintRequest):
    return docking_protocol.lint_protocol(req.record)
