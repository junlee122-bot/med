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
    run = db.get("workflow_runs", run_id)
    if not run:
        raise ValueError("workflow run not found")
    project_id = run.get("project_id")
    decisions = db.list_records(
        "compute_decisions", project_id=project_id, workflow_run_id=run_id, limit=500
    )
    cpu_models = db.list_records("cpu_models", workflow_run_id=run_id, limit=500)
    jobs = db.list_records(
        "compute_jobs", project_id=project_id, workflow_run_id=run_id, limit=500
    )
    job_ids = {str(job.get("id")) for job in jobs if job.get("id")}

    # Artifacts and cost events historically carried only their parent job id.
    # Join through the exact run-owned job set; never include global rows in a
    # run snapshot. Newer scoped rows are still constrained by the same parent.
    artifacts = [
        artifact for artifact in db.list_records("compute_artifacts", limit=5000)
        if str(artifact.get("compute_job_id")) in job_ids
    ]
    cost_events = [
        event for event in db.list_records("compute_cost_events", limit=5000)
        if str(event.get("compute_job_id")) in job_ids
    ]

    def _model_meta(m: dict) -> dict:
        return {"id": m["id"], "task": m.get("task"), "model_family": m.get("model_family"),
                "metrics": m.get("metrics"), "checksum": m.get("checksum"),
                "validation_status": m.get("validation_status"), "source_type": m.get("source_type")}

    def _artifact_meta(a: dict) -> dict:
        return {"id": a["id"], "artifact_type": a.get("artifact_type"), "checksum_sha256": a.get("checksum_sha256"),
                "validation_status": a.get("validation_status"), "source_type": a.get("source_type"),
                "size_bytes": a.get("size_bytes")}

    snap = {
        "id": f"csnap-{uuid.uuid4().hex[:8]}", "project_id": project_id,
        "workflow_run_id": run_id, "kind": "compute_snapshot",
        "compute_profile": decisions[0] if decisions else {},
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


def cost_summary(snapshot_id: str) -> dict[str, Any]:
    """Return only the cost events captured in this compute snapshot."""
    snap = db.get("compute_snapshots", snapshot_id)
    if not snap:
        raise ValueError("compute snapshot not found")
    events = snap.get("cost_events") or []
    estimated = round(sum(float(event.get("estimated_cost_usd") or 0.0) for event in events), 4)
    actual = round(sum(
        float(event.get("actual_cost_usd") or 0.0)
        for event in events if event.get("event_type") == "actual_cost"
    ), 4)
    return {
        "snapshot_id": snapshot_id,
        "workflow_run_id": snap.get("workflow_run_id"),
        "estimated_total_usd": estimated,
        "actual_total_usd": actual,
        "event_count": len(events),
        "replay_cost_usd": 0.0,
        "note": "Snapshot-scoped recorded costs; replay incurs zero live cost.",
    }


def llm_ledger(snapshot_id: str) -> dict[str, Any]:
    """Compute snapshots do not store LLM prompts/outputs — kept separate by design."""
    return {"snapshot_id": snapshot_id, "llm_calls": [],
            "note": "Compute snapshots capture compute metadata only; LLM reasoning lives in the AI ledger."}
