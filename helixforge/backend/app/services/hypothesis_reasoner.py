"""Evidence-grounded hybrid hypothesis reasoner.

Asks the LLM (when enabled) for conservative, testable hypotheses grounded ONLY in
the provided evidence IDs, then validates deterministically: every cited evidence
ID must exist, no failed citation may be used, every statement must pass the
scientific language lint (with one safe-rewrite attempt), and each hypothesis is
evidence-graded. Falls back to the deterministic template on any failure. An LLM
never supplies scientific facts — only reasoning over provided evidence.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.llm import call_llm
from app.llm.schemas import LLMCallPurpose
from app.models.schemas import utcnow
from app.services import evidence_grading
from app.services.scientific_language_linter import check as lang_check
from app.storage import db


def _run_and_evidence(run_id: Optional[str]):
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    if run_id and not run:
        raise ValueError("workflow run not found")
    pid = run.get("project_id") if run else None
    rid = run.get("id") if run else None
    ev = (db.list_records("evidence_items", project_id=pid, workflow_run_id=rid, limit=500)
          if pid and rid else [])
    return run, pid, ev


def _evidence_digest(ev: list[dict], limit: int = 12) -> tuple[str, set[str], set[str]]:
    """Compact evidence summaries + the set of valid (non-failed) IDs."""
    lines = []
    all_ids: set[str] = set()
    verified_ids: set[str] = set()
    for e in ev[:limit]:
        eid = e.get("id")
        all_ids.add(eid)
        vs = (e.get("verification_status") or "").upper()
        if vs not in ("FAILED", "UNRESOLVED", "UNVERIFIED", "NOT_FOUND"):
            verified_ids.add(eid)
        title = (e.get("title") or e.get("claim") or "")[:100]
        direction = e.get("evidence_direction") or "support"
        lines.append(f"- {eid} [{e.get('source_name','?')}, {vs or 'UNKNOWN'}, {direction}]: {title}")
    return "\n".join(lines), all_ids, verified_ids


def _deterministic_hypotheses(run, tname, condition, verified_ids: set[str]) -> dict[str, Any]:
    ids = list(verified_ids)[:4]
    return {
        "hypotheses": [
            {"hypothesis_id": "H1",
             "statement": f"An {tname}-directed small molecule is an in-silico hypothesis for expert review in {condition}, supported by public-data signals.",
             "mechanism_summary": f"Modulation of {tname} activity.", "target": tname, "disease_context": condition,
             "supporting_evidence_ids": ids, "contradictory_evidence_ids": [],
             "assumptions": ["In-silico hypothesis only; no wet-lab/clinical validation."],
             "uncertainty_reasons": ["deterministic template; limited reasoning"], "evidence_grade": "C",
             "confidence": 0.6, "next_validation_needs": ["orthogonal target validation"],
             "safety_notes": [], "language_risk": "PASS"},
        ],
        "overall_summary": f"Deterministic template hypothesis for {tname}.",
        "limitations": ["Template output; requires expert review."], "claims_to_avoid": ["cure", "proven"],
    }


def _sanitize_hypothesis(h: dict, all_ids: set[str], verified_ids: set[str],
                         run_id, project_id, client) -> tuple[Optional[dict], list[str]]:
    """Validate one hypothesis: real evidence IDs, no failed citations, language-safe."""
    notes: list[str] = []
    # 1) evidence IDs must exist AND be verified.
    sup = [i for i in (h.get("supporting_evidence_ids") or []) if i in all_ids]
    dropped_fake = [i for i in (h.get("supporting_evidence_ids") or []) if i not in all_ids]
    if dropped_fake:
        notes.append(f"dropped non-existent evidence IDs: {dropped_fake}")
    failed_used = [i for i in sup if i not in verified_ids]
    sup = [i for i in sup if i in verified_ids]
    if failed_used:
        notes.append(f"removed failed/unverified citations: {failed_used}")
    h["supporting_evidence_ids"] = sup

    # 2) language lint; one safe-rewrite attempt on block.
    statement = h.get("statement", "")
    lint = lang_check(statement)
    if lint["status"] == "BLOCKED":
        rw = call_llm(purpose=LLMCallPurpose.SAFE_REWRITE, prompt_template_id="safe_rewrite",
                      user_prompt=f"Rewrite conservatively: {statement}", required_keys=["rewritten"],
                      run_id=run_id, project_id=project_id, client=client)
        if rw.ok and rw.data and lang_check(rw.data["rewritten"])["status"] != "BLOCKED":
            h["statement"] = rw.data["rewritten"]
            notes.append("statement safe-rewritten (was BLOCKED)")
        else:
            notes.append("statement dropped: overclaim could not be safely rewritten")
            return None, notes
    elif lint["status"] == "REVIEW_REQUIRED":
        h["language_risk"] = "REVIEW_REQUIRED"

    # 3) evidence grade (deterministic).
    claim = {"claim_text": h["statement"], "claim_type": evidence_grading.ClaimType.DISEASE_TARGET_ASSOCIATION,
             "linked_evidence_ids": sup}
    ev_records = db.list_records(
        "evidence_items", project_id=project_id, workflow_run_id=run_id, limit=500
    )
    graded = evidence_grading.grade_claim(claim, ev_records)
    h["evidence_grade"] = graded["evidence_grade"].split("_")[0]  # A/B/.. letter
    h["deterministic_grade"] = graded["evidence_grade"]
    h["confidence"] = min(float(h.get("confidence", 0.6)), graded["confidence"] + 0.1)
    return h, notes


def generate_hybrid(run_id: Optional[str] = None, mode: Optional[str] = None,
                    client: Any = None) -> dict[str, Any]:
    run, pid, ev = _run_and_evidence(run_id)
    rid = run.get("id") if run else run_id
    tname = (run.get("target_query") if run else None) or "EGFR"
    condition = (run.get("condition") if run else None) or "non-small cell lung cancer"
    digest, all_ids, verified_ids = _evidence_digest(ev)

    user_prompt = (
        f"Target: {tname}\nDisease context: {condition}\n"
        f"Available evidence (use ONLY these IDs):\n{digest or '(no evidence retrieved)'}\n"
        f"Verified evidence IDs: {sorted(verified_ids) or 'none'}\n"
        "Generate 2-4 conservative, testable, high-level hypotheses per the schema. "
        "supporting_evidence_ids must be a subset of the verified IDs above."
    )
    res = call_llm(purpose=LLMCallPurpose.HYPOTHESIS_REASONING, prompt_template_id="hypothesis_reasoner",
                   user_prompt=user_prompt, required_keys=["hypotheses", "overall_summary"],
                   list_keys=["hypotheses"], mode=mode, run_id=rid, project_id=pid, client=client)

    source = res.reasoning_source_type
    validation_notes: list[str] = []
    rejected = 0
    if res.ok and res.data and res.data.get("hypotheses"):
        cleaned = []
        for h in res.data["hypotheses"]:
            sane, notes = _sanitize_hypothesis(dict(h), all_ids, verified_ids, rid, pid, client)
            validation_notes.extend(notes)
            if sane is not None:
                cleaned.append(sane)
            else:
                rejected += 1
        if cleaned:
            data = {"hypotheses": cleaned, "overall_summary": res.data.get("overall_summary", ""),
                    "limitations": res.data.get("limitations", []),
                    "claims_to_avoid": res.data.get("claims_to_avoid", [])}
        else:
            data = _deterministic_hypotheses(run, tname, condition, verified_ids)
            source = "DETERMINISTIC_FALLBACK"
            validation_notes.append("all LLM hypotheses rejected; used deterministic template")
    else:
        data = _deterministic_hypotheses(run, tname, condition, verified_ids)
        if source == "REAL_LLM_OUTPUT":
            source = "DETERMINISTIC_FALLBACK"

    # Persist hypotheses into the shared table (flagged hybrid).
    stored = []
    for i, h in enumerate(data["hypotheses"]):
        rec = {
            "id": f"hyp-{rid}-hybrid-{i+1}", "project_id": pid, "created_at": utcnow(),
            "workflow_run_id": rid, "target_symbol": h.get("target", tname),
            "target_id": (run.get("id") if run else None), "statement": h["statement"],
            "mechanism_summary": h.get("mechanism_summary", ""),
            "evidence_ids": h.get("supporting_evidence_ids", []),
            "confidence": h.get("confidence", 0.6),
            "assumptions": h.get("assumptions", []), "limitations": "; ".join(data.get("limitations", [])),
            "critic_status": "pending", "overclaim": False, "status": "draft",
            "reasoning_source_type": source, "evidence_grade": h.get("evidence_grade"),
            "language_risk": h.get("language_risk", "PASS"),
            "next_validation_needs": h.get("next_validation_needs", []),
            "hybrid": True,
        }
        db.insert("hypotheses", rec)
        stored.append(rec)

    return {
        "run_id": rid, "target": tname, "condition": condition,
        "reasoning_source_type": source, "model": res.model, "llm_call_id": res.llm_call_id,
        "fallback_used": res.fallback_used, "fallback_reason": res.fallback_reason,
        "input_evidence_count": len(ev), "verified_evidence_ids": sorted(verified_ids),
        "hypotheses": stored, "hypothesis_count": len(stored),
        "rejected_or_rewritten": rejected, "validation_notes": validation_notes,
        "overall_summary": data.get("overall_summary", ""), "limitations": data.get("limitations", []),
        "disclaimer": ("LLM-assisted, evidence-grounded hypotheses. Not a clinical claim; "
                       "in-silico only; requires experimental validation. / 임상적 주장이 아님, 전문가 검토 필요."),
        "checked_at": utcnow(),
    }


def get_hybrid(run_id: str) -> dict[str, Any]:
    hyps = [h for h in db.list_records("hypotheses", workflow_run_id=run_id, limit=1000)
            if h.get("hybrid")]
    return {"run_id": run_id, "hypotheses": hyps, "count": len(hyps)}
