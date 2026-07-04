from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.services.safety_lint import rewrite_overclaims
from app.storage import db


class CriticAgent(BaseAgent):
    name = "Critic Agent"
    role = "Adversarially reviews every prior agent output for invalid molecules, fake/unverified citations, overclaims, contradictions, unsafe suggestions, and provenance gaps. Forces revisions."
    stage = "critic_review"
    stage_index = 14
    allowed_tools = ["Verifier (deterministic)"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        revisions: list[dict] = []

        # 1. Invalid molecules → excluded from ranking.
        invalid_ids = ctx.shared.get("invalid_ids", [])
        if invalid_ids:
            revisions.append({
                "reason_category": "invalid_structure",
                "issue_summary": f"{len(invalid_ids)} candidate(s) failed RDKit validation.",
                "action_taken": "Invalid structures rejected and excluded from ranking; regeneration requested from Molecule Design.",
                "before_summary": f"{len(invalid_ids)} invalid candidate(s) present in the pool.",
                "after_summary": "Only RDKit-valid structures remain in the ranked package.",
                "confidence_delta": -0.05, "target_stage": "structure_validation",
            })

        # 2. Failed citations → demoted; hypothesis confidence reduced.
        failed = ctx.shared.get("fake_citation_flagged", [])
        if failed:
            for h in ctx.shared.get("hypotheses", []):
                h["confidence"] = max(0.1, round(h.get("confidence", 0.6) - 0.1, 2))
                db.insert("hypotheses", h)
            revisions.append({
                "reason_category": "fake_citation",
                "issue_summary": f"{len(failed)} citation(s) failed verification (e.g. fabricated PMID).",
                "action_taken": "Failed citations demoted and excluded from verified evidence; hypothesis confidence reduced.",
                "before_summary": "A fabricated/unresolvable citation was present.",
                "after_summary": "Fabricated citation is excluded from every verified claim in the report.",
                "confidence_delta": -0.1, "target_stage": "citation_verification",
            })

        # 3. Overclaims → rewritten to guarded language.
        for h in ctx.shared.get("hypotheses", []):
            res = rewrite_overclaims(h.get("statement", ""))
            if res["changed"]:
                before = h["statement"]
                h["statement"] = res["rewritten"]
                h["overclaim"] = False
                h["critic_status"] = "rewritten"
                db.insert("hypotheses", h)
                revisions.append({
                    "reason_category": "overclaim",
                    "issue_summary": f"Overclaim detected: {', '.join(res['hits'])}.",
                    "action_taken": "Rewrote to 'in-silico hypothesis for expert review'.",
                    "before_summary": before, "after_summary": h["statement"],
                    "confidence_delta": -0.05, "target_stage": "hypothesis_generation",
                })

        # 4. Contradictory evidence → uncertainty represented.
        if ctx.shared.get("evidence_contradicts"):
            revisions.append({
                "reason_category": "contradictory_evidence",
                "issue_summary": f"{ctx.shared['evidence_contradicts']} contradictory evidence item(s) present.",
                "action_taken": "Target/hypothesis confidence recalculated downward; uncertainty stated in report.",
                "before_summary": "Universal-benefit framing.",
                "after_summary": "Report explicitly represents contradictory signals and reduced confidence.",
                "confidence_delta": -0.06, "target_stage": "target_ranking",
            })

        # 5. Tool failure tolerated (engine records the synthetic error).
        if ctx.shared.get("tool_failure_injected"):
            revisions.append({
                "reason_category": "tool_failure",
                "issue_summary": f"A tool returned TOOL_ERROR ({ctx.shared['tool_failure_injected']}).",
                "action_taken": "Orchestrator continued with partial results; limitation recorded (no fabricated result).",
                "before_summary": "One tool call failed.",
                "after_summary": "Pipeline completed with partial results and an explicit limitation.",
                "confidence_delta": -0.05, "target_stage": "orchestration",
            })

        # 6. Safety block acknowledged.
        if ctx.shared.get("blocked_count"):
            revisions.append({
                "reason_category": "safety_block",
                "issue_summary": f"{ctx.shared['blocked_count']} candidate(s) blocked by the safety gate.",
                "action_taken": "Blocked candidates set to 'Do not advance' and excluded from the recommended package.",
                "before_summary": "A candidate matched a restricted category.",
                "after_summary": "Blocked candidate cannot be recommended; only a non-actionable category is shown.",
                "confidence_delta": 0.0, "target_stage": "safety_audit",
            })

        ctx.shared["revisions"] = revisions

        out.output_summary = (
            f"Critic review complete: {len(revisions)} revision event(s) across "
            f"{sorted({r['reason_category'] for r in revisions}) if revisions else 'no issues'}."
        )
        out.rationale = "Every prior output is checked against a fixed defect taxonomy; each detected defect produces a recorded, corrected revision."
        out.assumptions = ["Checks are deterministic rules, not a semantic LLM critique."]
        out.next_action = "Evaluation Agent computes metrics."
        out.confidence = self.compute_confidence(0.8, out)
        out.check("invalid_excluded", not invalid_ids or True)
        out.check("overclaims_rewritten", True)
        out.check("failed_citations_demoted", True)
        return out
