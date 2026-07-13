"""EGFR / NSCLC integration pipeline.

Runs the real-data pipeline end to end. Each step is isolated: a failing tool
records a TOOL_ERROR / CONFIGURED_BUT_NOT_RUN step and the pipeline continues
with partial results. Every step is audited. Real evidence, targets, and
molecules are persisted so the report is traceable.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.adapters import registry as reg
from app.models.schemas import SourceType, WorkflowRunResponse, WorkflowStepResult, utcnow
from app.services import audit
from app.storage import db

HUMAN_RESPONSIBILITY = (
    "This system is research decision support only. It does not replace expert "
    "scientific, clinical, regulatory, legal, or ethical review. Final "
    "responsibility belongs to the human research team."
)


def _step(name: str, tool: str, out: dict[str, Any]) -> WorkflowStepResult:
    return WorkflowStepResult(
        step=name, tool_name=tool,
        source_type=SourceType(out.get("source_type", SourceType.TOOL_ERROR.value)),
        status="ok" if out.get("source_type") == SourceType.REAL_TOOL_OUTPUT.value else out.get("status", out.get("source_type", "")),
        summary=out.get("output_summary", ""),
        audit_event_id=out.get("audit_event_id"),
        errors=out.get("errors", []),
    )


def _run_entity_id(prefix: str, run_id: str, source_id: Any) -> str:
    """Keep source identifiers recognizable without sharing ids across runs."""
    return f"{prefix}-{run_id}-{source_id}"


def run_pipeline(payload: dict[str, Any]) -> WorkflowRunResponse:
    project_id = payload.get("project_id") or f"proj-{uuid.uuid4().hex[:8]}"
    run_id = f"run-{uuid.uuid4().hex[:10]}"
    condition = payload.get("condition", "non-small cell lung cancer")
    target_query = payload.get("target_query", "EGFR")
    max_results = int(payload.get("max_results", 8))

    db.insert("projects", {"id": project_id, "created_at": utcnow(),
                           "name": f"{target_query} / {condition} pipeline", "condition": condition})
    started = utcnow()
    db.insert("workflow_runs", {"id": run_id, "project_id": project_id, "created_at": started,
                                "status": "running", "condition": condition, "target_query": target_query})
    audit.record_event(event_type="stage", agent_name="Project Orchestrator",
                       source_type=SourceType.REAL_TOOL_OUTPUT, project_id=project_id, workflow_run_id=run_id,
                       input_summary=f"{target_query} / {condition}", output_summary="Pipeline planning: 12-step DAG")

    steps: list[WorkflowStepResult] = []
    counts = {"REAL_TOOL_OUTPUT": 0, "DEMO_FALLBACK": 0, "CONFIGURED_BUT_NOT_RUN": 0, "TOOL_ERROR": 0}

    def track(name, tool, out):
        st = _step(name, tool, out)
        steps.append(st)
        counts[st.source_type.value] = counts.get(st.source_type.value, 0) + 1
        return out

    # 1. PubMed
    pm = track("evidence_mining", "PubMed",
               reg.pubmed.execute({"query": f"{target_query} {condition} resistance", "max_results": max_results},
                                  project_id=project_id, workflow_run_id=run_id))
    for it in pm.get("items", [])[:max_results]:
        db.insert("evidence_items", {"id": _run_entity_id("ev", run_id, it["pmid"]),
                                     "project_id": project_id, "workflow_run_id": run_id, "created_at": utcnow(),
                                     "source_name": "PubMed", "identifier": f"PMID:{it['pmid']}",
                                     "title": it["title"], "url": it["url"], "source_type": SourceType.REAL_TOOL_OUTPUT.value})

    # 2. ChEMBL targets
    ct = track("target_discovery", "ChEMBL",
               reg.chembl.execute({"operation": "targets", "query": target_query, "max_results": max_results},
                                  project_id=project_id, workflow_run_id=run_id))
    single_protein = None
    for t in ct.get("items", []):
        db.insert("target_candidates", {**t,
                                        "id": _run_entity_id("tgt", run_id, t.get("target_chembl_id")),
                                        "project_id": project_id, "workflow_run_id": run_id,
                                        "created_at": utcnow(), "source_type": SourceType.REAL_TOOL_OUTPUT.value})
        if single_protein is None and t.get("target_type") == "SINGLE PROTEIN":
            single_protein = t.get("target_chembl_id")
    target_id = single_protein or "CHEMBL203"  # EGFR single protein fallback id

    # 3. ChEMBL activities (real molecules with SMILES)
    acts = track("activity_lookup", "ChEMBL",
                 reg.chembl.execute({"operation": "activities", "target_chembl_id": target_id,
                                     "activity_type": "IC50", "max_results": max_results * 3},
                                    project_id=project_id, workflow_run_id=run_id))

    # 4. ClinicalTrials.gov
    trials = track("clinical_precedent", "ClinicalTrials.gov",
                   reg.clinicaltrials.execute({"condition": condition, "query": target_query, "max_results": max_results},
                                              project_id=project_id, workflow_run_id=run_id))

    # 5-7. Extract candidate SMILES + RDKit validate + descriptors
    seen = set()
    validated = 0
    for a in acts.get("items", []):
        smi = a.get("canonical_smiles")
        if not smi or smi in seen:
            continue
        seen.add(smi)
        if len(seen) > max_results:
            break
        rd = reg.rdkit.execute({"operation": "descriptors", "smiles": smi},
                               project_id=project_id, workflow_run_id=run_id)
        sf = reg.safety.execute({"smiles": smi, "label": a.get("molecule_chembl_id")},
                                project_id=project_id, workflow_run_id=run_id)
        if rd.get("valid"):
            validated += 1
        db.insert("molecule_candidates", {
            "id": _run_entity_id("mol", run_id, f"{a.get('molecule_chembl_id')}-{len(seen)}"),
            "project_id": project_id, "workflow_run_id": run_id, "created_at": utcnow(),
            "molecule_chembl_id": a.get("molecule_chembl_id"), "label": a.get("molecule_chembl_id"),
            "smiles": smi, "valid": rd.get("valid"), "descriptors": rd.get("descriptors"),
            "safety_status": sf.get("status"), "source_type": SourceType.REAL_TOOL_OUTPUT.value,
        })
    steps.append(WorkflowStepResult(step="structure_validation", tool_name="RDKit",
                                    source_type=SourceType(SourceType.REAL_TOOL_OUTPUT.value if reg_rdkit_ok() else SourceType.CONFIGURED_BUT_NOT_RUN.value),
                                    status="ok", summary=f"{validated}/{len(seen)} candidate SMILES validated by RDKit"))
    counts["REAL_TOOL_OUTPUT"] += 1 if reg_rdkit_ok() else 0

    # 8. TDC ADME dataset (evaluation grounding)
    tdc_out = track("admet_dataset", "TDC/PyTDC",
                    reg.tdc.execute({"dataset": "Caco2_Wang"}, project_id=project_id, workflow_run_id=run_id))
    if tdc_out.get("source_type") == SourceType.REAL_TOOL_OUTPUT.value:
        db.insert("tdc_dataset_records", {"id": f"tdc-{uuid.uuid4().hex[:6]}", "project_id": project_id,
                                          "workflow_run_id": run_id, "created_at": utcnow(),
                                          "dataset_name": tdc_out.get("dataset_name"),
                                          "task": tdc_out.get("task"), "row_count": tdc_out.get("row_count"),
                                          "split_summary": tdc_out.get("split_summary"),
                                          "source_type": SourceType.REAL_TOOL_OUTPUT.value})

    # 9. Vina fixture docking (optional)
    if payload.get("run_vina_fixture"):
        track("docking", "AutoDock Vina",
              reg.vina.execute({"receptor_fixture": "sample_receptor.pdbqt", "ligand_fixture": "sample_ligand.pdbqt"},
                               project_id=project_id, workflow_run_id=run_id))

    # 10. REINVENT4 config (optional)
    if payload.get("create_reinvent_config", True):
        rv = reg.reinvent.create_config({"target_name": target_query, "max_molecules": 100, "project_id": project_id})
        audit.record_tool_run(tool_name="REINVENT4", tool_category="chemistry",
                              source_type=SourceType(rv["source_type"]), input_summary=rv["input_summary"],
                              output_summary=rv["output_summary"], project_id=project_id, workflow_run_id=run_id)
        steps.append(_step("generative_config", "REINVENT4", rv))
        counts[rv["source_type"]] = counts.get(rv["source_type"], 0) + 1

    # 11. Safety gate over textual outputs
    sg = reg.safety.execute({"text": "high-level candidate prioritization for expert review", "label": "pipeline_output"},
                            project_id=project_id, workflow_run_id=run_id)
    steps.append(_step("safety_gate", "Safety", sg))

    # 12. Report
    rep = reg.report.generate(project_id, run_id, title=f"HelixForge — {target_query}/{condition} Pipeline Report")
    steps.append(WorkflowStepResult(step="report", tool_name="Report", source_type=SourceType.REAL_TOOL_OUTPUT,
                                    status="ok", summary=f"Report {rep['report_id']} generated"))

    completed = utcnow()
    db.insert("workflow_runs", {"id": run_id, "project_id": project_id, "created_at": started,
                                "status": "complete", "completed_at": completed, "condition": condition,
                                "target_query": target_query, "report_id": rep["report_id"], "counts": counts})

    return WorkflowRunResponse(
        run_id=run_id, project_id=project_id, status="complete", started_at=started, completed_at=completed,
        steps=steps, counts=counts, report_id=rep["report_id"], disclaimer=HUMAN_RESPONSIBILITY,
    )


def reg_rdkit_ok() -> bool:
    from app.adapters.rdkit_adapter import rdkit_available
    return rdkit_available()
