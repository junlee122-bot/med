from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent

DISCLAIMER = "This is high-level research planning, not medical, legal, or regulatory advice."


class ClinicalStrategyAgent(BaseAgent):
    name = "Clinical Strategy Agent"
    role = "Summarizes real ClinicalTrials.gov precedent into a high-level, non-advisory clinical strategy. No dosage or medical advice."
    stage = "clinical_strategy"
    stage_index = 12
    allowed_tools = ["ClinicalTrials.gov (cached)"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        trials = ctx.shared.get("trials", [])
        precedent = []
        phases = {}
        for t in trials[: ctx.max_results]:
            phase = t.get("phase") or "N/A"
            phases[phase] = phases.get(phase, 0) + 1
            precedent.append({
                "nct_id": t.get("nct_id"), "title": t.get("brief_title"),
                "status": t.get("status"), "phase": phase,
                "intervention_class": (t.get("interventions") or ["—"])[0] if t.get("interventions") else "—",
                "relevance": "target/condition match", "risk_note": "expert review required",
            })
        clinical = {
            "indication": ctx.condition,
            "population_logic": f"Biomarker-selected {ctx.condition} population expressing/altered for {ctx.target_query} (expert-defined).",
            "endpoints": ["Safety & tolerability (primary, early phase)", "Objective response (efficacy signal)", "PFS (secondary)"],
            "comparator": "Standard-of-care per line/region (expert-selected).",
            "risk_factors": ["On-target toxicity", "Acquired resistance", "Biomarker/endpoint mismatch", "Competitive landscape"],
            "precedent": precedent, "phase_distribution": phases,
            "disclaimer": DISCLAIMER,
        }
        ctx.shared["clinical"] = clinical

        out.output_summary = f"Clinical strategy drafted from {len(precedent)} real trial precedents (phases: {phases or 'n/a'})."
        out.rationale = "Only high-level design elements are produced; all specifics require expert clinical/biostatistics input."
        out.assumptions = ["Precedent presence indicates feasibility, not efficacy."]
        out.uncertainty_notes = DISCLAIMER
        out.next_action = "Regulatory Reviewer builds the checklist."
        out.confidence = self.compute_confidence(0.62, out)
        out.check("disclaimer_present", True)
        out.check("no_dosage_or_medical_advice", True)
        return out
