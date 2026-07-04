from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.llm import cost_estimator, llm_adapter, model_router, prompt_cache, prompt_templates, replay_store
from app.llm.config import get_llm_config
from app.llm.schemas import LLMCallPurpose, LLMMode

router = APIRouter(prefix="/api/llm", tags=["llm"])


@router.get("/config")
def llm_config():
    return get_llm_config().public_dict()


@router.get("/health")
def llm_health():
    return llm_adapter.health()


class LLMTestRequest(BaseModel):
    purpose: str = "COST_ESTIMATION_TEST"
    prompt: str = "Summarize: EGFR is a candidate target for expert review."


@router.post("/test")
def llm_test(req: LLMTestRequest):
    """Deterministic self-test of the adapter (no live call unless a key is configured)."""
    res = llm_adapter.call_llm(purpose=req.purpose, prompt_template_id="report_summary",
                               user_prompt=req.prompt, record_ledger=False)
    return res.to_dict()


@router.get("/ledger")
def llm_ledger(run_id: str | None = None):
    return {"calls": replay_store.list_calls(run_id, limit=500)}


@router.get("/costs")
def llm_costs(run_id: str | None = None):
    return model_router.cost_ledger(run_id)


@router.get("/cost-ledger")
def llm_cost_ledger(run_id: str | None = None):
    return model_router.cost_ledger(run_id)


@router.post("/costs/reset-session")
def llm_reset_session():
    prompt_cache.clear()
    return model_router.reset_session()


@router.get("/router")
def llm_router(mode: str | None = None):
    return model_router.route_table(mode)


class RouterPreviewRequest(BaseModel):
    purpose: str
    mode: str | None = None


@router.post("/router/preview")
def llm_router_preview(req: RouterPreviewRequest):
    routing = model_router.route(req.purpose, req.mode)
    est = cost_estimator.estimate_call_cost(routing["model"], 4000, routing["max_output_tokens"])
    return {"routing": routing, "cost_estimate": est}


class SetModeRequest(BaseModel):
    mode: str


@router.post("/router/set-mode")
def llm_set_mode(req: SetModeRequest):
    if req.mode not in LLMMode.ALL:
        raise HTTPException(status_code=400, detail=f"mode must be one of {sorted(LLMMode.ALL)}")
    # Runtime mode hint (env still governs live availability). Returns the route table.
    return {"requested_mode": req.mode, "note": "Set HELIXFORGE_LLM_MODE in env to persist; "
            "live availability still requires USE_LLM + API key.",
            "route_table": model_router.route_table(req.mode)}


class BudgetCheckRequest(BaseModel):
    estimated_cost_usd: float = 0.05
    run_id: str | None = None


@router.post("/budget/check")
def llm_budget_check(req: BudgetCheckRequest):
    return model_router.check_budget(req.estimated_cost_usd, req.run_id)


@router.get("/pricing")
def llm_pricing():
    return cost_estimator.pricing_table()


@router.get("/prompt-templates")
def llm_prompt_templates():
    return {"templates": prompt_templates.registry()}


@router.get("/cache")
def llm_cache():
    return prompt_cache.stats()


@router.post("/replay/{llm_call_id}")
def llm_replay(llm_call_id: str):
    call = replay_store.get_call(llm_call_id)
    if not call:
        raise HTTPException(status_code=404, detail="llm call not found")
    return {"llm_call_id": llm_call_id, "reasoning_source_type": "RECORDED_LLM_OUTPUT",
            "recorded": {k: call.get(k) for k in ("model", "purpose", "output_summary", "data",
                                                  "input_hash", "output_hash")},
            "note": "Recorded LLM output replayed — no live API call."}


# ---- Optional gated live smoke test (§16) ----
class LiveSmokeRequest(BaseModel):
    purpose: str = "DYNAMIC_PLANNING"
    model: str = "claude-sonnet-5"
    max_cost_usd: float = 0.05


@router.post("/live-smoke")
def llm_live_smoke(req: LiveSmokeRequest):
    cfg = get_llm_config()
    if not cfg.enable_live_smoke:
        return {"ran": False, "reason": "HELIXFORGE_ENABLE_LIVE_LLM_SMOKE is not true — live smoke disabled.",
                "safe": True}
    if not cfg.api_key:
        return {"ran": False, "reason": "ANTHROPIC_API_KEY not set.", "safe": True}
    res = llm_adapter.call_llm(
        purpose=LLMCallPurpose.REPORT_SUMMARY, prompt_template_id="report_summary",
        user_prompt="Reply with a one-line neutral confirmation that the reasoning layer is reachable.",
        record_ledger=True)
    return {"ran": True, "model": res.model, "reasoning_source_type": res.reasoning_source_type,
            "tokens_in": res.tokens_in, "tokens_out": res.tokens_out,
            "estimated_cost_usd": res.estimated_cost_usd, "actual_cost_usd": res.actual_cost_usd,
            "fallback_used": res.fallback_used, "safety_status": res.safety_status,
            "health": llm_adapter.health()}
