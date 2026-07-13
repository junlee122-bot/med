"""Model routing policy + per-run / per-day cost guard.

Reserves Fable 5 for the highest-value reasoning (hypothesis, critic in final mode)
and routes routine work to cheaper models. The cost guard blocks calls that would
exceed the per-run or per-day budget and records budget events.
"""
from __future__ import annotations

import math
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from app.llm.config import get_llm_config
from app.llm.schemas import (BUDGET_BLOCKED_DAY, BUDGET_BLOCKED_RUN, BUDGET_OK,
                             LLMCallPurpose, LLMMode)

# ---- Cost ledger (process-lifetime; resettable per session) -----------------
_SESSION_COST: dict[str, float] = {"session_total": 0.0}
_RUN_COST: dict[str, float] = {}          # run_id -> usd
_DAY_COST: dict[str, Any] = {"date": datetime.now(timezone.utc).date().isoformat(), "day_total": 0.0}
_EVENTS: list[dict[str, Any]] = []
_RESERVATIONS: dict[str, dict[str, Any]] = {}
_LOCK = threading.RLock()
_PERSISTED_LEDGER_LOADED = False


def _today_utc() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _refresh_day_locked() -> None:
    today = _today_utc()
    if _DAY_COST.get("date") != today:
        _DAY_COST.update({"date": today, "day_total": 0.0})


def _ensure_persisted_costs_loaded_locked() -> None:
    """Seed guards from persisted calls so a process restart cannot zero them."""
    global _PERSISTED_LEDGER_LOADED
    if _PERSISTED_LEDGER_LOADED:
        return
    from app.storage import db

    # Aggregate over the complete durable ledger in SQLite. Loading only the
    # latest page lets newer zero-cost/fallback calls evict older paid calls and
    # resets the guard after a process restart.
    persisted_runs = db.sum_payload_numeric_by_workflow_run(
        "llm_calls", "actual_cost_usd"
    )
    _RUN_COST.clear()
    _RUN_COST.update({
        run_id: cost for run_id, cost in persisted_runs.items()
        if math.isfinite(cost) and cost > 0
    })
    day_total = db.sum_payload_numeric(
        "llm_calls", "actual_cost_usd", created_at_prefix=_today_utc()
    )
    _DAY_COST["day_total"] = day_total if math.isfinite(day_total) and day_total > 0 else 0.0
    _PERSISTED_LEDGER_LOADED = True


def _reserved_total_locked(run_id: str | None = None) -> float:
    return sum(
        float(reservation["estimated_cost"])
        for reservation in _RESERVATIONS.values()
        if run_id is None or reservation.get("run_id") == run_id
    )


def _budget_result_locked(estimated_cost: float, run_id: str | None) -> dict[str, Any]:
    cfg = get_llm_config()
    _refresh_day_locked()
    _ensure_persisted_costs_loaded_locked()
    run_spent = _RUN_COST.get(run_id, 0.0) if run_id else 0.0
    day_spent = float(_DAY_COST["day_total"])
    run_reserved = _reserved_total_locked(run_id) if run_id else 0.0
    day_reserved = _reserved_total_locked()
    if run_id and (run_spent + run_reserved + estimated_cost) > cfg.max_cost_per_run:
        return {"allowed": False, "status": BUDGET_BLOCKED_RUN,
                "reason": f"per-run budget ${cfg.max_cost_per_run:.2f} would be exceeded "
                          f"(spent ${run_spent:.4f} + reserved ${run_reserved:.4f} + "
                          f"est ${estimated_cost:.4f}).",
                "run_spent": run_spent, "day_spent": day_spent}
    if (day_spent + day_reserved + estimated_cost) > cfg.max_cost_per_day:
        return {"allowed": False, "status": BUDGET_BLOCKED_DAY,
                "reason": f"per-day budget ${cfg.max_cost_per_day:.2f} would be exceeded.",
                "run_spent": run_spent, "day_spent": day_spent}
    return {"allowed": True, "status": BUDGET_OK, "reason": "within budget",
            "run_spent": run_spent, "day_spent": day_spent}


def route(purpose: str, mode: str | None = None) -> dict[str, Any]:
    """Resolve the model + max output tokens for a purpose under a mode."""
    cfg = get_llm_config()
    mode = mode or cfg.mode
    final = mode == LLMMode.HYBRID_FABLE_FINAL

    if purpose in (LLMCallPurpose.DYNAMIC_PLANNING, LLMCallPurpose.REPLANNING):
        model = cfg.final_model if final else cfg.planner_model
        max_tokens = cfg.max_tokens_planner
    elif purpose == LLMCallPurpose.HYPOTHESIS_REASONING:
        model = cfg.hypothesis_model if final else cfg.dev_model
        max_tokens = cfg.max_tokens_hypothesis
    elif purpose == LLMCallPurpose.SEMANTIC_CRITIQUE:
        model = cfg.critic_model if final else cfg.dev_model
        max_tokens = cfg.max_tokens_critic
    elif purpose in (LLMCallPurpose.REPORT_SUMMARY, LLMCallPurpose.PROPOSAL_SUMMARY):
        model = cfg.dev_model if final else cfg.cheap_model
        max_tokens = 1500
    elif purpose == LLMCallPurpose.SAFE_REWRITE:
        model = cfg.cheap_model
        max_tokens = 800
    else:  # COST_ESTIMATION_TEST and any unknown
        model = cfg.cheap_model
        max_tokens = 400
    return {"purpose": purpose, "mode": mode, "model": model, "max_output_tokens": max_tokens,
            "is_final_fable": final and model == cfg.final_model}


