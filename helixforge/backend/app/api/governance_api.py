from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import source_type_governance as gov
from app.storage import db

router = APIRouter(prefix="/api/source-types", tags=["governance"])


class LintRequest(BaseModel):
    markdown: str = ""


@router.get("/audit")
def source_type_audit(run_id: str | None = None):
    if not run_id:
        return gov.audit()
    run = db.get("workflow_runs", run_id)
    if not run:
        raise HTTPException(status_code=404, detail="workflow run not found")
    return gov.audit(run.get("project_id"), run_id)


@router.post("/lint-report")
def source_type_lint_report(req: LintRequest):
    return gov.lint_report_source_types(req.markdown)
