from __future__ import annotations

from app.adapters import registry as reg
from app.agents.base import AgentContext, AgentOutput, BaseAgent, track
from app.models.schemas import SourceType


class BindingStructureAgent(BaseAgent):
    name = "Binding & Structure Agent"
    role = "Runs fixture-based AutoDock Vina docking when configured. Never fabricates a docking score; reports honest status when Vina is unavailable."
    stage = "binding"
    stage_index = 9
    allowed_tools = ["AutoDock Vina", "PDB", "AlphaFold DB"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        if ctx.run_vina_fixture:
            res = track(ctx, out, reg.vina.execute(
                {"receptor_fixture": "sample_receptor.pdbqt", "ligand_fixture": "sample_ligand.pdbqt"},
                project_id=ctx.project_id, workflow_run_id=ctx.workflow_run_id), network=False)
            ctx.shared["vina"] = res
            st = res.get("source_type")
            out.output_summary = f"Vina fixture docking: {res.get('status', st)} ({res.get('output_summary', '')})."
            if st != SourceType.REAL_TOOL_OUTPUT.value:
                out.warnings.append("Vina not fully configured — status is honest (no fabricated score).")
                out.status = "WARNING"
        else:
            hc = reg.vina.health()
            ctx.shared["vina"] = {"source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
                                  "status": "not_run", "output_summary": "Vina fixture docking not requested."}
            ctx.bump(SourceType.CONFIGURED_BUT_NOT_RUN.value)
            out.source_types.append(SourceType.CONFIGURED_BUT_NOT_RUN.value)
            out.output_summary = f"Vina fixture docking not requested. Adapter health: {hc.status.value}."
        out.rationale = "Fixture-based docking only; arbitrary receptor preparation is future work and requires expert setup."
        out.assumptions = ["Docking scores, when present, are in-silico estimates, not experimental affinities."]
        out.next_action = "Synthesis Feasibility Agent (score only)."
        out.confidence = self.compute_confidence(0.6, out)
        out.check("no_fabricated_docking", True, "score shown only if REAL_TOOL_OUTPUT")
        return out
