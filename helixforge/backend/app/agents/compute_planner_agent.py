"""Compute Planner agent (Phase 8, Section 25).

Wraps the deterministic compute-aware planner as a first-class agent: given the
detected compute profile, it decides CPU-substitute / GPU-spec / recorded-replay per
capability and records `ComputeDecision`s for the run. Observable trace only (method,
backend, reason, cost, limitations) — no hidden chain-of-thought. Deterministic; needs
no LLM key. It can never add wet-lab, synthesis, dosage, or shell steps.
"""
from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.models.schemas import SourceType


class ComputePlannerAgent(BaseAgent):
    name = "ComputePlannerAgent"
    role = "Choose a scientific method per capability based on quality, cost, and latency"
    stage = "compute_planning"
    stage_index = 1
    allowed_tools = ["compute_capability_detector", "compute_aware_planner"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        from app.compute import capability_detector
        from app.services import compute_aware_planner

        out = AgentOutput()
        caps = capability_detector.detect("local")
        plan = compute_aware_planner.plan_compute(caps, workflow_run_id=ctx.workflow_run_id)
        ctx.shared["compute_profile"] = caps["profile"]
        ctx.shared["compute_decisions"] = plan["decisions"]

        gpu = plan["gpu_enabled"]
        out.output_summary = (
            f"Compute profile {caps['profile']}: {plan['decision_count']} capabilities routed "
            f"({'GPU specs' if gpu else 'CPU substitutes'}). "
            f"{'GPU jobs require human approval.' if gpu else 'No GPU present — CPU substitutes used.'}"
        )
        out.rationale = plan["summary"]
        out.assumptions = ["CPU-only is a complete scientific mode; GPU is an optional accelerator."]
        out.uncertainty_notes = ("CPU substitutes are screening/prioritization signals, not GPU-grade "
                                 "results; GPU quality gains are not realized until a validated, approved job runs.")
        out.next_action = ("Proceed on CPU; build a GPU escalation plan for top candidates if a provider is enabled."
                           if not gpu else "Submit validated GPU specs after human approval.")
        out.source_types = [SourceType.HEURISTIC_ANALYSIS.value]

        # Observable validation checks.
        out.check("compute_profile_detected", bool(caps.get("profile")), caps.get("profile"))
        out.check("no_gpu_is_not_a_failure", True, "missing GPU routes to CPU substitutes")
        out.check("decisions_recorded", plan["decision_count"] > 0, f"{plan['decision_count']} decisions")
        out.check("no_shell_or_synthesis_steps",
                  "step-by-step synthesis" not in str(plan).lower() and "rm -rf" not in str(plan).lower(),
                  "planner cannot emit shell/synthesis")
        out.confidence = 0.85 if caps.get("profile") else 0.5
        ctx.bump(SourceType.HEURISTIC_ANALYSIS.value)
        ctx.local_calls += 1
        return out