def route_table(mode: str | None = None) -> dict[str, Any]:
    cfg = get_llm_config()
    mode = mode or cfg.mode
    rows = {p: route(p, mode) for p in sorted(LLMCallPurpose.ALL)}
    return {"mode": mode, "routes": rows,
            "note": "Fable 5 is reserved for high-value reasoning; routine steps use cheaper models or deterministic fallback."}


# ---- Cost guard --------------------------------------------------------------
def check_budget(estimated_cost: float, run_id: str | None = None) -> dict[str, Any]:
    try:
        estimated_cost = float(estimated_cost)
    except (TypeError, ValueError):
        return {"allowed": False, "status": BUDGET_BLOCKED_RUN,
                "reason": "estimated cost must be a finite non-negative number",
                "run_spent": 0.0, "day_spent": 0.0}
    if not math.isfinite(estimated_cost) or estimated_cost < 0:
        return {"allowed": False, "status": BUDGET_BLOCKED_RUN,
                "reason": "estimated cost must be a finite non-negative number",
                "run_spent": 0.0, "day_spent": 0.0}
    with _LOCK:
        return _budget_result_locked(estimated_cost, run_id)


def reserve_budget(estimated_cost: float, run_id: str | None = None) -> dict[str, Any]:
    """Atomically check and reserve estimated spend for an in-flight call."""
    check = check_budget(estimated_cost, run_id)
    if not check["allowed"]:
        return check
    with _LOCK:
        # Re-check under the same lock because another caller may have reserved
        # after the first validation and before this lock acquisition.
        check = _budget_result_locked(float(estimated_cost), run_id)
        if not check["allowed"]:
            return check
        reservation_id = f"llm-res-{uuid.uuid4().hex[:12]}"
        _RESERVATIONS[reservation_id] = {
            "run_id": run_id, "estimated_cost": float(estimated_cost)
        }
        return {**check, "reservation_id": reservation_id}


def release_reservation(reservation_id: str | None) -> None:
    if not reservation_id:
        return
    with _LOCK:
        _RESERVATIONS.pop(reservation_id, None)


def settle_reservation(reservation_id: str | None, actual_cost: float,
                       model: str = "", purpose: str = "") -> None:
    """Replace an in-flight estimate with the actual recorded spend."""
    with _LOCK:
        reservation = _RESERVATIONS.pop(reservation_id, None) if reservation_id else None
        if reservation is None:
            raise ValueError("unknown or already-settled budget reservation")
        run_id = reservation.get("run_id")
        _record_spend_locked(actual_cost, run_id, model, purpose, cache_hit=False)


def record_spend(actual_cost: float, run_id: str | None = None, model: str = "",
                 purpose: str = "", cache_hit: bool = False) -> None:
    with _LOCK:
        _record_spend_locked(actual_cost, run_id, model, purpose, cache_hit)


def _record_spend_locked(actual_cost: float, run_id: str | None, model: str,
                         purpose: str, cache_hit: bool) -> None:
    try:
        actual_cost = float(actual_cost)
    except (TypeError, ValueError) as exc:
        raise ValueError("actual cost must be a finite non-negative number") from exc
    if not math.isfinite(actual_cost) or actual_cost < 0:
        raise ValueError("actual cost must be a finite non-negative number")
    if cache_hit:
        actual_cost = 0.0
    _refresh_day_locked()
    _ensure_persisted_costs_loaded_locked()
    _SESSION_COST["session_total"] += actual_cost
    _DAY_COST["day_total"] += actual_cost
    if run_id:
        _RUN_COST[run_id] = _RUN_COST.get(run_id, 0.0) + actual_cost
    _EVENTS.append({"run_id": run_id, "model": model, "purpose": purpose,
                    "cost_usd": round(actual_cost, 6), "cache_hit": cache_hit,
                    "date": _DAY_COST["date"]})


def cost_ledger(run_id: str | None = None) -> dict[str, Any]:
    cfg = get_llm_config()
    with _LOCK:
        _refresh_day_locked()
        _ensure_persisted_costs_loaded_locked()
        events = [dict(e) for e in _EVENTS if (not run_id or e["run_id"] == run_id)]
        session_total = _SESSION_COST["session_total"]
        day_total = _DAY_COST["day_total"]
        run_total = _RUN_COST.get(run_id, 0.0) if run_id else None
    by_model: dict[str, dict[str, Any]] = {}
    for e in events:
        m = by_model.setdefault(e["model"] or "unknown", {"calls": 0, "cost_usd": 0.0, "cache_hits": 0})
        m["calls"] += 1
        m["cost_usd"] = round(m["cost_usd"] + e["cost_usd"], 6)
        m["cache_hits"] += 1 if e["cache_hit"] else 0
    return {"session_total_usd": round(session_total, 6),
            "day_total_usd": round(day_total, 6),
            "run_total_usd": round(run_total, 6) if run_total is not None else None,
            "by_model": by_model, "call_count": len(events),
            "cache_hits": sum(1 for e in events if e["cache_hit"]),
            "budget": {"max_cost_per_run_usd": cfg.max_cost_per_run,
                       "max_cost_per_day_usd": cfg.max_cost_per_day}}


def reset_session() -> dict[str, Any]:
    # Session display state may be cleared, but run/day guards intentionally
    # survive so this endpoint cannot be used to bypass budget enforcement.
    with _LOCK:
        _SESSION_COST["session_total"] = 0.0
    return {"reset": True, "budget_counters_preserved": True}


def _reset_all_for_tests() -> None:
    """Test isolation helper; never exposed by the API."""
    global _PERSISTED_LEDGER_LOADED
    with _LOCK:
        _SESSION_COST["session_total"] = 0.0
        _RUN_COST.clear()
        _EVENTS.clear()
        _RESERVATIONS.clear()
        _DAY_COST.update({"date": _today_utc(), "day_total": 0.0})
        _PERSISTED_LEDGER_LOADED = True
