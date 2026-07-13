"""Compute cost estimation + budget guard.

Pricing is a user-configurable SNAPSHOT, never asserted as permanent truth — every
estimate is labeled "verify in provider console". Per-run and per-day budget guards
block over-budget jobs; no paid job runs without an explicit cost estimate, a max
cost, human approval, and a passing safety validation.
"""
from __future__ import annotations

import math
import threading
from typing import Any

from app.compute.config import get_compute_config
from app.models.schemas import utcnow
from app.storage import db

# Default GPU-hour price snapshot (USD). NOT authoritative — verify in provider console.
DEFAULT_PRICING: dict[str, dict[str, Any]] = {
    "generic_a100_40gb": {"gpu_class": "A100-40GB", "price_per_gpu_hour": 1.80,
                          "storage_per_gb_month": 0.10, "currency": "USD"},
    "generic_a100_80gb": {"gpu_class": "A100-80GB", "price_per_gpu_hour": 2.50,
                          "storage_per_gb_month": 0.10, "currency": "USD"},
    "generic_h100": {"gpu_class": "H100-80GB", "price_per_gpu_hour": 4.00,
                     "storage_per_gb_month": 0.12, "currency": "USD"},
    "generic_l4": {"gpu_class": "L4-24GB", "price_per_gpu_hour": 0.80,
                   "storage_per_gb_month": 0.08, "currency": "USD"},
}
PRICING_DISCLAIMER = ("Pricing is a user-configurable snapshot and may be outdated — "
                      "verify current rates in the provider console before running a paid job.")
_BUDGET_LOCK = threading.RLock()


