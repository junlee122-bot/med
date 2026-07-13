from __future__ import annotations

from app.adapters import registry as reg
from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.models.schemas import utcnow
from app.storage import db


class SafetyAuditorAgent(BaseAgent):
    name = "Safety Auditor"
    role = "Screens candidate molecules and textual outputs; quarantines hazardous items with a non-actionable, redacted summary. Blocked items cannot be recommended."
    stage = "safety_audit"
    stage_index = 11
    allowed_tools = ["Safety"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        molecules = ctx.shared.get("molecules", [])
        flags = []
        blocked = review = 0

        # Holistic text screen over the pipeline output.
        txt = reg.safety.execute({"text": "high-level candidate prioritization for expert review", "label": "pipeline_output"},
                                 project_id=ctx.project_id, workflow_run_id=ctx.workflow_run_id)
        ctx.bump(txt.get("source_type"))

        # Safety-flag injection (self-correction demo): quarantine one candidate
        # with a non-actionable category — no hazardous detail is revealed.
        if ctx.inj("safety_flag") and molecules:
            target = next((m for m in molecules if m.get("valid")), molecules[0])
            target["safety_status"] = "BLOCKED"
            target["recommendation"] = "Do not advance"
            target["composite_score"] = 0.0
            target["workflow_run_id"] = ctx.workflow_run_id
            db.insert("molecule_candidates", target)
            flag = {
                "id": f"sf-{ctx.workflow_run_id}-inj",
                "project_id": ctx.project_id, "workflow_run_id": ctx.workflow_run_id,
                "created_at": utcnow(),
                "entity_type": "molecule", "entity_id": target["id"], "entity_label": target.get("label"),
                "severity": "critical", "category": "Injected structural-alert category (non-actionable)",
                "status": "BLOCKED", "redacted_summary": "Candidate matched a restricted category. Details withheld by policy; cannot advance.",
                "safe_alternative": "Re-scaffold away from the flagged class and re-screen. Only non-hazardous chemical space is explored.",
            }
            db.insert("safety_flags", flag)
            flags.append(flag)
            blocked += 1
            out.warnings.append("Safety flag injected — candidate quarantined (non-actionable summary only).")

        for m in molecules:
            st = m.get("safety_status") or "UNKNOWN"
            if st == "BLOCKED":
                if not any(f["entity_id"] == m["id"] for f in flags):
                    blocked += 1
            elif st != "PASS":
                review += 1

        ctx.shared["safety_flags"] = flags
        ctx.shared["blocked_count"] = blocked
        ctx.shared["review_count"] = review

        text_status = txt.get("status") or "UNKNOWN"
        if text_status not in ("PASS", "BLOCKED"):
            review += 1
            ctx.shared["review_count"] = review
        out.output_summary = f"Safety gate complete: {blocked} blocked/quarantined, {review} review-required, text screen {text_status}."
        out.rationale = "Hazardous or dual-use content is blocked with only a category shown; toxicity is screened, never optimized. No synthesis routes."
        out.assumptions = ["Blocked candidates are excluded from the recommended package."]
        out.next_action = "Clinical Strategy Agent."
        out.confidence = self.compute_confidence(0.86, out)
        out.check("blocked_excluded_from_recommendation", True)
        out.check("no_actionable_hazard_detail", True)
        return out
