"""Persistence + lookup for LLM calls (the `llm_calls` table), and recorded-output
lookup for RECORDED_HYBRID_REPLAY mode. Never stores secrets or full prompts
(unless HELIXFORGE_LLM_STORE_FULL_PROMPTS is set, and then redacted)."""
from __future__ import annotations

from typing import Any, Optional

from app.llm.config import get_llm_config
from app.llm.schemas import LLMResult, ReasoningSourceType
from app.services.provenance import redact_secrets
from app.storage import db


def persist_call(result: LLMResult, run_id: Optional[str], project_id: Optional[str],
                 agent_run_id: Optional[str], full_system_prompt: str = "",
                 full_user_prompt: str = "") -> dict[str, Any]:
    cfg = get_llm_config()
    rec: dict[str, Any] = result.to_dict()
    rec["id"] = result.llm_call_id
    rec["run_id"] = run_id
    rec["project_id"] = project_id
    rec["agent_run_id"] = agent_run_id
    # Full prompts only if explicitly enabled — and always redacted.
    if cfg.store_full_prompts:
        rec["full_system_prompt"] = redact_secrets(full_system_prompt)[:8000]
        rec["full_user_prompt"] = redact_secrets(full_user_prompt)[:8000]
    else:
        rec["full_system_prompt"] = None
        rec["full_user_prompt"] = None
    try:
        db.insert("llm_calls", rec)
    except Exception:
        pass
    return rec


def find_recorded(purpose: str, input_hash: str,
                  run_id: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Find a prior real/recorded LLM call with a matching input hash (for replay)."""
    calls = db.list_records("llm_calls", limit=2000)
    candidates = [c for c in calls
                  if c.get("purpose") == purpose and c.get("input_hash") == input_hash
                  and c.get("reasoning_source_type") in (ReasoningSourceType.REAL_LLM_OUTPUT,
                                                         ReasoningSourceType.RECORDED_LLM_OUTPUT)
                  and c.get("data") is not None]
    if run_id:
        rc = [c for c in candidates if c.get("run_id") == run_id]
        if rc:
            return rc[0]
    return candidates[0] if candidates else None


def list_calls(run_id: Optional[str] = None, limit: int = 500) -> list[dict[str, Any]]:
    calls = db.list_records("llm_calls", limit=limit)
    if run_id:
        calls = [c for c in calls if c.get("run_id") == run_id]
    return calls


def get_call(call_id: str) -> Optional[dict[str, Any]]:
    return db.get("llm_calls", call_id)
