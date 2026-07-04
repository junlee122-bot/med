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

INTERACTION_TYPES = ("DETERMINISTIC_AGENT", "LLM_CALL", "HUMAN_INPUT", "REPORT_TEMPLATE", "SAFETY_LINT")


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


def list_interactions(run_id: Optional[str] = None, limit: int = 500) -> list[dict]:
    rows = db.list_records("ai_interactions", limit=limit)
    if run_id:
        rows = [r for r in rows if r.get("run_id") == run_id]
    return rows


def summary_for_run(run_id: str) -> dict[str, Any]:
    rows = list_interactions(run_id)
    by_type: dict[str, int] = {}
    providers = set()
    for r in rows:
        by_type[r["interaction_type"]] = by_type.get(r["interaction_type"], 0) + 1
        providers.add(r.get("provider"))
    llm_used = by_type.get("LLM_CALL", 0) > 0
    return {
        "run_id": run_id, "interaction_count": len(rows), "by_type": by_type,
        "providers": sorted(p for p in providers if p),
        "llm_used": llm_used,
        "statement": (
            "This run used deterministic agents (no external LLM calls)." if not llm_used
            else "This run included optional LLM calls; provider/model/settings are logged."
        ),
        "ethics_note": (
            "Prompts/settings, tool calls, and citations are logged. Full secrets and private "
            "chain-of-thought are never stored — only summaries and hashes."
        ),
    }


def manual_note(run_id: str, note: str, author: str = "human") -> dict[str, Any]:
    return record(run_id=run_id, agent_run_id=None, interaction_type="HUMAN_INPUT",
                  provider="human", model_name="n/a", user_prompt_summary=note, notes=f"manual note by {author}")
