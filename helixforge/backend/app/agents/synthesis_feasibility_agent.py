from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent


class SynthesisFeasibilityAgent(BaseAgent):
    name = "Synthesis Feasibility Agent"
    role = "Produces a high-level, NON-ACTIONABLE feasibility summary only. By policy it never emits routes, reagents, conditions, or procedures."
    stage = "synthesis_feasibility"
    stage_index = 10
    allowed_tools = []

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        molecules = [m for m in ctx.shared.get("molecules", []) if m.get("valid")]
        # Heuristic, non-actionable feasibility band from descriptor complexity only.
        summary = []
        for m in molecules:
            d = m.get("descriptors") or {}
            rings = d.get("ring_count", 0) or 0
            rot = d.get("rotatable_bonds", 0) or 0
            complexity = min(1.0, (rings * 0.1 + rot * 0.03))
            band = "High" if complexity < 0.35 else ("Medium" if complexity < 0.6 else "Low")
            m["synthesis_feasibility"] = band
            m["requires_expert_review"] = True
            summary.append(band)
        ctx.shared["feasibility_summary"] = summary
        highs = summary.count("High")
        out.output_summary = (
            f"Feasibility band assigned to {len(summary)} candidates (High={highs}). "
            "Score/complexity only — NO synthesis route, reagents, or conditions are produced (policy)."
        )
        out.rationale = "Feasibility is a coarse descriptor-complexity heuristic for prioritization; expert review is required."
        out.assumptions = ["Feasibility band is not a retrosynthesis result and implies nothing about a real route."]
        out.next_action = "Safety Auditor gate."
        out.confidence = self.compute_confidence(0.6, out)
        out.check("no_synthesis_route_emitted", True, "policy: routes withheld")
        return out
