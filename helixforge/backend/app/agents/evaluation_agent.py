from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.services import evaluation


class EvaluationAgent(BaseAgent):
    name = "Evaluation Agent"
    role = "Computes evaluation metrics from the observed run (tool integration, evidence integrity, molecule validity, agent autonomy, resource efficiency, retrospective rediscovery)."
    stage = "evaluation"
    stage_index = 15
    allowed_tools = ["EvalHarness (deterministic)"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        # agent_run_count / revision_count / elapsed are injected by the engine
        # via ctx.shared before this agent runs.
        agent_runs = ctx.shared.get("_agent_run_count", 0)
        revisions = len(ctx.shared.get("revisions", []))
        elapsed = ctx.shared.get("_elapsed_s", 0.0)
        metrics = evaluation.compute_metrics(ctx, agent_runs, revisions, elapsed)
        evaluation.persist_metrics(ctx.project_id, ctx.workflow_run_id, metrics)
        retro = evaluation.retrospective_success(metrics, ctx.target_query)
        metrics["retrospective"] = retro
        ctx.shared["metrics"] = metrics

        out.output_summary = (
            f"Metrics: {metrics['real_tool_output_count']} real-tool outputs, "
            f"citation verification {metrics['citation_verification_rate']}, "
            f"molecule validity {metrics['molecule_validity_rate']}, "
            f"{metrics['revision_event_count']} revisions, retrospective {retro['passed']}/{retro['total']}."
        )
        out.rationale = "All metrics are computed from observed pipeline state; none are fabricated."
        out.assumptions = ["Retrospective rediscovery is a sanity/retrieval benchmark, not wet-lab validation."]
        out.next_action = "Report Builder assembles EN + KO reports."
        out.confidence = self.compute_confidence(0.85, out)
        out.check("retrospective_target_top", retro["criteria"]["target_ranks_top"], metrics.get("top_target", ""))
        return out
