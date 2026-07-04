"""Thin wrapper exposing the hybrid dynamic planner as an agent-style entry point.
The deterministic OrchestratorAgent remains the fixed-stage fallback; this agent
adds LLM-assisted dynamic planning with deterministic validation + fallback."""
from __future__ import annotations

from typing import Any, Optional

from app.services import dynamic_planner


class HybridPlannerAgent:
    name = "Hybrid Planner Agent"
    role = ("Produces a validated execution plan using the LLM when enabled; falls back "
            "to the fixed deterministic plan. Cannot add wet-lab/synthesis/dosage stages.")
    stage = "dynamic_plan"

    def plan(self, *, condition: str, target_query: str, scenario_id: str = "",
             mode: Optional[str] = None, tools_health: Optional[dict] = None,
             run_id: Optional[str] = None, project_id: Optional[str] = None,
             client: Any = None, **kw) -> dict[str, Any]:
        return dynamic_planner.plan_run(condition=condition, target_query=target_query,
                                        scenario_id=scenario_id, mode=mode, tools_health=tools_health,
                                        run_id=run_id, project_id=project_id, client=client, **kw)
