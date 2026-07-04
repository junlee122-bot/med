"""Expert review board workflow.

Turns a run's outputs into a role-based review queue so the right specialist signs
off on the right artifact before it is used. Deterministic item generation; human
decisions are persisted. Release readiness can require expert sign-off on
high-risk items. Observable trace only — no hidden reasoning.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import utcnow
from app.storage import db


class ExpertRole:
    COMPUTATIONAL_CHEMISTRY = "COMPUTATIONAL_CHEMISTRY"
    MEDICINAL_CHEMISTRY = "MEDICINAL_CHEMISTRY"
    BIOLOGY_TARGET_EXPERT = "BIOLOGY_TARGET_EXPERT"
    CLINICAL_DEVELOPMENT = "CLINICAL_DEVELOPMENT"
    REGULATORY_AFFAIRS = "REGULATORY_AFFAIRS"
    AI_ML_REVIEWER = "AI_ML_REVIEWER"
    SAFETY_ETHICS_REVIEWER = "SAFETY_ETHICS_REVIEWER"
    BUSINESS_REVIEWER = "BUSINESS_REVIEWER"


DECISIONS = ["APPROVE_FOR_PROPOSAL", "APPROVE_FOR_DEMO_ONLY", "NEEDS_MORE_EVIDENCE",
             "REJECT", "ESCALATE", "NOT_APPLICABLE"]


def _item(run_id, item_type, item_id, title, summary, role, required_roles, risk, source_type, grade=None):
    return {
        "id": f"eri-{uuid.uuid4().hex[:8]}", "run_id": run_id, "item_type": item_type,
        "item_id": item_id, "title": title, "summary": summary,
        "recommended_role": role, "required_roles": required_roles, "risk_level": risk,
        "source_type": source_type, "evidence_grade": grade, "review_status": "PENDING",
        "reviewer_name": None, "reviewer_role": None, "reviewer_comment": None,
        "decision": None, "created_at": utcnow(), "reviewed_at": None,
    }


def generate_from_run(run_id: str | None = None) -> dict[str, Any]:
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    rid = run.get("id") if run else None
    pid = run.get("project_id") if run else None
    items: list[dict] = []

    targets = db.list_records("target_candidates", project_id=pid, limit=20) if pid else []
    if targets:
        t = targets[0]
        items.append(_item(rid, "target", t.get("id"),
                           f"Selected target: {t.get('pref_name') or t.get('target_chembl_id')}",
                           "Review target biology plausibility and druggability.",
                           ExpertRole.BIOLOGY_TARGET_EXPERT,
                           [ExpertRole.BIOLOGY_TARGET_EXPERT], "medium", t.get("source_type")))

    mols = db.list_records("molecule_candidates", project_id=pid, limit=200) if pid else []
    for m in mols[:5]:
        risk = "high" if str(m.get("safety_status")).upper() != "PASS" else "medium"
        items.append(_item(rid, "molecule", m.get("id"),
                           f"Candidate: {m.get('label') or m.get('molecule_chembl_id')}",
                           "Review medicinal-chemistry profile, alerts, and activity reliability.",
                           ExpertRole.MEDICINAL_CHEMISTRY,
                           [ExpertRole.MEDICINAL_CHEMISTRY, ExpertRole.COMPUTATIONAL_CHEMISTRY], risk,
                           m.get("source_type")))

    hyps = db.list_records("hypotheses", project_id=pid, limit=10) if pid else []
    for h in hyps[:3]:
        items.append(_item(rid, "hypothesis", h.get("id"),
                           f"Hypothesis: {(h.get('statement') or '')[:60]}",
                           "Verify evidence linkage and that phrasing matches evidence grade.",
                           ExpertRole.AI_ML_REVIEWER,
                           [ExpertRole.BIOLOGY_TARGET_EXPERT], "medium", None))

    # Standing items that always require sign-off.
    items.append(_item(rid, "clinical_strategy", "clinical", "Clinical precedent & strategy",
                       "Confirm precedent is described as precedent, not efficacy.",
                       ExpertRole.CLINICAL_DEVELOPMENT, [ExpertRole.CLINICAL_DEVELOPMENT], "high", "HEURISTIC_ANALYSIS"))
    items.append(_item(rid, "regulatory", "regulatory", "Regulatory checklist",
                       "Confirm regulatory content is high-level and not compliance advice.",
                       ExpertRole.REGULATORY_AFFAIRS, [ExpertRole.REGULATORY_AFFAIRS], "high", "HEURISTIC_ANALYSIS"))
    items.append(_item(rid, "safety", "safety", "Safety & ethics lint issues",
                       "Confirm no forbidden content, overclaims removed, disclaimers present.",
                       ExpertRole.SAFETY_ETHICS_REVIEWER, [ExpertRole.SAFETY_ETHICS_REVIEWER], "high", None))
    items.append(_item(rid, "report", "report", "Final report / submission bundle",
                       "Confirm claims are graded and language is conservative.",
                       ExpertRole.AI_ML_REVIEWER,
                       [ExpertRole.SAFETY_ETHICS_REVIEWER, ExpertRole.AI_ML_REVIEWER], "high", None))

    for it in items:
        try:
            db.insert("expert_review_items", it)
        except Exception:
            pass
    return {"run_id": rid, "items": items, "count": len(items),
            "by_role": _by_role(items), "checked_at": utcnow()}


def _by_role(items: list[dict]) -> dict[str, int]:
    out: dict[str, int] = {}
    for it in items:
        out[it["recommended_role"]] = out.get(it["recommended_role"], 0) + 1
    return out


def list_items(role: str | None = None, status: str | None = None) -> dict[str, Any]:
    items = db.list_records("expert_review_items", limit=1000)
    if role:
        items = [i for i in items if i.get("recommended_role") == role or role in (i.get("required_roles") or [])]
    if status:
        items = [i for i in items if i.get("review_status") == status]
    return {"items": items, "count": len(items), "roles": sorted({i["recommended_role"] for i in items})}


def record_decision(item_id: str, decision: str, reviewer_name: str = "", reviewer_role: str = "",
                    comment: str = "") -> dict[str, Any]:
    it = db.get("expert_review_items", item_id)
    if not it:
        return {"error": "item not found"}
    if decision not in DECISIONS:
        return {"error": f"decision must be one of {DECISIONS}"}
    it["decision"] = decision
    it["review_status"] = "REVIEWED"
    it["reviewer_name"] = reviewer_name
    it["reviewer_role"] = reviewer_role
    it["reviewer_comment"] = comment
    it["reviewed_at"] = utcnow()
    db.insert("expert_review_items", it)
    return it


def summary_for_run(run_id: str) -> dict[str, Any]:
    items = [i for i in db.list_records("expert_review_items", limit=1000) if i.get("run_id") == run_id]
    high_risk = [i for i in items if i.get("risk_level") == "high"]
    pending_high = [i for i in high_risk if i.get("review_status") == "PENDING"]
    reviewed = [i for i in items if i.get("review_status") == "REVIEWED"]
    rejected = [i for i in reviewed if i.get("decision") == "REJECT"]
    return {
        "run_id": run_id, "total": len(items), "reviewed": len(reviewed),
        "pending": len(items) - len(reviewed), "high_risk": len(high_risk),
        "pending_high_risk": len(pending_high), "rejected": len(rejected),
        "all_high_risk_signed_off": len(pending_high) == 0 and len(high_risk) > 0,
        "blocks_final_ready": len(pending_high) > 0 or len(rejected) > 0,
        "checked_at": utcnow(),
    }
