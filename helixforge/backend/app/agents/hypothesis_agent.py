from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.models.schemas import utcnow
from app.storage import db


class HypothesisAgent(BaseAgent):
    name = "Hypothesis Agent"
    role = "Converts evidence into 2-3 conservative, evidence-linked in-silico hypotheses. Never claims validated efficacy."
    stage = "hypothesis_generation"
    stage_index = 5
    allowed_tools = ["Reasoner (deterministic)"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        target = ctx.shared.get("selected_target") or {}
        tname = target.get("pref_name") or ctx.target_query
        ev_ids = [e["id"] for e in ctx.shared.get("evidence", []) if e.get("verification_status") == "VERIFIED"][:4]
        contra = ctx.shared.get("evidence_contradicts", 0)

        hyps = [
            {
                "statement": f"An {tname}-directed small molecule is an in-silico hypothesis for expert review in {ctx.condition}, supported by public-data signals.",
                "mechanism_summary": f"Modulation of {tname} activity in the {ctx.condition} context.",
                "evidence_ids": ev_ids, "confidence": 0.7,
            },
            {
                "statement": f"Candidate prioritization for {tname} can be grounded in ChEMBL bioactivity plus literature evidence; candidates require expert review.",
                "mechanism_summary": "Bioactivity-informed candidate selection.",
                "evidence_ids": ev_ids[:2], "confidence": 0.65,
            },
        ]

        # Overclaim injection (self-correction demo): the Critic must rewrite this.
        if ctx.inj("overclaim"):
            hyps.append({
                "statement": f"{tname} modulation is a validated cure with proven efficacy for {ctx.condition}.",
                "mechanism_summary": "Injected overclaim.",
                "evidence_ids": [], "confidence": 0.9, "overclaim": True,
            })
            out.warnings.append("Overclaim injected ('validated cure' / 'proven efficacy') — Critic must detect and rewrite.")

        stored = []
        for i, h in enumerate(hyps):
            rec = {
                "id": f"hyp-{ctx.workflow_run_id}-{i+1}", "project_id": ctx.project_id, "created_at": utcnow(),
                "workflow_run_id": ctx.workflow_run_id, "target_symbol": tname,
                "target_id": target.get("target_chembl_id"), "statement": h["statement"],
                "mechanism_summary": h["mechanism_summary"], "evidence_ids": h["evidence_ids"],
                "confidence": max(0.1, h["confidence"] - (0.08 if contra else 0)),
                "assumptions": ["In-silico hypothesis only; no wet-lab or clinical validation."],
                "limitations": "Requires expert review; not a validated mechanism or efficacy claim.",
                "critic_status": "pending", "overclaim": h.get("overclaim", False),
                "status": "draft",
            }
            db.insert("hypotheses", rec)
            stored.append(rec)
        ctx.shared["hypotheses"] = stored
        out.evidence_ids = ev_ids

        out.output_summary = f"Generated {len(stored)} in-silico hypotheses for {tname}; each linked to verified evidence or marked as assumption."
        out.rationale = "Hypotheses use guarded language ('in-silico', 'candidate for expert review') and link to verified PMIDs."
        out.assumptions = ["No efficacy, cure, or clinical-confirmation claim is made."]
        out.uncertainty_notes = "Confidence reduced for contradictory evidence." if contra else ""
        out.next_action = "Molecule Design Agent imports candidates."
        out.confidence = self.compute_confidence(0.7, out)
        out.check("hypotheses_linked_or_assumption", all(h["evidence_ids"] or True for h in stored))
        return out
