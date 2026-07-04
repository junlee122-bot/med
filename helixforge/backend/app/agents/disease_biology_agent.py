from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent


class DiseaseBiologyAgent(BaseAgent):
    name = "Disease Biology Agent"
    role = "Frames high-level disease context and the evidence-search strategy. Does not fabricate biological claims."
    stage = "disease_modeling"
    stage_index = 1
    allowed_tools = ["PubMed (query design)"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        query = f"{ctx.target_query} {ctx.condition} resistance"
        ctx.shared["pubmed_query"] = query
        ctx.shared["disease_context"] = (
            f"{ctx.condition} is framed here as the indication; {ctx.target_query} is the candidate target of interest. "
            "This agent only sets scope and the literature-search strategy — all biological claims must come from "
            "retrieved public evidence downstream."
        )
        out.output_summary = (
            f"Scoped indication '{ctx.condition}' with target hypothesis '{ctx.target_query}'. "
            f"PubMed search strategy: \"{query}\"."
        )
        out.rationale = (
            "Framing the indication and a precise query up front lets the Evidence Miner retrieve relevant, "
            "verifiable literature rather than broad, noisy results."
        )
        out.assumptions = [
            "Disease context is a scoping artifact, not a validated biological model.",
            "All downstream claims must be backed by retrieved evidence IDs or marked as assumptions.",
        ]
        out.uncertainty_notes = "No biological assertions are made at this stage; scope only."
        out.next_action = "Evidence Miner retrieves literature for the query."
        out.confidence = 0.8
        out.check("query_defined", bool(query))
        return out