def _nonnegative_finite(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be a finite non-negative number") from exc
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{label} must be a finite non-negative number")
    return number


def list_pricing_profiles() -> dict[str, Any]:
    stored = {p["id"]: p for p in db.list_records("compute_cost_events", limit=200)
              if p.get("event_type") == "pricing_profile"}
    profiles = [{"id": k, **v, "verified": False, "user_entered": False} for k, v in DEFAULT_PRICING.items()]
    profiles += [{"id": p["id"], **(p.get("pricing_snapshot") or {}), "verified": False, "user_entered": True}
                 for p in stored.values()]
    return {"profiles": profiles, "disclaimer": PRICING_DISCLAIMER, "checked_at": utcnow()}


def _profile(profile_id: str | None) -> dict[str, Any]:
    if profile_id and profile_id in DEFAULT_PRICING:
        return DEFAULT_PRICING[profile_id]
    if profile_id:
        rec = db.get("compute_cost_events", f"pricing-profile-{profile_id}")
        if not rec:
            # Backward compatibility for profiles created before IDs were
            # namespaced; never accept a non-profile cost event.
            legacy = db.get("compute_cost_events", profile_id)
            rec = legacy if legacy and legacy.get("event_type") == "pricing_profile" else None
        if rec and rec.get("event_type") == "pricing_profile" and rec.get("pricing_snapshot"):
            profile = dict(rec["pricing_snapshot"])
            _nonnegative_finite(profile.get("price_per_gpu_hour"), "price_per_gpu_hour")
            _nonnegative_finite(profile.get("storage_per_gb_month"), "storage_per_gb_month")
            return profile
        raise ValueError("pricing profile not found")
    return dict(DEFAULT_PRICING["generic_a100_40gb"])


def estimate_gpu_job_cost(spec: dict[str, Any], pricing_profile_id: str | None = None) -> dict[str, Any]:
    """Estimate cost from requested resources × a pricing snapshot. Approximate."""
    rr = spec.get("resource_request") or {}
    prof = _profile(pricing_profile_id)
    gpu_count = int(rr.get("gpu_count", 1) or 1)
    runtime_min = int(rr.get("max_runtime_minutes", 120) or 120)
    gpu_hours = gpu_count * runtime_min / 60.0
    hourly_rate = _nonnegative_finite(prof.get("price_per_gpu_hour", 2.0), "price_per_gpu_hour")
    storage_rate = _nonnegative_finite(
        prof.get("storage_per_gb_month", 0.1), "storage_per_gb_month"
    )
    compute_cost = gpu_hours * hourly_rate
    # storage: tiny fraction of a month for demo-scale artifacts
    size_gb = (spec.get("output_contract") or {}).get("maximum_total_size_mb", 512) / 1024.0
    storage_cost = size_gb * storage_rate / 30.0
    total = round(compute_cost + storage_cost, 4)
    return {
        "estimated_cost_usd": total, "gpu_hours": round(gpu_hours, 3),
        "pricing_profile": {"id": pricing_profile_id or "generic_a100_40gb", **prof},
        "components": {"compute_usd": round(compute_cost, 4), "storage_usd": round(storage_cost, 5)},
        "currency": prof.get("currency", "USD"),
        "approximate": True, "disclaimer": PRICING_DISCLAIMER, "estimated_at": utcnow(),
    }


def _spent_today(workflow_run_id: str | None = None) -> float:
    today = utcnow()[:10]
    total = db.sum_payload_numeric(
        "compute_cost_events", "actual_cost_usd", workflow_run_id=workflow_run_id,
        created_at_prefix=today,
        payload_equals={"event_type": "actual_cost"},
    )
    return round(total, 4)


def _spent_for_run(workflow_run_id: str) -> float:
    return round(db.sum_payload_numeric(
        "compute_cost_events", "actual_cost_usd", workflow_run_id=workflow_run_id,
        payload_equals={"event_type": "actual_cost"},
    ), 4)


def _active_reserved(workflow_run_id: str | None = None) -> float:
    return db.sum_payload_numeric(
        "compute_cost_events", "reserved_cost_usd", workflow_run_id=workflow_run_id,
        payload_equals={"event_type": "budget_reservation", "reservation_status": "ACTIVE"},
    )


def check_budget(estimated_cost_usd: float, job_max_cost_usd: float | None = None,
                 workflow_run_id: str | None = None) -> dict[str, Any]:
    """Per-run + per-day budget guard. Returns {ok, status, reason, ...}."""
    cfg = get_compute_config()
    try:
        estimated_cost_usd = _nonnegative_finite(estimated_cost_usd, "estimated_cost_usd")
        configured_cap = _nonnegative_finite(cfg.max_job_cost_usd, "configured run cap")
        requested_cap = (_nonnegative_finite(job_max_cost_usd, "job max cost")
                         if job_max_cost_usd is not None else configured_cap)
        daily_cap = _nonnegative_finite(cfg.max_daily_cost_usd, "daily cap")
    except ValueError as exc:
        return {"ok": False, "status": "BUDGET_BLOCKED", "scope": "invalid",
                "reason": str(exc)}
    run_cap = min(configured_cap, requested_cap)
    spent = _spent_today()
    reserved = _active_reserved()
    run_spent = _spent_for_run(workflow_run_id) if workflow_run_id else 0.0
    run_reserved = _active_reserved(workflow_run_id) if workflow_run_id else 0.0
    if estimated_cost_usd > run_cap or (
        workflow_run_id and run_spent + run_reserved + estimated_cost_usd > run_cap
    ):
        return {"ok": False, "status": "BUDGET_BLOCKED", "scope": "run",
                "reason": (f"estimate would exceed per-run cap ${run_cap} "
                           f"(spent ${run_spent:.4f}, reserved ${run_reserved:.4f})."),
                "run_cap_usd": run_cap, "run_spent_usd": run_spent,
                "run_reserved_usd": run_reserved, "spent_today_usd": spent,
                "reserved_usd": reserved, "daily_cap_usd": daily_cap}
    if spent + reserved + estimated_cost_usd > daily_cap:
        return {"ok": False, "status": "BUDGET_BLOCKED", "scope": "day",
                "reason": (f"estimate would exceed daily cap ${daily_cap} "
                           f"(spent ${spent:.4f}, reserved ${reserved:.4f})."),
                "run_cap_usd": run_cap, "spent_today_usd": spent,
                "reserved_usd": reserved, "daily_cap_usd": daily_cap}
    return {"ok": True, "status": "OK", "reason": "within budget",
            "run_cap_usd": run_cap, "run_spent_usd": run_spent,
            "run_reserved_usd": run_reserved, "spent_today_usd": spent,
            "reserved_usd": reserved, "daily_cap_usd": daily_cap,
            "remaining_today_usd": round(daily_cap - spent - reserved, 4)}


def reserve_budget(compute_job_id: str, estimated_cost_usd: float,
                   job_max_cost_usd: float | None = None, *,
                   project_id: str | None = None,
                   workflow_run_id: str | None = None) -> dict[str, Any]:
    """Atomically replace a job reservation after checking run/day capacity."""
    reservation_id = f"cost-reservation-{compute_job_id}"
    with _BUDGET_LOCK:
        existing = db.get("compute_cost_events", reservation_id)
        if existing and existing.get("reservation_status") == "ACTIVE":
            existing["reservation_status"] = "RELEASED"
            existing["reserved_cost_usd"] = 0.0
            existing["released_at"] = utcnow()
            db.insert("compute_cost_events", existing)
        budget = check_budget(
            estimated_cost_usd, job_max_cost_usd, workflow_run_id=workflow_run_id
        )
        if not budget["ok"]:
            return budget
        amount = _nonnegative_finite(estimated_cost_usd, "estimated_cost_usd")
        db.insert("compute_cost_events", {
            "id": reservation_id, "project_id": project_id,
            "workflow_run_id": workflow_run_id, "compute_job_id": compute_job_id,
            "event_type": "budget_reservation", "reservation_status": "ACTIVE",
            "reserved_cost_usd": amount, "estimated_cost_usd": amount,
            "actual_cost_usd": 0.0, "created_at": utcnow(),
        })
        return {**budget, "reservation_id": reservation_id,
                "reserved_cost_usd": amount}


def release_budget_reservation(compute_job_id: str) -> None:
    with _BUDGET_LOCK:
        reservation_id = f"cost-reservation-{compute_job_id}"
        existing = db.get("compute_cost_events", reservation_id)
        if not existing or existing.get("reservation_status") != "ACTIVE":
            return
        existing["reservation_status"] = "RELEASED"
        existing["reserved_cost_usd"] = 0.0
        existing["released_at"] = utcnow()
        db.insert("compute_cost_events", existing)


def record_cost_event(compute_job_id: str, event_type: str, estimated: float = 0.0,
                      actual: float = 0.0, pricing_snapshot: dict | None = None,
                      project_id: str | None = None,
                      workflow_run_id: str | None = None) -> dict[str, Any]:
    import uuid
    estimated = _nonnegative_finite(estimated, "estimated cost")
    actual = _nonnegative_finite(actual, "actual cost")
    with _BUDGET_LOCK:
        if event_type == "actual_cost":
            release_budget_reservation(compute_job_id)
        rec = {"id": f"cost-{uuid.uuid4().hex[:10]}", "project_id": project_id,
               "workflow_run_id": workflow_run_id, "compute_job_id": compute_job_id,
               "event_type": event_type, "estimated_cost_usd": estimated,
               "actual_cost_usd": actual, "pricing_snapshot": pricing_snapshot or {},
               "created_at": utcnow()}
        db.insert("compute_cost_events", rec)
    return rec


def costs_summary(workflow_run_id: str | None = None) -> dict[str, Any]:
    """Summarize all costs, or only events owned by one workflow run."""
    estimated = round(sum(db.sum_payload_numeric(
        "compute_cost_events", "estimated_cost_usd", workflow_run_id=workflow_run_id,
        payload_equals={"event_type": event_type},
    ) for event_type in ("estimate", "retry_estimate")), 4)
    actual = round(db.sum_payload_numeric(
        "compute_cost_events", "actual_cost_usd",
        workflow_run_id=workflow_run_id,
        payload_equals={"event_type": "actual_cost"},
    ), 4)
    reserved = round(_active_reserved(workflow_run_id), 4)
    event_count = db.count("compute_cost_events", workflow_run_id=workflow_run_id)
    cfg = get_compute_config()
    return {"estimated_total_usd": estimated, "actual_total_usd": actual,
            "spent_today_usd": _spent_today(workflow_run_id), "reserved_usd": reserved,
            "daily_cap_usd": cfg.max_daily_cost_usd,
            "run_cap_usd": cfg.max_job_cost_usd, "event_count": event_count,
            "workflow_run_id": workflow_run_id,
            "replay_cost_usd": 0.0, "note": "Replayed compute has zero live cost.",
            "disclaimer": PRICING_DISCLAIMER, "checked_at": utcnow()}


def compare_cpu_vs_gpu(job_type: str, cpu_seconds_estimate: float, spec: dict[str, Any],
                       pricing_profile_id: str | None = None) -> dict[str, Any]:
    """Honest CPU-vs-GPU tradeoff for the planner/UI. Estimates are approximate."""
    gpu = estimate_gpu_job_cost(spec, pricing_profile_id)
    recommendation = "CPU_ONLY"
    if gpu["estimated_cost_usd"] <= 2.0 and cpu_seconds_estimate > 1800:
        recommendation = "REMOTE_GPU_RECOMMENDED"
    elif cpu_seconds_estimate > 7200:
        recommendation = "NEEDS_BENCHMARK"
    return {
        "job_type": job_type,
        "cpu": {"estimated_seconds": round(cpu_seconds_estimate, 1), "estimated_cost_usd": 0.0,
                "backend": "LOCAL_CPU"},
        "gpu": {"estimated_cost_usd": gpu["estimated_cost_usd"], "gpu_hours": gpu["gpu_hours"],
                "backend": "REMOTE_GPU"},
        "expected_quality_difference": "GPU may improve throughput/model capacity; CPU baseline is honest and auditable.",
        "recommendation": recommendation, "disclaimer": PRICING_DISCLAIMER, "checked_at": utcnow(),
    }
