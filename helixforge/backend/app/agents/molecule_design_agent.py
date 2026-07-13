from __future__ import annotations

from app.adapters import registry as reg
from app.agents.base import AgentContext, AgentOutput, BaseAgent, track
from app.models.schemas import SourceType


class MoleculeDesignAgent(BaseAgent):
    name = "Molecule Design Agent"
    role = "Imports real candidate molecules from ChEMBL activities for the selected target and, if configured, creates a REINVENT4 config. Never fabricates molecules."
    stage = "molecule_design"
    stage_index = 6
    allowed_tools = ["ChEMBL", "REINVENT4"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        target_id = ctx.shared.get("selected_target_id", "CHEMBL203")
        acts = track(ctx, out, reg.chembl.execute(
            {"operation": "activities", "target_chembl_id": target_id, "activity_type": "IC50",
             "max_results": ctx.max_results * 3},
            project_id=ctx.project_id, workflow_run_id=ctx.workflow_run_id), network=True)

        seen = set()
        raw = []
        for a in acts.get("items", []):
            smi = a.get("canonical_smiles")
            if not smi or smi in seen:
                continue
            seen.add(smi)
            if len(raw) >= ctx.max_results:
                break
            raw.append({
                "molecule_chembl_id": a.get("molecule_chembl_id"), "smiles": smi,
                "activity_type": a.get("activity_type") or a.get("standard_type"),
                "standard_value": a.get("standard_value"), "standard_units": a.get("standard_units"),
                "pchembl_value": a.get("pchembl_value"), "relation": a.get("standard_relation"),
                "source": "ChEMBL activity", "source_type": SourceType.REAL_TOOL_OUTPUT.value,
            })
        ctx.shared["molecules_raw"] = raw

        # REINVENT4 config (honest source_type — config real, run not executed here).
        rv = None
        if ctx.create_reinvent_config:
            rv = reg.reinvent.create_config({
                "target_name": ctx.target_query,
                "max_molecules": 100,
                "project_id": ctx.project_id,
                "workflow_run_id": ctx.workflow_run_id,
            })
            ctx.bump(rv["source_type"])
            ctx.shared["reinvent"] = rv
            out.source_types.append(rv["source_type"])

        out.molecule_ids = [r["molecule_chembl_id"] for r in raw if r.get("molecule_chembl_id")]
        out.output_summary = (
            f"Imported {len(raw)} real candidate molecules (ChEMBL activities for {target_id})"
            + (f"; REINVENT4 config {rv['source_type']}." if rv else ".")
        )
        out.rationale = "Real bioactive structures are used as the candidate pool; generative design is prepared via a real config but not run here."
        out.assumptions = ["ChEMBL activity molecules are comparators/starting points, not novel generated molecules."]
        out.next_action = "Cheminformatics Validator validates every SMILES."
        out.confidence = self.compute_confidence(0.8 if raw else 0.4, out)
        out.check("candidates_imported", len(raw) > 0, f"{len(raw)} candidates")
        if not raw:
            out.status = "WARNING"
            out.warnings.append("No ChEMBL activity structures available for the selected target.")
        return out
