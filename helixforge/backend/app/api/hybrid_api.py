from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import dynamic_planner, hypothesis_reasoner, semantic_critic
from app.storage import db

router = APIRouter(prefix="/api", tags=["hybrid"])


# ---- Dynamic planner ----
class PlanRequest(BaseModel):
    condition: str = "non-small cell lung cancer"
    target_query: str = "EGFR"
    scenario_id: str = ""
    mode: str | None = None
    budget_usd: float = 2.0
    safety_strictness: str = "presentation_safe"
    user_goals: str = ""
    run_id: str | None = None
    project_id: str | None = None


@router.post("/workflow/plan-hybrid")
def plan_hybrid(req: PlanRequest):
    return dynamic_planner.plan_run(
        condition=req.condition, target_query=req.target_query, scenario_id=req.scenario_id,
        mode=req.mode, budget_usd=req.budget_usd, safety_strictness=req.safety_strictness,
        user_goals=req.user_goals, run_id=req.run_id, project_id=req.project_id)


@router.get("/workflow/hybrid-plans/{plan_id}")
def get_hybrid_plan(plan_id: str):
    p = dynamic_planner.get_plan(plan_id)
    if not p:
        raise HTTPException(status_code=404, detail="plan not found")
    return p


@router.get("/workflow/runs/{run_id}/replans")
def run_replans(run_id: str):
    return {"run_id": run_id, "replan_events": dynamic_planner.list_replans(run_id)}


# ---- Hybrid hypotheses ----
class HypothesisRequest(BaseModel):
    run_id: str | None = None
    mode: str | None = None


@router.post("/hypotheses/generate-hybrid")
def hypotheses_generate_hybrid(req: HypothesisRequest):
    return hypothesis_reasoner.generate_hybrid(run_id=req.run_id, mode=req.mode)


@router.get("/hypotheses/run/{run_id}/hybrid")
def hypotheses_run_hybrid(run_id: str):
    return hypothesis_reasoner.get_hybrid(run_id)


# ---- Semantic critic ----
class CriticRequest(BaseModel):
    mode: str | None = None


@router.post("/critic/semantic/run/{run_id}")
def semantic_critic_run(run_id: str, req: CriticRequest):
    return semantic_critic.run_semantic_critic(run_id, mode=req.mode)


@router.get("/critic/semantic/run/{run_id}")
def semantic_critic_get(run_id: str):
    c = semantic_critic.get_semantic_critic(run_id)
    return c or {"run_id": run_id, "critique_items": [], "note": "no semantic critique yet"}
