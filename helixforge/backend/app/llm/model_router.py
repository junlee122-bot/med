"""Model routing policy + per-run / per-day cost guard.

Reserves Fable 5 for the highest-value reasoning (hypothesis, critic in final mode)
and routes routine work to cheaper models. The cost guard blocks calls that would
exceed the per-run or per-day budget and records budget events.
"""
from __future__ import annotations

from typing import Any

from app.llm.config import get_llm_config
from app.llm.schemas import (BUDGET_BLOCKED_DAY, BUDGET_BLOCKED_RUN, BUDGET_OK,
                             LLMCallPurpose, LLMMode)

# ---- Cost ledger (process-lifetime; resettable per session) -----------------
_SESSION_COST: dict[str, float] = {"session_total": 0.0}
_RUN_COST: dict[str, float] = {}          # run_id -> usd
_DAY_COST: dict[str, float] = {"day_total": 0.0}  # simple running total (no wall clock)
_EVENTS: list[dict[str, Any]] = []


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
    cfg = get_llm_config()
    run_spent = _RUN_COST.get(run_id, 0.0) if run_id else 0.0
    day_spent = _DAY_COST["day_total"]
    if run_id and (run_spent + estimated_cost) > cfg.max_cost_per_run:
        return {"allowed": False, "status": BUDGET_BLOCKED_RUN,
                "reason": f"per-run budget ${cfg.max_cost_per_run:.2f} would be exceeded "
                          f"(spent ${run_spent:.4f} + est ${estimated_cost:.4f}).",
                "run_spent": run_spent, "day_spent": day_spent}
    if (day_spent + estimated_cost) > cfg.max_cost_per_day:
        return {"allowed": False, "status": BUDGET_BLOCKED_DAY,
                "reason": f"per-day budget ${cfg.max_cost_per_day:.2f} would be exceeded.",
                "run_spent": run_spent, "day_spent": day_spent}
    return {"allowed": True, "status": BUDGET_OK, "reason": "within budget",
            "run_spent": run_spent, "day_spent": day_spent}


def record_spend(actual_cost: float, run_id: str | None = None, model: str = "",
                 purpose: str = "", cache_hit: bool = False) -> None:
    if cache_hit:
        actual_cost = 0.0
    _SESSION_COST["session_total"] += actual_cost
    _DAY_COST["day_total"] += actual_cost
    if run_id:
        _RUN_COST[run_id] = _RUN_COST.get(run_id, 0.0) + actual_cost
    _EVENTS.append({"run_id": run_id, "model": model, "purpose": purpose,
                    "cost_usd": round(actual_cost, 6), "cache_hit": cache_hit})


def cost_ledger(run_id: str | None = None) -> dict[str, Any]:
    cfg = get_llm_config()
    events = [e for e in _EVENTS if (not run_id or e["run_id"] == run_id)]
    by_model: dict[str, dict[str, Any]] = {}
    for e in events:
        m = by_model.setdefault(e["model"] or "unknown", {"calls": 0, "cost_usd": 0.0, "cache_hits": 0})
        m["calls"] += 1
        m["cost_usd"] = round(m["cost_usd"] + e["cost_usd"], 6)
        m["cache_hits"] += 1 if e["cache_hit"] else 0
    return {"session_total_usd": round(_SESSION_COST["session_total"], 6),
            "day_total_usd": round(_DAY_COST["day_total"], 6),
            "run_total_usd": round(_RUN_COST.get(run_id, 0.0), 6) if run_id else None,
            "by_model": by_model, "call_count": len(events),
            "cache_hits": sum(1 for e in events if e["cache_hit"]),
            "budget": {"max_cost_per_run_usd": cfg.max_cost_per_run,
                       "max_cost_per_day_usd": cfg.max_cost_per_day}}


def reset_session() -> dict[str, Any]:
    _SESSION_COST["session_total"] = 0.0
    _DAY_COST["day_total"] = 0.0
    _RUN_COST.clear()
    _EVENTS.clear()
    return {"reset": True}
