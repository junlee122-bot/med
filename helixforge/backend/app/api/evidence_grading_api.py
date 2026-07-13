from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import evidence_grading
from app.storage import db

router = APIRouter(prefix="/api", tags=["evidence-grading"])


@router.get("/evidence-grades/run/{run_id}")
def evidence_grades_run(run_id: str):
    try:
        return evidence_grading.grade_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/evidence-grades/compute")
def evidence_grades_compute(run_id: str | None = None):
    try:
        return evidence_grading.grade_run(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


class GradeClaimRequest(BaseModel):
    claim_text: str
    claim_type: str = "DISEASE_TARGET_ASSOCIATION"
    linked_evidence_ids: list[str] = []
    run_id: str | None = None


@router.post("/evidence-grades/grade-claim")
def evidence_grade_claim(req: GradeClaimRequest):
    if req.run_id:
        run = db.get("workflow_runs", req.run_id)
        if not run:
            raise HTTPException(status_code=404, detail="workflow run not found")
        ev = db.list_records(
            "evidence_items", project_id=run.get("project_id"),
            workflow_run_id=req.run_id, limit=1000,
        )
    else:
        ev = []
    return evidence_grading.grade_claim(req.model_dump(), ev)


class LintReportRequest(BaseModel):
    markdown: str | None = None
    report_id: str | None = None


@router.post("/evidence-grades/lint-report")
def evidence_grades_lint_report(req: LintReportRequest):
    md = req.markdown
    if md is None and req.report_id:
        rep = db.get("reports", req.report_id)
        md = rep.get("markdown", "") if rep else ""
    return evidence_grading.detect_unsupported_strong_claims(md or "")
