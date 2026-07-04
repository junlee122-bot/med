"""Semantic critic (Fable-assisted).

Layers an LLM semantic review on top of the existing rule-based critic to catch
subtle overclaim / evidence-gap / source-confusion / clinical-overreach issues.
Every accepted critique item is validated deterministically (cited IDs exist, no
chain-of-thought markers, no unsafe content, safe rewrites pass the language lint)
and converted into a RevisionEvent. Falls back to a deterministic critique summary
when the LLM is unavailable. The critic never invents scientific facts.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.llm import call_llm
from app.llm.safety import contains_chain_of_thought
from app.llm.schemas import LLMCallPurpose
from app.models.schemas import utcnow
from app.services.scientific_language_linter import check as lang_check
from app.storage import db

_VALID_SEVERITY = {"INFO", "WARNING", "REVIEW_REQUIRED", "BLOCKING"}
_VALID_CATEGORY = {"EVIDENCE_GAP", "OVERCLAIM", "CONTRADICTION", "SOURCE_CONFUSION", "SAFETY",
                   "CLINICAL_OVERREACH", "REGULATORY_OVERREACH", "MOLECULE_QUALITY",
                   "MISSING_LIMITATION", "OTHER"}


def _gather_context(run_id: str) -> dict[str, Any]:
    run = db.get("workflow_runs", run_id) or {}
    pid = run.get("project_id")
    hyps = [h for h in db.list_records("hypotheses", project_id=pid, limit=200)
            if h.get("workflow_run_id") == run_id]
    mols = db.list_records("molecule_candidates", project_id=pid, limit=200) if pid else []
    ev = db.list_records("evidence_items", project_id=pid, limit=200) if pid else []
    entity_ids = ({h.get("id") for h in hyps} | {m.get("id") for m in mols} | {e.get("id") for e in ev})
    return {"run": run, "pid": pid, "hyps": hyps, "mols": mols, "ev": ev, "entity_ids": entity_ids}


def _context_digest(ctx: dict) -> str:
    lines = ["HYPOTHESES:"]
    for h in ctx["hyps"][:6]:
        lines.append(f"- {h.get('id')}: {(h.get('statement') or '')[:120]} [grade {h.get('evidence_grade','?')}]")
    lines.append("MOLECULES (top):")
    for m in ctx["mols"][:6]:
        lines.append(f"- {m.get('id')}: {m.get('label') or m.get('molecule_chembl_id')} "
                     f"score={m.get('composite_score')} safety={m.get('safety_status')}")
    lines.append(f"EVIDENCE COUNT: {len(ctx['ev'])}")
    return "\n".join(lines)


def _deterministic_critique(ctx: dict) -> dict[str, Any]:
    """A conservative deterministic critique when the LLM is unavailable."""
    items = []
    for h in ctx["hyps"]:
        if h.get("language_risk") == "REVIEW_REQUIRED" or (h.get("evidence_grade") in ("D", "E", "F")):
            items.append({"id": f"C{len(items)+1}", "severity": "REVIEW_REQUIRED",
                          "category": "EVIDENCE_GAP", "affected_entity_type": "hypothesis",
                          "affected_entity_id": h.get("id"),
                          "issue_summary": "Low evidence grade or review-required language.",
                          "supporting_evidence_ids": h.get("evidence_ids", []),
                          "reasoning_summary": "Deterministic check: weak grade / cautious-language flag.",
                          "recommended_fix": "Expert review of evidence linkage.",
                          "safe_rewrite": "", "requires_human_review": True})
    for m in ctx["mols"]:
        if str(m.get("safety_status")).upper() not in ("PASS", "NONE", ""):
            items.append({"id": f"C{len(items)+1}", "severity": "REVIEW_REQUIRED",
                          "category": "MOLECULE_QUALITY", "affected_entity_type": "molecule",
                          "affected_entity_id": m.get("id"),
                          "issue_summary": f"Molecule safety status is {m.get('safety_status')}.",
                          "supporting_evidence_ids": [], "reasoning_summary": "Deterministic safety-status check.",
                          "recommended_fix": "Do not advance without review.", "safe_rewrite": "",
                          "requires_human_review": True})
    risk = "REVIEW_REQUIRED" if items else "PASS"
    return {"critique_items": items, "overall_risk": risk,
            "must_fix_before_submission": [i["id"] for i in items if i["severity"] == "BLOCKING"],
            "safe_summary": f"Deterministic critique: {len(items)} item(s) flagged for review."}


def _validate_item(item: dict, entity_ids: set[str]) -> tuple[Optional[dict], str]:
    """Validate one critique item; reject unsafe/CoT-leaking/invalid-id items."""
    sev = item.get("severity")
    cat = item.get("category")
    if sev not in _VALID_SEVERITY:
        item["severity"] = "REVIEW_REQUIRED"
    if cat not in _VALID_CATEGORY:
        item["category"] = "OTHER"
    # Chain-of-thought must never leak.
    blob = f"{item.get('issue_summary','')} {item.get('reasoning_summary','')} {item.get('recommended_fix','')}"
    if contains_chain_of_thought(blob):
        return None, "rejected: chain-of-thought marker in critique"
    # Cited evidence IDs must exist (drop unknown ones).
    sup = [i for i in (item.get("supporting_evidence_ids") or []) if i in entity_ids]
    item["supporting_evidence_ids"] = sup
    # Safe rewrite must itself be safe.
    sr = item.get("safe_rewrite") or ""
    if sr and lang_check(sr)["status"] == "BLOCKED":
        item["safe_rewrite"] = ""
        item["safe_rewrite_note"] = "proposed rewrite failed language lint; removed"
    # The whole item text must not carry forbidden content.
    if lang_check(blob)["status"] == "BLOCKED":
        return None, "rejected: critique text failed safety lint"
    return item, "ok"


def run_semantic_critic(run_id: str, mode: Optional[str] = None, client: Any = None) -> dict[str, Any]:
    ctx = _gather_context(run_id)
    pid = ctx["pid"]
    user_prompt = ("Review this in-silico drug-discovery run for subtle problems. Cite entity/evidence "
                   "IDs. Do not invent facts.\n" + _context_digest(ctx) +
                   "\nProduce the critique JSON per the schema.")
    res = call_llm(purpose=LLMCallPurpose.SEMANTIC_CRITIQUE, prompt_template_id="semantic_critic",
                   user_prompt=user_prompt, required_keys=["critique_items", "overall_risk"],
                   list_keys=["critique_items"], mode=mode, run_id=run_id, project_id=pid, client=client)

    source = res.reasoning_source_type
    rejected = 0
    if res.ok and res.data:
        items = []
        for it in res.data.get("critique_items", []):
            valid, _why = _validate_item(dict(it), ctx["entity_ids"])
            if valid is not None:
                items.append(valid)
            else:
                rejected += 1
        data = {"critique_items": items, "overall_risk": res.data.get("overall_risk", "REVIEW_REQUIRED"),
                "must_fix_before_submission": res.data.get("must_fix_before_submission", []),
                "safe_summary": res.data.get("safe_summary", "")}
        if not items:
            data = _deterministic_critique(ctx)
            source = "DETERMINISTIC_FALLBACK"
    else:
        data = _deterministic_critique(ctx)
        if source == "REAL_LLM_OUTPUT":
            source = "DETERMINISTIC_FALLBACK"

    # Convert accepted items into RevisionEvents (existing table).
    revision_ids = []
    for it in data["critique_items"]:
        rev = {"id": f"rev-sem-{uuid.uuid4().hex[:8]}", "project_id": pid, "workflow_run_id": run_id,
               "created_at": utcnow(), "reason_category": it.get("category", "OTHER").lower(),
               "issue_summary": it.get("issue_summary", ""),
               "action_taken": it.get("recommended_fix", ""),
               "before_summary": "", "after_summary": it.get("safe_rewrite", ""),
               "confidence_delta": 0.0, "source": "semantic_critic", "severity": it.get("severity")}
        try:
            db.insert("revision_events", rev)
            revision_ids.append(rev["id"])
        except Exception:
            pass

    payload = {
        "id": f"critique-{uuid.uuid4().hex[:10]}", "run_id": run_id, "project_id": pid,
        "created_at": utcnow(), "reasoning_source_type": source, "model": res.model,
        "llm_call_id": res.llm_call_id, "fallback_used": res.fallback_used,
        "critique_items": data["critique_items"], "critique_count": len(data["critique_items"]),
        "overall_risk": data["overall_risk"],
        "must_fix_before_submission": data.get("must_fix_before_submission", []),
        "safe_summary": data.get("safe_summary", ""), "rejected_items": rejected,
        "revision_event_ids": revision_ids,
        "disclaimer": "LLM-assisted critique; validated deterministically. No hidden chain-of-thought stored.",
    }
    try:
        db.insert("semantic_critiques", payload)
    except Exception:
        pass
    return payload


def get_semantic_critic(run_id: str) -> Optional[dict]:
    rows = [c for c in db.list_records("semantic_critiques", limit=200) if c.get("run_id") == run_id]
    return rows[0] if rows else None
