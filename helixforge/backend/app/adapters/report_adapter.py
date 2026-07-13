"""Report adapter — builds a Markdown report from real persisted tool runs.

Reads ToolRun / AuditEvent / entity records from storage and assembles a report
whose every data point is traceable to a recorded tool call with its SourceType.
Includes the mandatory human-responsibility statement and safety policy. Never
includes synthesis routes or actionable hazardous content.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.adapters.base import ToolAdapter
from app.models.schemas import HealthStatus, SourceType, ToolHealth, ValidationStatus, utcnow
from app.storage import db

HUMAN_RESPONSIBILITY = (
    "This system is research decision support only. It does not replace expert "
    "scientific, clinical, regulatory, legal, or ethical review. Final "
    "responsibility belongs to the human research team."
)
NO_SYNTHESIS = ("Synthesis feasibility is summarized at a high level only. No reaction routes, "
                "reagents, conditions, or purification steps are produced by policy.")


class ReportAdapter(ToolAdapter):
    id = "report"
    name = "Report"
    category = "reporting"
    required_config: list[str] = []
    mode = "local"

    def health_check(self) -> ToolHealth:
        return ToolHealth(
            tool_id=self.id, name=self.name, category=self.category,
            status=HealthStatus.AVAILABLE, mode=self.mode,
            detail="Report builder ready (Markdown + JSON audit from real tool runs).",
            required_config=self.required_config,
        )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        rep = self.generate(payload.get("project_id"), payload.get("workflow_run_id"), payload.get("title"))
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.REAL_TOOL_OUTPUT.value,
            "input_summary": f"project={payload.get('project_id')}",
            "output_summary": f"Report {rep['report_id']} generated from {rep['json_audit']['tool_run_count']} tool runs.",
            "validation_status": ValidationStatus.PASSED.value,
            "report_id": rep["report_id"], "errors": [], "warnings": [],
        }

    def generate(self, project_id: Optional[str], workflow_run_id: Optional[str] = None,
                 title: Optional[str] = None) -> dict[str, Any]:
        title = title or "HelixForge AI — Integration Report"
        if workflow_run_id is not None:
            run = db.get("workflow_runs", workflow_run_id)
            if not run:
                raise ValueError(f"Run {workflow_run_id} not found")
            if run.get("project_id") != project_id:
                raise ValueError("workflow run does not belong to the requested project")

        def records(table: str, limit: int, order: str = "DESC") -> list[dict[str, Any]]:
            return db.list_records(
                table, project_id=project_id, workflow_run_id=workflow_run_id,
                limit=limit, order=order,
            )

        tool_runs = records("tool_runs", 500, "ASC")
        events = records("audit_events", 500, "ASC")
        evidence = records("evidence_items", 200)
        molecules = records("molecule_candidates", 200)
        targets = records("target_candidates", 50)
        docking = records("docking_jobs", 50)
        reinvent = records("reinvent_jobs", 50)
        tdc = records("tdc_dataset_records", 50)
        safety = records("safety_flags", 50)

        by_source: dict[str, int] = {}
        for tr in tool_runs:
            by_source[tr.get("source_type", "?")] = by_source.get(tr.get("source_type", "?"), 0) + 1

        md = [f"# {title}", ""]
        md.append(f"> **Generated:** {utcnow()}  ")
        md.append(f"> **Project:** {project_id or '(none)'}  ")
        md.append(f"> **Provenance:** every value below is traceable to a recorded tool call and labeled by SourceType.")
        md.append("")
        md.append("## 1. Tool Run Summary")
        md.append("| Provenance | Count |")
        md.append("|---|---|")
        for k in ["REAL_TOOL_OUTPUT", "DEMO_FALLBACK", "CONFIGURED_BUT_NOT_RUN", "TOOL_ERROR", "HUMAN_INPUT"]:
            md.append(f"| {k} | {by_source.get(k, 0)} |")
        md.append("")
        md.append("| Tool | Provenance | Summary |")
        md.append("|---|---|---|")
        for tr in tool_runs[-30:]:
            md.append(f"| {tr.get('tool_name')} | {tr.get('source_type')} | {str(tr.get('output_summary',''))[:80].replace('|','/')} |")
        md.append("")

        md.append("## 2. Evidence Items (PubMed / ClinicalTrials.gov / ChEMBL)")
        if evidence:
            md.append("| Source | Identifier | Title / Summary |")
            md.append("|---|---|---|")
            for e in evidence[:20]:
                md.append(f"| {e.get('source_name','')} | {e.get('identifier','')} | {str(e.get('title',''))[:70].replace('|','/')} |")
        else:
            md.append("_No evidence persisted for this project yet._")
        md.append("")

        md.append("## 3. Target Candidates (ChEMBL)")
        if targets:
            md.append("| ChEMBL ID | Name | Organism |")
            md.append("|---|---|---|")
            for t in targets[:15]:
                md.append(f"| {t.get('target_chembl_id','')} | {t.get('pref_name','')} | {t.get('organism','')} |")
        else:
            md.append("_No targets persisted yet._")
        md.append("")

        md.append("## 4. Molecule Candidates (RDKit-validated)")
        if molecules:
            md.append("| Label | Valid | MW | logP | QED | Lipinski | Safety |")
            md.append("|---|---|---|---|---|---|---|")
            for m in molecules[:25]:
                d = m.get("descriptors") or {}
                md.append(f"| {m.get('label', m.get('molecule_chembl_id',''))} | {m.get('valid', m.get('validity_status',''))} | "
                          f"{d.get('mol_weight','')} | {d.get('logp','')} | {d.get('qed','')} | "
                          f"{'pass' if d.get('lipinski_pass') else d.get('lipinski_violations','')} | {m.get('safety_status','')} |")
        else:
            md.append("_No molecule candidates persisted yet._")
        md.append("")

        md.append("## 5. TDC Dataset Usage (evaluation)")
        if tdc:
            for r in tdc[:6]:
                md.append(f"- **{r.get('dataset_name','')}** ({r.get('task','')}): {r.get('row_count','?')} rows, splits {r.get('split_summary',{})} — {r.get('source_type','')}")
        else:
            md.append("_No TDC dataset loaded in this run._")
        md.append("")

        md.append("## 6. Docking (AutoDock Vina)")
        if docking:
            for j in docking[:6]:
                md.append(f"- Job `{j.get('id')}`: status **{j.get('status')}**, provenance {j.get('source_type')}, scores {j.get('scores', [])}")
        else:
            md.append("_No docking job in this run._")
        md.append("")
        md.append("## 7. Generative Design (REINVENT4)")
        if reinvent:
            for j in reinvent[:6]:
                md.append(f"- Job `{j.get('id')}`: status **{j.get('status')}**, provenance {j.get('source_type')}, config `{j.get('config_path','')}`")
        else:
            md.append("_No REINVENT4 job in this run._")
        md.append("")

        md.append("## 8. Safety Audit")
        md.append(f"- Safety flags recorded: **{len(safety)}**")
        md.append(f"- {NO_SYNTHESIS}")
        for f in safety[:10]:
            md.append(f"  - {f.get('status')}: {f.get('entity_label','')} — {str(f.get('redacted_summary',''))[:90]}")
        md.append("")

        md.append("## 9. Limitations")
        md.append("- In-silico decision support only. `CONFIGURED_BUT_NOT_RUN` tools produced no results and are not estimated.")
        md.append("- Docking is fixture-based; arbitrary receptor preparation is future work.")
        md.append("- ADMET/toxicity require trained models; TDC provides datasets/benchmarks, not deployed predictions here.")
        md.append("")

        md.append("## 10. Safety Policy & Human Responsibility")
        md.append(f"> {HUMAN_RESPONSIBILITY}")
        md.append("")
        md.append(f"_{NO_SYNTHESIS} No medical, dosage, or regulatory advice is provided._")

        markdown = "\n".join(md)
        json_audit = {
            "project_id": project_id,
            "workflow_run_id": workflow_run_id,
            "generated_at": utcnow(),
            "tool_run_count": len(tool_runs),
            "provenance_counts": by_source,
            "audit_event_count": len(events),
            "evidence_count": len(evidence),
            "molecule_count": len(molecules),
            "target_count": len(targets),
            "safety_flag_count": len(safety),
            "disclaimer": HUMAN_RESPONSIBILITY,
        }
        report_id = f"rep-{uuid.uuid4().hex[:10]}"
        record = {
            "id": report_id, "project_id": project_id, "created_at": utcnow(),
            "workflow_run_id": workflow_run_id,
            "title": title, "markdown": markdown, "json_audit": json_audit,
        }
        db.insert("reports", record)
        return {"report_id": report_id, "title": title, "created_at": record["created_at"],
                "markdown": markdown, "json_audit": json_audit, "format": "markdown"}
