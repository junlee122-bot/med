"""Hybrid run snapshot + replay.

Extends record/replay to capture LLM reasoning metadata alongside deterministic
tool outputs. Never stores API keys, secrets, unsafe content, hidden
chain-of-thought, or full prompts (unless explicitly enabled and redacted). On
replay there are NO live API calls: recorded LLM outputs are served labeled
RECORDED_LLM_OUTPUT and deterministic-fallback stages stay labeled as such.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from app.llm import model_router
from app.models.schemas import utcnow
from app.services import snapshots
from app.services.provenance import redact_secrets
from app.storage import db

# Fields from a persisted llm_call that are safe to store in a snapshot.
_SAFE_LLM_FIELDS = ["llm_call_id", "model", "provider", "purpose", "reasoning_source_type",
                    "prompt_template_id", "prompt_template_hash", "input_hash", "output_hash",
                    "input_summary", "output_summary", "tokens_in", "tokens_out",
                    "estimated_cost_usd", "actual_cost_usd", "cache_hit", "budget_status",
                    "fallback_used", "fallback_reason", "schema_validation_status", "safety_status",
                    "data"]


def _safe_llm_call(call: dict) -> dict:
    out = {k: call.get(k) for k in _SAFE_LLM_FIELDS}
    # data may contain reasoning JSON — keep it but redact defensively, never prompts/keys.
    if out.get("data") is not None:
        try:
            out["data"] = json.loads(redact_secrets(json.dumps(out["data"])))
        except Exception:
            out["data"] = None
    out["output_summary"] = redact_secrets(out.get("output_summary") or "")
    out["input_summary"] = redact_secrets(out.get("input_summary") or "")
    return out


def create_hybrid_snapshot(run_id: str, name: str = "", description: str = "") -> dict[str, Any]:
    """Create a base snapshot (deterministic tool data) + attach LLM metadata."""
    base = snapshots.create_snapshot_from_run(run_id, name or f"hybrid {run_id}",
                                              description or "Hybrid Fable run snapshot", created_by="hybrid")
    snap_id = base["id"]
    llm_calls = [c for c in db.list_records("llm_calls", limit=1000) if c.get("run_id") == run_id]
    safe_calls = [_safe_llm_call(c) for c in llm_calls]
    cost = model_router.cost_ledger(run_id)
    real = sum(1 for c in safe_calls if c["reasoning_source_type"] == "REAL_LLM_OUTPUT")
    fallback = sum(1 for c in safe_calls if c["fallback_used"])
    models = sorted({c["model"] for c in safe_calls if c.get("model") and c["model"] != "deterministic"})

    hybrid_meta = {
        "id": f"hybmeta-{uuid.uuid4().hex[:10]}", "snapshot_id": snap_id, "run_id": run_id,
        "created_at": utcnow(), "is_hybrid": True, "llm_calls": safe_calls, "llm_call_count": len(safe_calls),
        "real_llm_output_count": real, "deterministic_fallback_count": fallback,
        "models_used": models, "cost_summary": cost,
        "labels": {"tool_data": "RECORDED_REAL_TOOL_OUTPUT", "llm_reasoning": "RECORDED_LLM_OUTPUT",
                   "fallback": "DETERMINISTIC_FALLBACK"},
        "note": "No secrets, keys, full prompts, or chain-of-thought stored. Replay uses no live API calls.",
    }
    try:
        db.insert("snapshot_artifacts", hybrid_meta)
    except Exception:
        pass
    base["hybrid_meta"] = hybrid_meta
    base["is_hybrid"] = True
    return base


def _hybrid_meta(snapshot_id: str) -> Optional[dict]:
    rows = [r for r in db.list_records("snapshot_artifacts", limit=1000)
            if r.get("snapshot_id") == snapshot_id and r.get("is_hybrid")]
    return rows[0] if rows else None


def replay_hybrid(snapshot_id: str) -> dict[str, Any]:
    """Replay a hybrid snapshot: deterministic data via the base replay, LLM outputs
    served as RECORDED_LLM_OUTPUT. NO live API calls."""
    base = snapshots.replay_snapshot(snapshot_id)
    meta = _hybrid_meta(snapshot_id)
    llm = meta.get("llm_calls", []) if meta else []
    return {
        "snapshot_id": snapshot_id, "replayed_at": utcnow(),
        "tool_data_replay": {"source_type": "RECORDED_REAL_TOOL_OUTPUT",
                             "note": base.get("note", "deterministic tool outputs replayed")},
        "llm_reasoning_replay": [{"llm_call_id": c.get("llm_call_id"), "model": c.get("model"),
                                  "purpose": c.get("purpose"),
                                  "reasoning_source_type": "RECORDED_LLM_OUTPUT",
                                  "output_summary": c.get("output_summary")} for c in llm],
        "recorded_llm_call_count": len(llm),
        "live_api_calls": 0, "no_live_calls": True,
        "note": "Recorded hybrid replay — deterministic tool data + recorded LLM reasoning, no live API calls.",
    }


def llm_ledger(snapshot_id: str) -> dict[str, Any]:
    meta = _hybrid_meta(snapshot_id)
    if not meta:
        return {"snapshot_id": snapshot_id, "is_hybrid": False, "llm_calls": []}
    return {"snapshot_id": snapshot_id, "is_hybrid": True, "llm_calls": meta.get("llm_calls", []),
            "models_used": meta.get("models_used", []), "llm_call_count": meta.get("llm_call_count", 0)}


def cost_summary(snapshot_id: str) -> dict[str, Any]:
    meta = _hybrid_meta(snapshot_id)
    return meta.get("cost_summary", {}) if meta else {"note": "not a hybrid snapshot"}
