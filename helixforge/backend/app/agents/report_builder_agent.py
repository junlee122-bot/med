from __future__ import annotations

from app.agents.base import AgentContext, AgentOutput, BaseAgent
from app.models.schemas import SourceType, utcnow
from app.services import reporting
from app.services.safety_lint import lint_report
from app.storage import db


class ReportBuilderAgent(BaseAgent):
    name = "Report Builder"
    role = "Assembles the English technical report and Korean judge report from real run artifacts, then runs the safety lint before marking them export-ready."
    stage = "report_generation"
    stage_index = 16
    allowed_tools = ["Report"]

    def run(self, ctx: AgentContext) -> AgentOutput:
        out = AgentOutput()
        agent_runs = ctx.shared.get("_agent_runs_view", [])
        revisions = ctx.shared.get("revisions", [])
        metrics = ctx.shared.get("metrics", {})
        metrics["_counts"] = ctx.counts
        common = dict(run_id=ctx.workflow_run_id, project_id=ctx.project_id, condition=ctx.condition,
                      target_query=ctx.target_query, shared=ctx.shared, metrics=metrics,
                      agent_runs=agent_runs, revisions=revisions)

        en_md = reporting.build_en_report(**common)
        ko_md = reporting.build_ko_judge_report(**common)
        en_lint = lint_report(en_md)
        ko_lint = lint_report(ko_md)

        en_id = f"rep-en-{ctx.workflow_run_id}"
        ko_id = f"rep-ko-{ctx.workflow_run_id}"
        db.insert("reports", {"id": en_id, "project_id": ctx.project_id, "created_at": utcnow(),
                              "workflow_run_id": ctx.workflow_run_id, "type": "en_technical",
                              "title": f"HelixForge — {ctx.target_query}/{ctx.condition} Agentic Report (EN)",
                              "markdown": en_md, "language": "en", "safety_lint": en_lint,
                              "export_safe": en_lint["export_safe"], "source_type": SourceType.REAL_TOOL_OUTPUT.value})
        db.insert("reports", {"id": ko_id, "project_id": ctx.project_id, "created_at": utcnow(),
                              "workflow_run_id": ctx.workflow_run_id, "type": "ko_judge",
                              "title": f"HelixForge — 심사위원 리포트 (KO)", "markdown": ko_md,
                              "language": "ko", "safety_lint": ko_lint, "export_safe": ko_lint["export_safe"],
                              "source_type": SourceType.REAL_TOOL_OUTPUT.value})
        ctx.shared["report_id"] = en_id
        ctx.shared["ko_report_id"] = ko_id

        out.output_summary = (
            f"Generated EN technical report ({en_id}) and KO judge report ({ko_id}). "
            f"Safety lint: EN={en_lint['status']}, KO={ko_lint['status']}."
        )
        out.rationale = "Every claim links to an evidence ID or a labeled assumption/source type; both reports embed the human-responsibility statement."
        out.next_action = "Reports available for Markdown/JSON export."
        out.confidence = self.compute_confidence(0.85, out)
        out.check("en_export_safe", en_lint["export_safe"], en_lint["status"])
        out.check("ko_export_safe", ko_lint["export_safe"], ko_lint["status"])
        out.check("disclaimer_present", "responsibility" in en_md.lower() and "책임" in ko_md)
        if not en_lint["export_safe"] or not ko_lint["export_safe"]:
            out.status = "WARNING"
            out.warnings.append("A report failed the safety lint; export gated.")
        return out
