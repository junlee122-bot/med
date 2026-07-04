from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import evidence_grading
from app.storage import db

router = APIRouter(prefix="/api", tags=["evidence-grading"])


@router.get("/evidence-grades/run/{run_id}")
def evidence_grades_run(run_id: str):
    return evidence_grading.grade_run(run_id)


@router.post("/evidence-grades/compute")
def evidence_grades_compute(run_id: str | None = None):
    return evidence_grading.grade_run(run_id)


class GradeClaimRequest(BaseModel):
    claim_text: str
    claim_type: str = "DISEASE_TARGET_ASSOCIATION"
    linked_evidence_ids: list[str] = []
    run_id: str | None = None


@router.post("/evidence-grades/grade-claim")
def evidence_grade_claim(req: GradeClaimRequest):
    ev = db.list_records("evidence_items", limit=1000)
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
