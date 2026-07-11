"""Compute record/replay (Phase 8, Section 22).

Captures a run's compute state (profile, decisions, CPU model metadata, GPU job
specs, recorded GPU outputs, cost events, artifact metadata + checksums, validation
statuses, timestamps) for offline replay. Replay makes NO provider call and incurs
NO cost; recorded GPU outputs are labeled RECORDED_GPU_OUTPUT with original + replay
timestamps. Credentials, large binaries, and unredacted logs are never included.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.compute.security import redact_secrets
from app.models.schemas import SourceType, utcnow
from app.storage import db


def create_from_run(run_id: str) -> dict[str, Any]:
    decisions = [d for d in db.list_records("compute_decisions", limit=500)
                 if d.get("workflow_run_id") == run_id]
    cpu_models = [m for m in db.list_records("cpu_models", limit=200) if m.get("run_id") == run_id]
    jobs = [j for j in db.list_records("compute_jobs", limit=200) if j.get("workflow_run_id") == run_id]
    artifacts = db.list_records("compute_artifacts", limit=500)
    cost_events = db.list_records("compute_cost_events", limit=500)

    def _model_meta(m: dict) -> dict:
        return {"id": m["id"], "task": m.get("task"), "model_family": m.get("model_family"),
                "metrics": m.get("metrics"), "checksum": m.get("checksum"),
                "validation_status": m.get("validation_status"), "source_type": m.get("source_type")}

    def _artifact_meta(a: dict) -> dict:
        return {"id": a["id"], "artifact_type": a.get("artifact_type"), "checksum_sha256": a.get("checksum_sha256"),
                "validation_status": a.get("validation_status"), "source_type": a.get("source_type"),
                "size_bytes": a.get("size_bytes")}

    snap = {
        "id": f"csnap-{uuid.uuid4().hex[:8]}", "workflow_run_id": run_id, "kind": "compute_snapshot",
        "compute_profile": (db.list_records("compute_decisions", limit=1) or [{}]),
        "compute_decisions": decisions,
        "cpu_model_metadata": [_model_meta(m) for m in cpu_models],
        "gpu_job_specs": [{"id": j["id"], "job_type": j.get("job_type"), "status": j.get("status"),
                           "specification_hash": j.get("specification_hash"),
                           "source_type": j.get("source_type")} for j in jobs],
        "recorded_gpu_outputs": [_artifact_meta(a) for a in artifacts
                                 if a.get("source_type") == SourceType.RECORDED_GPU_OUTPUT.value],
        "artifact_metadata": [_artifact_meta(a) for a in artifacts],
        "cost_events": [{"id": e["id"], "event_type": e.get("event_type"),
                         "estimated_cost_usd": e.get("estimated_cost_usd"),
                         "actual_cost_usd": e.get("actual_cost_usd")} for e in cost_events],
        "original_timestamps": {"captured_at": utcnow()},
        "excludes": ["credentials", "large checkpoints", "trajectories", "unredacted logs", "binaries"],
        "created_at": utcnow(),
    }
    snap = redact_secrets(snap)  # belt-and-suspenders: no secrets ever
    db.insert("compute_snapshots", snap)
    return snap


def replay(snapshot_id: str) -> dict[str, Any]:
    snap = db.get("compute_snapshots", snapshot_id)
    if not snap:
        raise ValueError("compute snapshot not found")
    replayed_at = utcnow()
    return {
        "snapshot_id": snapshot_id, "workflow_run_id": snap.get("workflow_run_id"),
        "provider_call_made": False, "cost_usd": 0.0,
        "compute_decisions": snap.get("compute_decisions", []),
        "cpu_model_metadata": snap.get("cpu_model_metadata", []),
        "recorded_gpu_outputs": [{**a, "source_type": SourceType.RECORDED_GPU_OUTPUT.value,
                                  "original_captured_at": snap.get("original_timestamps", {}).get("captured_at"),
                                  "replayed_at": replayed_at} for a in snap.get("recorded_gpu_outputs", [])],
        "gpu_job_specs": snap.get("gpu_job_specs", []),
        "banner": "REPLAY: no live provider call, zero cost. Recorded GPU outputs are labeled RECORDED_GPU_OUTPUT.",
        "replayed_at": replayed_at,
    }


def manifest(snapshot_id: str) -> dict[str, Any]:
    snap = db.get("compute_snapshots", snapshot_id)
    if not snap:
        raise ValueError("compute snapshot not found")
    return {
        "snapshot_id": snapshot_id, "workflow_run_id": snap.get("workflow_run_id"),
        "decision_count": len(snap.get("compute_decisions", [])),
        "cpu_model_count": len(snap.get("cpu_model_metadata", [])),
        "gpu_job_spec_count": len(snap.get("gpu_job_specs", [])),
        "recorded_gpu_output_count": len(snap.get("recorded_gpu_outputs", [])),
        "artifact_count": len(snap.get("artifact_metadata", [])),
        "excludes": snap.get("excludes", []),
        "contains_credentials": False, "captured_at": snap.get("original_timestamps", {}).get("captured_at"),
    }


def llm_ledger(snapshot_id: str) -> dict[str, Any]:
    """Compute snapshots do not store LLM prompts/outputs — kept separate by design."""
    return {"snapshot_id": snapshot_id, "llm_calls": [],
            "note": "Compute snapshots capture compute metadata only; LLM reasoning lives in the AI ledger."}
