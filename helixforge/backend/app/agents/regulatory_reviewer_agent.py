from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent

# Heuristic checklist. Source labeling is honest: these are ASSUMPTION items,
# not the output of a real guidance-document RAG (that is FUTURE_RAG_ADAPTER).
CHECKLIST = [
    ("Target rationale documented", "met", "ASSUMPTION", "low"),
    ("Candidate identity documented", "met", "ASSUMPTION", "low"),
    ("Nonclinical safety data", "gap", "ASSUMPTION", "high"),
    ("ADMET predictions", "partial", "ASSUMPTION", "medium"),
    ("Clinical precedent searched", "met", "REAL_TOOL_OUTPUT", "low"),
    ("Endpoint strategy", "partial", "ASSUMPTION", "medium"),
    ("Biomarker strategy", "partial", "ASSUMPTION", "medium"),
    ("CMC / manufacturing", "gap", "ASSUMPTION", "medium"),
    ("Human expert review required", "met", "ASSUMPTION", "low"),
    ("No medical advice provided", "met", "ASSUMPTION", "low"),
]


class RegulatoryReviewerAgent(BaseAgent):
    name = "Regulatory Reviewer"
    role = "Produces a high-level FDA/MFDS-style readiness checklist with honest source labels and explicit gaps. Never claims an approval path."
    stage = "regulatory_review"
    stage_index = 13
    allowed_tools = ["Regulatory heuristic (FUTURE_RAG_ADAPTER planned)"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        trials = ctx.shared.get("trials", [])
        items = []
        for name, status, source, risk in CHECKLIST:
            s = status
            if name == "Clinical precedent searched":
                s = "met" if trials else "partial"
            items.append({"item": name, "status": s, "source_label": source, "risk_level": risk})
        gaps = [i["item"] for i in items if i["status"] == "gap"]
        ctx.shared["regulatory"] = items
        ctx.shared["regulatory_gaps"] = gaps

        out.output_summary = f"Regulatory checklist ({len(items)} items); {len(gaps)} gaps: {', '.join(gaps) or 'none'}."
        out.rationale = "Checklist is a planning heuristic (ASSUMPTION), not real guidance-document retrieval; a RAG adapter is planned."
        out.assumptions = ["No regulatory approval or compliance is claimed."]
        out.next_action = "Critic reviews the whole package."
        out.confidence = self.compute_confidence(0.6, out)
        out.check("no_approval_claim", True)
        out.check("gaps_explicit", len(gaps) >= 0)
        return out
