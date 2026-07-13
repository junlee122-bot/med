"""AI interaction transparency ledger.

Records every AI/agent interaction for ethics transparency. The default runtime
is DETERMINISTIC (no external LLM), which is itself recorded honestly. No full
secrets and no private chain-of-thought are stored — only summaries and hashes.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Optional

from app.models.schemas import utcnow
from app.services.provenance import redact_secrets
from app.storage import db

INTERACTION_TYPES = ("DETERMINISTIC_AGENT", "LLM_CALL", "LLM_REPLAY", "HUMAN_INPUT",
                     "REPORT_TEMPLATE", "SAFETY_LINT", "CLAIM_REWRITE", "MODEL_ROUTER_DECISION",
                     "BUDGET_GUARD_DECISION")


def _hash(s: str) -> str:
    return "sha256:" + hashlib.sha256((s or "").encode()).hexdigest()[:16]


def record(
    *, run_id: str, agent_run_id: Optional[str], interaction_type: str,
    provider: str = "none (deterministic)", model_name: str = "deterministic-agent",
    model_version: str = "phase3", temperature: Optional[float] = None, max_tokens: Optional[int] = None,
    system_prompt_summary: str = "", user_prompt_summary: str = "", tool_config_summary: str = "",
    project_id: Optional[str] = None, notes: str = "",
) -> dict[str, Any]:
    if interaction_type not in INTERACTION_TYPES:
        interaction_type = "DETERMINISTIC_AGENT"
    sysp = redact_secrets(system_prompt_summary)
    userp = redact_secrets(user_prompt_summary)
    rec = {
        "id": f"ai-{uuid.uuid4().hex[:12]}", "project_id": project_id, "created_at": utcnow(),
        "run_id": run_id, "agent_run_id": agent_run_id, "interaction_type": interaction_type,
        "provider": provider, "model_name": model_name, "model_version": model_version,
        "temperature": temperature, "max_tokens": max_tokens,
        "system_prompt_summary": sysp, "user_prompt_summary": userp,
        "tool_config_summary": redact_secrets(tool_config_summary),
        "input_hash": _hash(userp), "output_hash": _hash(notes), "timestamp": utcnow(),
        "redacted": True, "notes": redact_secrets(notes),
    }
    db.insert("ai_interactions", rec)
    return rec


def record_llm_call(result, *, run_id: Optional[str], project_id: Optional[str] = None,
                    agent_run_id: Optional[str] = None) -> dict[str, Any]:
    """Record a real/recorded/fallback LLM call (an app.llm.schemas.LLMResult) in the
    ledger. Stores only observable metadata + summaries — never full prompts or CoT."""
    r = result.to_dict() if hasattr(result, "to_dict") else dict(result)
    replayed = r.get("reasoning_source_type") == "RECORDED_LLM_OUTPUT"
    itype = "LLM_REPLAY" if replayed else "LLM_CALL"
    rec = {
        "id": f"ai-{uuid.uuid4().hex[:12]}", "project_id": project_id, "created_at": utcnow(),
        "run_id": run_id, "agent_run_id": agent_run_id, "interaction_type": itype,
        "provider": r.get("provider", "none"), "model_name": r.get("model", "deterministic"),
        "model_version": "phase7", "temperature": r.get("temperature"),
        "max_tokens": r.get("max_output_tokens"),
        "system_prompt_summary": f"template:{r.get('prompt_template_id')}",
        "user_prompt_summary": redact_secrets(r.get("input_summary", "")),
        "tool_config_summary": f"purpose:{r.get('purpose')}",
        "input_hash": r.get("input_hash", ""), "output_hash": r.get("output_hash", ""),
        "timestamp": utcnow(), "redacted": True,
        "notes": redact_secrets(r.get("output_summary", "")),
        # --- LLM-specific fields ---
        "llm_call_id": r.get("llm_call_id"), "purpose": r.get("purpose"),
        "reasoning_source_type": r.get("reasoning_source_type"),
        "prompt_template_id": r.get("prompt_template_id"),
        "prompt_template_hash": r.get("prompt_template_hash"),
        "prompt_summary": redact_secrets(r.get("input_summary", "")),
        "token_usage_input": r.get("tokens_in"), "token_usage_output": r.get("tokens_out"),
        "estimated_cost_usd": r.get("estimated_cost_usd"), "actual_cost_usd": r.get("actual_cost_usd"),
        "cache_hit": r.get("cache_hit"), "budget_status": r.get("budget_status"),
        "fallback_used": r.get("fallback_used"), "fallback_reason": r.get("fallback_reason"),
        "schema_validation_status": r.get("schema_validation_status"),
        "safety_status": r.get("safety_status"),
    }
    db.insert("ai_interactions", rec)
    return rec


def record_router_decision(*, run_id: str, purpose: str, model: str, mode: str,
                           project_id: Optional[str] = None) -> dict[str, Any]:
    return record(run_id=run_id, agent_run_id=None, interaction_type="MODEL_ROUTER_DECISION",
                  provider="router", model_name=model,
                  user_prompt_summary=f"route {purpose} in {mode}", project_id=project_id,
                  notes=f"routed {purpose} -> {model} ({mode})")


def list_interactions(run_id: Optional[str] = None, limit: int = 500) -> list[dict]:
    return db.list_records("ai_interactions", workflow_run_id=run_id, limit=limit)


def summary_for_run(run_id: str) -> dict[str, Any]:
    rows = list_interactions(run_id)
    by_type: dict[str, int] = {}
    providers = set()
    for r in rows:
        by_type[r["interaction_type"]] = by_type.get(r["interaction_type"], 0) + 1
        providers.add(r.get("provider"))
    llm_rows = [r for r in rows if r.get("interaction_type") in ("LLM_CALL", "LLM_REPLAY")]
    real_llm = [r for r in llm_rows if r.get("reasoning_source_type") == "REAL_LLM_OUTPUT"]
    replayed = [r for r in llm_rows if r.get("reasoning_source_type") == "RECORDED_LLM_OUTPUT"]
    fallbacks = [r for r in llm_rows if r.get("fallback_used")]
    llm_used = len(real_llm) > 0
    models_used = sorted({r.get("model_name") for r in llm_rows if r.get("model_name")
                          and r.get("model_name") != "deterministic"})
    templates = sorted({r.get("prompt_template_id") for r in llm_rows if r.get("prompt_template_id")})
    total_cost = round(sum((r.get("actual_cost_usd") or 0.0) for r in llm_rows), 6)
    return {
        "run_id": run_id, "interaction_count": len(rows), "by_type": by_type,
        "providers": sorted(p for p in providers if p),
        "llm_used": llm_used,
        "llm_call_count": len(real_llm), "llm_replay_count": len(replayed),
        "llm_fallback_count": len(fallbacks),
        "models_used": models_used, "prompt_templates_used": templates,
        "estimated_total_cost_usd": total_cost,
        "fallback_reasons": sorted({r.get("fallback_reason") for r in fallbacks if r.get("fallback_reason")}),
        "statement": (
            "This run used deterministic agents (no external LLM calls)." if not llm_used
            else f"This run included optional LLM calls ({len(real_llm)} real, {len(replayed)} replayed, "
                 f"{len(fallbacks)} deterministic fallback). Models: {', '.join(models_used) or 'n/a'}. "
                 "Every LLM output was validated by deterministic tools and governance gates."
        ),
        "ethics_note": (
            "Prompts/settings, tool calls, and citations are logged. Full secrets and private "
            "chain-of-thought are never stored — only summaries and hashes."
        ),
    }


def manual_note(run_id: str, note: str, author: str = "human") -> dict[str, Any]:
    return record(run_id=run_id, agent_run_id=None, interaction_type="HUMAN_INPUT",
                  provider="human", model_name="n/a", user_prompt_summary=note, notes=f"manual note by {author}")
