from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.services import source_type_governance as gov

router = APIRouter(prefix="/api/source-types", tags=["governance"])


class LintRequest(BaseModel):
    markdown: str = ""


@router.get("/audit")
def source_type_audit():
    return gov.audit()


@router.post("/lint-report")
def source_type_lint_report(req: LintRequest):
    return gov.lint_report_source_types(req.markdown)
