from __future__ import annotations

from fastapi import APIRouter, HTTPException

from pydantic import BaseModel

from app.agents.citation_verifier_agent import verify_identifier
from app.models.agent_schemas import EvidenceVerifyRequest
from app.services.evidence_linter import lint_run
from app.storage import db

router = APIRouter(prefix="/api", tags=["data"])


class EvidenceLintRequest(BaseModel):
    run_id: str | None = None
    report_id: str | None = None
    markdown: str | None = None


@router.post("/evidence/lint-report")
def evidence_lint_report(req: EvidenceLintRequest):
    md = req.markdown
    run_id = req.run_id
    if md is None and req.report_id:
        rep = db.get("reports", req.report_id)
        if not rep:
            raise HTTPException(status_code=404, detail="report not found")
        md = rep.get("markdown", "")
        run_id = run_id or rep.get("workflow_run_id")
    if not run_id:
        # Fall back to the latest agentic run.
        runs = [r for r in db.list_records("workflow_runs", limit=50)
                if r.get("kind") in ("agentic", "agentic_replay")]
        run_id = runs[0]["id"] if runs else "none"
    return lint_run(run_id, md)


@router.get("/evidence/lint/latest")
def evidence_lint_latest():
    runs = [r for r in db.list_records("workflow_runs", limit=50)
            if r.get("kind") in ("agentic", "agentic_replay")]
    if not runs:
        raise HTTPException(status_code=404, detail="no run to lint")
    return lint_run(runs[0]["id"])


@router.get("/targets")
def list_targets(project_id: str | None = None, limit: int = 100):
    rows = db.list_records("target_candidates", project_id=project_id, limit=limit)
    rows.sort(key=lambda r: r.get("rank", 999))
    return {"targets": rows, "count": len(rows)}


@router.get("/targets/{target_id}")
def get_target(target_id: str):
    rec = db.get("target_candidates", target_id) or db.get("target_candidates", f"tgt-{target_id}")
    if not rec:
        raise HTTPException(status_code=404, detail="target not found")
    return rec


@router.get("/hypotheses")
def list_hypotheses(project_id: str | None = None, limit: int = 100):
    return {"hypotheses": db.list_records("hypotheses", project_id=project_id, limit=limit)}


@router.get("/hypotheses/{hyp_id}")
def get_hypothesis(hyp_id: str):
    rec = db.get("hypotheses", hyp_id)
    if not rec:
        raise HTTPException(status_code=404, detail="hypothesis not found")
    return rec


@router.get("/evidence")
def list_evidence(project_id: str | None = None, limit: int = 200):
    return {"evidence": db.list_records("evidence_items", project_id=project_id, limit=limit)}


@router.get("/evidence/{evidence_id}")
def get_evidence(evidence_id: str):
    rec = db.get("evidence_items", evidence_id)
    if not rec:
        raise HTTPException(status_code=404, detail="evidence not found")
    return rec


@router.post("/evidence/verify")
def verify_evidence(req: EvidenceVerifyRequest):
    status, reason = verify_identifier(req.source_name, req.identifier_type, req.identifier, req.url)
    return {"verification_status": status, "verification_reason": reason,
            "identifier": req.identifier, "source_name": req.source_name}


@router.get("/molecules")
def list_molecules(project_id: str | None = None, limit: int = 200):
    rows = db.list_records("molecule_candidates", project_id=project_id, limit=limit)
    rows.sort(key=lambda r: r.get("rank", 999))
    return {"molecules": rows, "count": len(rows)}
