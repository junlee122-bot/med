from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.agents.citation_verifier_agent import verify_identifier
from app.models.agent_schemas import EvidenceVerifyRequest
from app.storage import db

router = APIRouter(prefix="/api", tags=["data"])


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
