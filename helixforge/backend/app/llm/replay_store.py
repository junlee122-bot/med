"""Persistence + lookup for LLM calls (the `llm_calls` table), and recorded-output
lookup for RECORDED_HYBRID_REPLAY mode. Never stores secrets or full prompts
(unless HELIXFORGE_LLM_STORE_FULL_PROMPTS is set, and then redacted)."""
from __future__ import annotations

import hashlib
import hmac
from typing import Any, Optional

from app.llm.config import get_llm_config
from app.llm.schemas import LLMResult, ReasoningSourceType
from app.services.provenance import redact_secrets
from app.storage import db


# The generic ledger is metadata-only. Prompt/output summaries and replay
# payloads can contain user or model text and are exposed only by the guarded
# recorded-output endpoint.
LEDGER_METADATA_FIELDS = (
    "id", "llm_call_id", "run_id", "project_id", "agent_run_id", "created_at",
    "provider", "model", "purpose", "reasoning_source_type",
    "prompt_template_id", "prompt_template_hash", "input_hash", "output_hash",
    "temperature", "effort", "max_output_tokens", "tokens_in", "tokens_out",
    "estimated_cost_usd", "actual_cost_usd", "cache_hit", "budget_status",
    "fallback_used", "fallback_reason", "schema_validation_status", "safety_status",
)


def _hash_output(text: str) -> str:
    """Match the LLM adapter's persisted output digest format."""
    return "sha256:" + hashlib.sha256((text or "").encode()).hexdigest()[:16]


def is_valid_recorded_output(call: dict[str, Any]) -> bool:
    """Fail closed unless a call is an intact, replayable LLM output."""
    if call.get("reasoning_source_type") not in (
        ReasoningSourceType.REAL_LLM_OUTPUT,
        ReasoningSourceType.RECORDED_LLM_OUTPUT,
    ):
        return False
    if not isinstance(call.get("data"), dict):
        return False
    text = call.get("text")
    expected = call.get("output_hash")
    if not isinstance(text, str) or not text or not isinstance(expected, str) or not expected:
        return False
    return hmac.compare_digest(expected, _hash_output(text))


def persist_call(result: LLMResult, run_id: Optional[str], project_id: Optional[str],
                 agent_run_id: Optional[str], full_system_prompt: str = "",
                 full_user_prompt: str = "") -> dict[str, Any]:
    cfg = get_llm_config()
    # Redact the complete result object, not only optional full prompts. Text,
    # parsed data, and summaries may echo a credential supplied in a prompt or
    # returned by a provider.
    redacted = redact_secrets(result.to_dict())
    rec: dict[str, Any] = dict(redacted) if isinstance(redacted, dict) else {}
    # Redaction can change the stored text. Bind the digest to the exact stored
    # representation so replay integrity checks remain meaningful.
    if rec.get("output_hash") and isinstance(rec.get("text"), str):
        rec["output_hash"] = _hash_output(rec["text"])
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
    # Replay is an exact-run operation.  Falling back to a global search when
    # the caller has no run identifier can silently reuse another project's
    # reasoning and mislabel it as belonging to this execution.
    if not run_id:
        return None
    calls = db.list_records("llm_calls", workflow_run_id=run_id, limit=2000)
    candidates = [c for c in calls
                  if c.get("purpose") == purpose and c.get("input_hash") == input_hash
                  and is_valid_recorded_output(c)]
    return candidates[0] if candidates else None


def list_calls(run_id: Optional[str] = None, limit: int = 500) -> list[dict[str, Any]]:
    return db.list_records("llm_calls", workflow_run_id=run_id, limit=limit)


def list_call_metadata(run_id: Optional[str] = None, limit: int = 500) -> list[dict[str, Any]]:
    """Return the public, content-free projection of the LLM call ledger."""
    return [
        {field: call.get(field) for field in LEDGER_METADATA_FIELDS if field in call}
        for call in list_calls(run_id, limit)
    ]


def get_call(call_id: str) -> Optional[dict[str, Any]]:
    return db.get("llm_calls", call_id)


def get_recorded_output(call_id: str) -> Optional[dict[str, Any]]:
    """Return a call only when it is safe and intact enough to replay."""
    call = get_call(call_id)
    return call if call and is_valid_recorded_output(call) else None
