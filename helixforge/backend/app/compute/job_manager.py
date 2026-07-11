"""Compute job lifecycle manager.

Create → validate (safety) → estimate cost → budget check → require human approval.
A paid/remote job is NEVER submitted until it is explicitly approved. CPU jobs run
through the local worker. This module owns persistence for compute_jobs.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.compute import job_spec as JS
from app.compute import schemas as S
from app.compute.cost_guard import check_budget, estimate_gpu_job_cost, record_cost_event
from app.compute.provider_registry import get_provider
from app.models.schemas import SourceType, utcnow
from app.storage import db


def dry_run(spec: dict[str, Any], pricing_profile_id: str | None = None) -> dict[str, Any]:
    """Validate + estimate + provider selection WITHOUT submitting. Section 5 contract."""
    from app.compute.security import scan_spec_for_forbidden
    v = JS.validate_gpu_job_spec(spec)
    blocked_fields = scan_spec_for_forbidden(spec)
    est = estimate_gpu_job_cost(v["normalized"], pricing_profile_id) if v["valid"] else None
    budget = check_budget(est["estimated_cost_usd"], v["normalized"]["resource_request"]["max_cost_usd"]) if est else None
    provider = get_provider("generic_rest")
    payload = JS.build_safe_job_payload(v["normalized"]) if v["valid"] else None
    return {
        "validated": v["valid"], "errors": v["errors"], "warnings": v["warnings"],
        "normalized_spec": v["normalized"], "spec_hash": v.get("spec_hash"),
        "selected_provider": provider.provider_type,
        "safe_payload": {"image": payload["image"], "entrypoint": payload["entrypoint"]} if payload else None,
        "estimated_cost": est, "budget": budget,
        "expected_artifacts": v["normalized"]["output_contract"]["required_artifact_types"] if v["valid"] else [],
        "blocked_fields": blocked_fields,
        "human_approval_required": True, "submitted": False,
        "note": "Dry run: no provider submission, no cost incurred.", "checked_at": utcnow(),
    }


def create_job(spec: dict[str, Any], requested_by_agent: str = "human",
               project_id: str | None = None, workflow_run_id: str | None = None,
               pricing_profile_id: str | None = None) -> dict[str, Any]:
    """Create a compute job in a pre-submission state. Never submits."""
    job_id = f"cjob-{uuid.uuid4().hex[:10]}"
    v = JS.validate_gpu_job_spec(spec)
    now = utcnow()
    base = {
        "id": job_id, "project_id": project_id or spec.get("project_id"),
        "workflow_run_id": workflow_run_id or spec.get("workflow_run_id"),
        "requested_by_agent": requested_by_agent, "job_type": spec.get("job_type"),
        "provider_id": "generic_rest", "execution_backend": S.ExecutionBackend.REMOTE_GPU,
        "specification": v["normalized"], "specification_hash": v.get("spec_hash"),
        "idempotency_key": v.get("spec_hash"),
        "created_at": now, "retry_count": 0, "max_retries": 1,
        "warnings": v["warnings"], "errors": v["errors"],
    }
    if not v["valid"]:
        base.update({"status": S.ComputeJobStatus.VALIDATION_FAILED,
                     "approval_status": S.ApprovalStatus.NOT_REQUIRED,
                     "human_approval_required": True,
                     "source_type": SourceType.GPU_SAFETY_BLOCKED.value})
        db.insert("compute_jobs", base)
        return base
    est = estimate_gpu_job_cost(v["normalized"], pricing_profile_id)
    budget = check_budget(est["estimated_cost_usd"], v["normalized"]["resource_request"]["max_cost_usd"])
    record_cost_event(job_id, "estimate", estimated=est["estimated_cost_usd"],
                      pricing_snapshot=est.get("pricing_profile"))
    if not budget["ok"]:
        base.update({"status": S.ComputeJobStatus.BUDGET_BLOCKED,
                     "approval_status": S.ApprovalStatus.NOT_REQUIRED,
                     "estimated_cost_usd": est["estimated_cost_usd"], "human_approval_required": True,
                     "budget": budget, "source_type": SourceType.GPU_BUDGET_BLOCKED.value})
        db.insert("compute_jobs", base)
        return base
    base.update({
        "status": S.ComputeJobStatus.WAITING_FOR_APPROVAL,
        "estimated_cost_usd": est["estimated_cost_usd"], "estimated_runtime_seconds":
            v["normalized"]["resource_request"]["max_runtime_minutes"] * 60,
        "requested_resources": v["normalized"]["resource_request"],
        "human_approval_required": True, "approval_status": S.ApprovalStatus.PENDING,
        "budget": budget, "source_type": SourceType.GPU_CONFIGURED_NOT_RUN.value,
    })
    db.insert("compute_jobs", base)
    return base


def approve_job(job_id: str, approved_by: str = "human", approved_cost_usd: float | None = None) -> dict[str, Any]:
    job = db.get("compute_jobs", job_id)
    if not job:
        raise ValueError("job not found")
    if job.get("status") != S.ComputeJobStatus.WAITING_FOR_APPROVAL:
        return {**job, "note": f"job not awaiting approval (status={job.get('status')})."}
    job["approval_status"] = S.ApprovalStatus.APPROVED
    job["approved_by"] = approved_by
    job["approved_cost_usd"] = approved_cost_usd or job.get("estimated_cost_usd")
    # Approval alone does not submit in this build session — it marks the job ready.
    job["status"] = S.ComputeJobStatus.CONFIGURED_NOT_RUN
    job["approved_at"] = utcnow()
    job["note"] = ("Approved. Live submission is gated (HELIXFORGE_ENABLE_LIVE_GPU_TEST); "
                   "no paid job runs in this build session.")
    db.insert("compute_jobs", job)
    return job


def cancel_job(job_id: str) -> dict[str, Any]:
    job = db.get("compute_jobs", job_id)
    if not job:
        raise ValueError("job not found")
    job["status"] = S.ComputeJobStatus.CANCELLED
    job["cancelled_at"] = utcnow()
    db.insert("compute_jobs", job)
    return job


def retry_job(job_id: str) -> dict[str, Any]:
    job = db.get("compute_jobs", job_id)
    if not job:
        raise ValueError("job not found")
    if job.get("retry_count", 0) >= job.get("max_retries", 1):
        return {**job, "note": "max retries reached; not retrying (avoids infinite retry)."}
    job["retry_count"] = job.get("retry_count", 0) + 1
    job["status"] = S.ComputeJobStatus.WAITING_FOR_APPROVAL
    job["approval_status"] = S.ApprovalStatus.PENDING
    db.insert("compute_jobs", job)
    return job


def get_job(job_id: str) -> dict[str, Any] | None:
    return db.get("compute_jobs", job_id)


def list_jobs(project_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return db.list_records("compute_jobs", project_id=project_id, limit=limit)
