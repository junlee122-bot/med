from __future__ import annotations

from app.adapters import registry as reg
from app.agents.base import AgentContext, AgentOutput, BaseAgent, track
from app.models.schemas import SourceType, utcnow
from app.services import scoring
from app.storage import db


class AdmetAgent(BaseAgent):
    name = "ADMET & Toxicology Agent"
    role = "Loads a real TDC ADME dataset as evaluation/training substrate and computes each candidate's composite prioritization score. Does not claim per-candidate ADMET prediction without a real model."
    stage = "admet_grounding"
    stage_index = 8
    allowed_tools = ["TDC/PyTDC", "RDKit descriptors"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        tdc = track(ctx, out, reg.tdc.execute(
            {"dataset": "Caco2_Wang"}, project_id=ctx.project_id, workflow_run_id=ctx.workflow_run_id), network=False)
        tdc_ready = tdc.get("source_type") == SourceType.REAL_TOOL_OUTPUT.value
        if tdc_ready:
            db.insert("tdc_dataset_records", {
                "id": f"tdc-{ctx.workflow_run_id}", "project_id": ctx.project_id, "created_at": utcnow(),
                "dataset_name": tdc.get("dataset_name"), "task": tdc.get("task"),
                "row_count": tdc.get("row_count"), "columns": tdc.get("columns"),
                "split_summary": tdc.get("split_summary"), "source_type": SourceType.REAL_TOOL_OUTPUT.value,
            })
        ctx.shared["tdc"] = tdc
        ctx.shared["tdc_ready"] = tdc_ready

        molecules = ctx.shared.get("molecules", [])
        scored = 0
        for m in molecules:
            if not m.get("valid"):
                m["composite_score"] = 0.0
                m["recommendation"] = "Reject — invalid structure"
                db.insert("molecule_candidates", m)
                continue
            activity = {"pchembl_value": m.get("pchembl_value")} if m.get("pchembl_value") else None
            inp = scoring.molecule_inputs_from_rdkit(
                {"valid": True, "descriptors": m.get("descriptors")}, activity,
                m.get("safety_status", "PASS"), tdc_ready, provenance=0.7)
            sc = scoring.score_molecule(inp)
            m["composite_score"] = sc["score"]
            m["recommendation"] = sc["recommendation"]
            m["score_breakdown"] = sc["breakdown"]
            m["score_warnings"] = sc["warnings"]
            db.insert("molecule_candidates", m)
            scored += 1
        molecules.sort(key=lambda x: (x.get("composite_score") or 0), reverse=True)
        for i, m in enumerate(molecules):
            m["rank"] = i + 1
        ctx.shared["molecules"] = molecules

        out.output_summary = (
            f"TDC {tdc.get('dataset_name', 'dataset')} loaded ({tdc.get('row_count', 0)} rows) as evaluation substrate; "
            f"scored {scored} valid candidates with the transparent composite score."
        )
        out.rationale = (
            "TDC dataset is loaded as an evaluation/training substrate (splits + size are real). No per-candidate ADMET "
            "prediction is claimed unless a trained model exists; the composite score aggregates QED/Lipinski/activity/"
            "druglikeness/provenance with safety and uncertainty penalties."
        )
        out.assumptions = ["TDC dataset grounds evaluation; it is not used here as a fitted predictor."]
        out.uncertainty_notes = "Composite score is a prioritization aid, not an efficacy prediction."
        out.next_action = "Binding & Structure Agent."
        out.confidence = self.compute_confidence(0.75, out)
        out.check("tdc_loaded", tdc_ready, tdc.get("output_summary", ""))
        out.check("candidates_scored", scored >= 0)
        return out
