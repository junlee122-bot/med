"""Hybrid run snapshot + replay.

Extends record/replay to capture LLM reasoning metadata alongside deterministic
tool outputs. Never stores API keys, secrets, unsafe content, hidden
chain-of-thought, or full prompts (unless explicitly enabled and redacted). On
replay there are NO live API calls: recorded LLM outputs are served labeled
RECORDED_LLM_OUTPUT and deterministic-fallback stages stay labeled as such.
"""
from __future__ import annotations

import hashlib
import hmac
import json
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


def _metadata_checksum(meta: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in meta.items() if key != "integrity_checksum"}
    raw = json.dumps(unsigned, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _verify_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    expected = str(meta.get("integrity_checksum") or "")
    actual = _metadata_checksum(meta)
    if not expected or not hmac.compare_digest(expected, actual):
        raise ValueError("hybrid snapshot metadata checksum mismatch; refusing replay")
    return meta


def _safe_llm_call(call: dict) -> dict:
    out = {k: call.get(k) for k in _SAFE_LLM_FIELDS}
    # data may contain reasoning JSON — keep it but redact defensively, never prompts/keys.
    if out.get("data") is not None:
        out["data"] = redact_secrets(out["data"])
    out["output_summary"] = redact_secrets(out.get("output_summary") or "")
    out["input_summary"] = redact_secrets(out.get("input_summary") or "")
    return out


def create_hybrid_snapshot(run_id: str, name: str = "", description: str = "") -> dict[str, Any]:
    """Create a base snapshot (deterministic tool data) + attach LLM metadata."""
    base = snapshots.create_snapshot_from_run(run_id, name or f"hybrid {run_id}",
                                              description or "Hybrid Fable run snapshot", created_by="hybrid")
    snap_id = base["id"]
    llm_calls = db.list_records(
        "llm_calls", project_id=base.get("project_id"), workflow_run_id=run_id, limit=2000
    )
    safe_calls = [_safe_llm_call(c) for c in llm_calls]
    cost = model_router.cost_ledger(run_id)
    real = sum(1 for c in safe_calls if c["reasoning_source_type"] == "REAL_LLM_OUTPUT")
    fallback = sum(1 for c in safe_calls if c["fallback_used"])
    models = sorted({c["model"] for c in safe_calls if c.get("model") and c["model"] != "deterministic"})

    hybrid_meta = {
        "id": f"hybmeta-{snap_id}", "snapshot_id": snap_id, "run_id": run_id,
        "workflow_run_id": run_id, "project_id": base.get("project_id"),
        "created_at": utcnow(), "is_hybrid": True, "llm_calls": safe_calls, "llm_call_count": len(safe_calls),
        "real_llm_output_count": real, "deterministic_fallback_count": fallback,
        "models_used": models, "cost_summary": cost,
        "labels": {"tool_data": "RECORDED_REAL_TOOL_OUTPUT", "llm_reasoning": "RECORDED_LLM_OUTPUT",
                   "fallback": "DETERMINISTIC_FALLBACK"},
        "base_snapshot_checksum": base.get("checksum"),
        "note": "No secrets, keys, full prompts, or chain-of-thought stored. Replay uses no live API calls.",
    }
    hybrid_meta["integrity_checksum"] = _metadata_checksum(hybrid_meta)
    db.insert("snapshot_artifacts", hybrid_meta)
    base["hybrid_meta"] = hybrid_meta
    base["is_hybrid"] = True
    return base


def _hybrid_meta(snapshot_id: str) -> Optional[dict]:
    current = db.get("snapshot_artifacts", f"hybmeta-{snapshot_id}")
    if current and current.get("snapshot_id") == snapshot_id and current.get("is_hybrid"):
        return _verify_metadata(current)
    # Compatibility with snapshots created before metadata IDs became
    # deterministic. New snapshots use the direct lookup above.
    snap = db.get("run_snapshots", snapshot_id)
    rows = [r for r in db.list_records(
        "snapshot_artifacts", project_id=(snap or {}).get("project_id"), limit=1000
    )
            if r.get("snapshot_id") == snapshot_id and r.get("is_hybrid")]
    return _verify_metadata(rows[0]) if rows else None


def replay_hybrid(snapshot_id: str) -> dict[str, Any]:
    """Replay a hybrid snapshot: deterministic data via the base replay, LLM outputs
    served as RECORDED_LLM_OUTPUT. NO live API calls."""
    meta = _hybrid_meta(snapshot_id)
    if not meta:
        raise ValueError("hybrid snapshot metadata not found")
    snap = snapshots.get_snapshot(snapshot_id)
    if not snap or not hmac.compare_digest(
        str(meta.get("base_snapshot_checksum") or ""), str(snap.get("checksum") or "")
    ):
        raise ValueError("hybrid snapshot base checksum mismatch; refusing replay")
    # Verify all metadata before the base replay creates any cloned entities.
    base = snapshots.replay_snapshot(snapshot_id)
    llm = meta.get("llm_calls", []) if meta else []
    replayed_calls = []
    for call in llm:
        original_source = call.get("reasoning_source_type")
        replayable = (
            original_source in ("REAL_LLM_OUTPUT", "RECORDED_LLM_OUTPUT")
            and call.get("data") is not None
            and bool(call.get("input_hash"))
            and bool(call.get("output_hash"))
        )
        replayed_calls.append({
            "llm_call_id": call.get("llm_call_id"), "model": call.get("model"),
            "purpose": call.get("purpose"),
            "reasoning_source_type": ("RECORDED_LLM_OUTPUT" if replayable else original_source),
            "output_summary": call.get("output_summary"), "replayable": replayable,
        })
    return {
        "snapshot_id": snapshot_id, "replayed_at": utcnow(),
        "tool_data_replay": {"source_type": "RECORDED_REAL_TOOL_OUTPUT",
                             "note": base.get("note", "deterministic tool outputs replayed")},
        "llm_reasoning_replay": replayed_calls,
        "recorded_llm_call_count": sum(1 for call in replayed_calls if call["replayable"]),
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
