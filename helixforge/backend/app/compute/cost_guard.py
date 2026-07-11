"""Compute cost estimation + budget guard.

Pricing is a user-configurable SNAPSHOT, never asserted as permanent truth — every
estimate is labeled "verify in provider console". Per-run and per-day budget guards
block over-budget jobs; no paid job runs without an explicit cost estimate, a max
cost, human approval, and a passing safety validation.
"""
from __future__ import annotations

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
        rec = db.get("compute_cost_events", profile_id)
        if rec and rec.get("pricing_snapshot"):
            return rec["pricing_snapshot"]
    return DEFAULT_PRICING["generic_a100_40gb"]


def estimate_gpu_job_cost(spec: dict[str, Any], pricing_profile_id: str | None = None) -> dict[str, Any]:
    """Estimate cost from requested resources × a pricing snapshot. Approximate."""
    rr = spec.get("resource_request") or {}
    prof = _profile(pricing_profile_id)
    gpu_count = int(rr.get("gpu_count", 1) or 1)
    runtime_min = int(rr.get("max_runtime_minutes", 120) or 120)
    gpu_hours = gpu_count * runtime_min / 60.0
    compute_cost = gpu_hours * float(prof.get("price_per_gpu_hour", 2.0))
    # storage: tiny fraction of a month for demo-scale artifacts
    size_gb = (spec.get("output_contract") or {}).get("maximum_total_size_mb", 512) / 1024.0
    storage_cost = size_gb * float(prof.get("storage_per_gb_month", 0.1)) / 30.0
    total = round(compute_cost + storage_cost, 4)
    return {
        "estimated_cost_usd": total, "gpu_hours": round(gpu_hours, 3),
        "pricing_profile": {"id": pricing_profile_id or "generic_a100_40gb", **prof},
        "components": {"compute_usd": round(compute_cost, 4), "storage_usd": round(storage_cost, 5)},
        "currency": prof.get("currency", "USD"),
        "approximate": True, "disclaimer": PRICING_DISCLAIMER, "estimated_at": utcnow(),
    }


def _spent_today() -> float:
    total = 0.0
    for e in db.list_records("compute_cost_events", limit=1000):
        if e.get("event_type") == "actual_cost":
            total += float(e.get("actual_cost_usd") or 0.0)
    return round(total, 4)


def check_budget(estimated_cost_usd: float, job_max_cost_usd: float | None = None) -> dict[str, Any]:
    """Per-run + per-day budget guard. Returns {ok, status, reason, ...}."""
    cfg = get_compute_config()
    run_cap = min(cfg.max_job_cost_usd, job_max_cost_usd) if job_max_cost_usd else cfg.max_job_cost_usd
    spent = _spent_today()
    if estimated_cost_usd > run_cap:
        return {"ok": False, "status": "BUDGET_BLOCKED", "scope": "run",
                "reason": f"estimate ${estimated_cost_usd} exceeds per-run cap ${run_cap}.",
                "run_cap_usd": run_cap, "spent_today_usd": spent, "daily_cap_usd": cfg.max_daily_cost_usd}
    if spent + estimated_cost_usd > cfg.max_daily_cost_usd:
        return {"ok": False, "status": "BUDGET_BLOCKED", "scope": "day",
                "reason": f"estimate would exceed daily cap ${cfg.max_daily_cost_usd} (spent ${spent}).",
                "run_cap_usd": run_cap, "spent_today_usd": spent, "daily_cap_usd": cfg.max_daily_cost_usd}
    return {"ok": True, "status": "OK", "reason": "within budget",
            "run_cap_usd": run_cap, "spent_today_usd": spent, "daily_cap_usd": cfg.max_daily_cost_usd,
            "remaining_today_usd": round(cfg.max_daily_cost_usd - spent, 4)}


def record_cost_event(compute_job_id: str, event_type: str, estimated: float = 0.0,
                      actual: float = 0.0, pricing_snapshot: dict | None = None) -> dict[str, Any]:
    import uuid
    rec = {"id": f"cost-{uuid.uuid4().hex[:10]}", "compute_job_id": compute_job_id,
           "event_type": event_type, "estimated_cost_usd": estimated, "actual_cost_usd": actual,
           "pricing_snapshot": pricing_snapshot or {}, "created_at": utcnow()}
    db.insert("compute_cost_events", rec)
    return rec


def costs_summary() -> dict[str, Any]:
    events = db.list_records("compute_cost_events", limit=1000)
    estimated = round(sum(float(e.get("estimated_cost_usd") or 0) for e in events), 4)
    actual = round(sum(float(e.get("actual_cost_usd") or 0) for e in events
                       if e.get("event_type") == "actual_cost"), 4)
    cfg = get_compute_config()
    return {"estimated_total_usd": estimated, "actual_total_usd": actual,
            "spent_today_usd": _spent_today(), "daily_cap_usd": cfg.max_daily_cost_usd,
            "run_cap_usd": cfg.max_job_cost_usd, "event_count": len(events),
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
