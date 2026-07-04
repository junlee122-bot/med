"""Agent engine — sequences the agentic pipeline over the real tool adapters.

Runs the orchestrator + 16 specialized agents, persisting an AgentPlan, one
AgentRun per stage, and RevisionEvents from the Critic. Tolerant of partial
failure: a raising agent is recorded as FAILED and the pipeline continues.
"""
from __future__ import annotations

import time
import traceback
import uuid
from typing import Any

from app.agents.base import AgentContext
from app.agents.orchestrator import OrchestratorAgent
from app.agents.disease_biology_agent import DiseaseBiologyAgent
from app.agents.evidence_miner_agent import EvidenceMinerAgent
from app.agents.citation_verifier_agent import CitationVerifierAgent
from app.agents.target_scout_agent import TargetScoutAgent
from app.agents.hypothesis_agent import HypothesisAgent
from app.agents.molecule_design_agent import MoleculeDesignAgent
from app.agents.cheminformatics_validator_agent import CheminformaticsValidatorAgent
from app.agents.admet_agent import AdmetAgent
from app.agents.binding_structure_agent import BindingStructureAgent
from app.agents.synthesis_feasibility_agent import SynthesisFeasibilityAgent
from app.agents.safety_auditor_agent import SafetyAuditorAgent
from app.agents.clinical_strategy_agent import ClinicalStrategyAgent
from app.agents.regulatory_reviewer_agent import RegulatoryReviewerAgent
from app.agents.critic_agent import CriticAgent
from app.agents.evaluation_agent import EvaluationAgent
from app.agents.report_builder_agent import ReportBuilderAgent
from app.models.schemas import SourceType, ValidationStatus, utcnow
from app.services import audit
from app.storage import db

AGENT_SEQUENCE = [
    DiseaseBiologyAgent, EvidenceMinerAgent, CitationVerifierAgent, TargetScoutAgent,
    HypothesisAgent, MoleculeDesignAgent, CheminformaticsValidatorAgent, AdmetAgent,
    BindingStructureAgent, SynthesisFeasibilityAgent, SafetyAuditorAgent,
    ClinicalStrategyAgent, RegulatoryReviewerAgent, CriticAgent, EvaluationAgent,
    ReportBuilderAgent,
]

HUMAN_RESPONSIBILITY = (
    "This system is research decision support only. It does not replace expert scientific, clinical, "
    "regulatory, legal, or ethical review. Final responsibility belongs to the human research team."
)


def _agent_run_record(agent, out, ctx, run_id, stage_index) -> dict[str, Any]:
    ts = utcnow()
    rec = {
        "id": f"ar-{run_id}-{stage_index}", "project_id": ctx.project_id, "created_at": ts,
        "workflow_run_id": run_id, "agent_name": agent.name, "agent_role": agent.role,
        "stage": agent.stage, "stage_index": stage_index, "status": out.status,
        "started_at": ts, "completed_at": ts,
        "input_summary": f"{ctx.target_query} / {ctx.condition}",
        "output_summary": out.output_summary, "rationale": out.rationale,
        "assumptions": out.assumptions, "uncertainty_notes": out.uncertainty_notes,
        "next_action": out.next_action, "tool_run_ids": out.tool_run_ids,
        "evidence_ids": out.evidence_ids, "molecule_ids": out.molecule_ids,
        "target_ids": out.target_ids, "validation_status": out.validation_status.value,
        "validation_checks": out.validation_checks, "confidence": out.confidence,
        "source_types": out.source_types, "warnings": out.warnings, "errors": out.errors,
        "is_revision": False,
    }
    db.insert("agent_runs", rec)
    audit.record_event(
        event_type="agent_run", agent_name=agent.name,
        source_type=SourceType.REAL_TOOL_OUTPUT if out.source_types and SourceType.REAL_TOOL_OUTPUT.value in out.source_types else SourceType.HUMAN_INPUT,
        input_summary=rec["input_summary"], output_summary=out.output_summary,
        project_id=ctx.project_id, workflow_run_id=run_id,
        validation_status=out.validation_status, confidence=out.confidence,
        warnings=out.warnings, errors=out.errors)
    return rec


def run_agentic_pipeline(payload: dict[str, Any]) -> dict[str, Any]:
    project_id = payload.get("project_id") or f"proj-{uuid.uuid4().hex[:8]}"
    run_id = f"arun-{uuid.uuid4().hex[:10]}"
    injections = payload.get("error_injections") or {}
    started = utcnow()
    t0 = time.time()

    ctx = AgentContext(
        project_id=project_id, workflow_run_id=run_id,
        condition=payload.get("condition", "non-small cell lung cancer"),
        target_query=payload.get("target_query", "EGFR"),
        max_results=int(payload.get("max_results", 8)),
        run_vina_fixture=bool(payload.get("run_vina_fixture", False)),
        create_reinvent_config=bool(payload.get("create_reinvent_config", True)),
        injections=injections,
    )
    ctx.shared["fake_citation_injected"] = bool(injections.get("fake_citation"))

    db.insert("projects", {"id": project_id, "created_at": started, "name": f"{ctx.target_query} / {ctx.condition} agentic",
                           "condition": ctx.condition})
    db.insert("workflow_runs", {"id": run_id, "project_id": project_id, "created_at": started, "status": "running",
                                "kind": "agentic", "condition": ctx.condition, "target_query": ctx.target_query})

    agent_runs: list[dict] = []

    # Stage 0 — Orchestrator (plan).
    orch = OrchestratorAgent()
    orch_out = orch.run(ctx)
    orch_rec = _agent_run_record(orch, orch_out, ctx, run_id, 0)
    agent_runs.append(orch_rec)
    plan = ctx.shared.get("plan", {})
    plan_rec = {"id": f"plan-{run_id}", "project_id": project_id, "created_at": started, "workflow_run_id": run_id,
                "objective": plan.get("objective", ""), "stages": plan.get("stages", []),
                "assigned_agents": plan.get("assigned_agents", []), "dependencies": plan.get("dependencies", []),
                "status": "created"}
    db.insert("agent_plans", plan_rec)

    # Optional injected tool failure (tolerated, honest).
    if injections.get("tool_failure"):
        ctx.shared["tool_failure_injected"] = "Simulated external tool outage"
        ctx.bump(SourceType.TOOL_ERROR.value)
        audit.record_tool_run(
            tool_name="Simulated Outage (injected)", tool_category="orchestration",
            source_type=SourceType.TOOL_ERROR, input_summary="simulated outage",
            output_summary="Tool returned TOOL_ERROR; orchestrator continues with partial results.",
            validation_status=ValidationStatus.FAILED, project_id=project_id, workflow_run_id=run_id,
            agent_name="Project Orchestrator", errors=["Injected TOOL_ERROR for self-correction demo"])

    # Sequential agents.
    for idx, AgentCls in enumerate(AGENT_SEQUENCE, start=1):
        agent = AgentCls()
        # Feed late-stage agents the running totals they need.
        if isinstance(agent, EvaluationAgent):
            ctx.shared["_agent_run_count"] = len(agent_runs)
            ctx.shared["_elapsed_s"] = time.time() - t0
        if isinstance(agent, ReportBuilderAgent):
            ctx.shared["_agent_runs_view"] = [
                {"agent_name": r["agent_name"], "stage": r["stage"], "status": r["status"],
                 "confidence": r["confidence"], "output_summary": r["output_summary"]}
                for r in agent_runs]
        try:
            out = agent.run(ctx)
        except Exception as exc:  # keep the pipeline alive on any agent failure
            from app.agents.base import AgentOutput
            out = AgentOutput(output_summary=f"{agent.name} failed: {exc}", status="FAILED",
                              validation_status=ValidationStatus.FAILED, errors=[str(exc)])
            out.check("agent_exception", False, traceback.format_exc().splitlines()[-1])
        rec = _agent_run_record(agent, out, ctx, run_id, idx)
        agent_runs.append(rec)

    # Persist revision events produced by the Critic.
    critic_run = next((r for r in agent_runs if r["agent_name"] == "Critic Agent"), None)
    revision_events = []
    for i, rv in enumerate(ctx.shared.get("revisions", []), start=1):
        orig = next((r for r in agent_runs if r["stage"] == rv.get("target_stage")), None)
        rec = {
            "id": f"rev-{run_id}-{i}", "project_id": project_id, "created_at": utcnow(), "workflow_run_id": run_id,
            "original_agent_run_id": orig["id"] if orig else None,
            "critic_agent_run_id": critic_run["id"] if critic_run else None,
            "reason_category": rv["reason_category"], "issue_summary": rv["issue_summary"],
            "action_taken": rv["action_taken"], "before_summary": rv["before_summary"],
            "after_summary": rv["after_summary"], "confidence_delta": rv["confidence_delta"],
        }
        db.insert("revision_events", rec)
        audit.record_event(event_type="revision", agent_name="Critic Agent", source_type=SourceType.HUMAN_INPUT,
                           input_summary=rv["issue_summary"], output_summary=rv["action_taken"],
                           project_id=project_id, workflow_run_id=run_id)
        revision_events.append(rec)

    metrics = ctx.shared.get("metrics", {})
    steps = [{"step": r["stage"], "agent": r["agent_name"], "status": r["status"],
              "source_type": (r["source_types"][0] if r["source_types"] else SourceType.HUMAN_INPUT.value),
              "summary": r["output_summary"]} for r in agent_runs]
    completed = utcnow()
    status = "complete"
    if any(r["status"] == "FAILED" for r in agent_runs):
        status = "warning"
    if ctx.shared.get("blocked_count"):
        status = "warning"

    db.insert("workflow_runs", {"id": run_id, "project_id": project_id, "created_at": started, "status": status,
                                "kind": "agentic", "completed_at": completed, "condition": ctx.condition,
                                "target_query": ctx.target_query, "counts": ctx.counts,
                                "report_id": ctx.shared.get("report_id"), "ko_report_id": ctx.shared.get("ko_report_id"),
                                "metrics": metrics, "revision_count": len(revision_events)})

    return {
        "run_id": run_id, "project_id": project_id, "status": status,
        "agent_runs": agent_runs, "plan": plan_rec, "steps": steps,
        "revision_events": revision_events, "counts": ctx.counts, "metrics": metrics,
        "report_id": ctx.shared.get("report_id"), "ko_report_id": ctx.shared.get("ko_report_id"),
        "disclaimer": HUMAN_RESPONSIBILITY,
    }


def run_error_injection_demo(scenario: str, condition: str, target_query: str) -> dict[str, Any]:
    """Run the agentic pipeline with a single injection toggled and surface the
    before/after of the correction it triggered."""
    toggles = {k: (k == scenario) for k in
               ("invalid_smiles", "fake_citation", "tool_failure", "safety_flag", "overclaim", "contradictory_evidence")}
    result = run_agentic_pipeline({
        "condition": condition, "target_query": target_query, "max_results": 6,
        "create_reinvent_config": False, "error_injections": toggles,
    })
    scenario_reason = {
        "invalid_smiles": "invalid_structure", "fake_citation": "fake_citation",
        "tool_failure": "tool_failure", "safety_flag": "safety_block",
        "overclaim": "overclaim", "contradictory_evidence": "contradictory_evidence",
    }.get(scenario, scenario)
    rev = next((r for r in result["revision_events"] if r["reason_category"] == scenario_reason), None)
    return {
        "scenario": scenario, "workflow_run_id": result["run_id"], "project_id": result["project_id"],
        "agent_runs": result["agent_runs"], "revision_events": result["revision_events"],
        "before": rev["before_summary"] if rev else "", "after": rev["after_summary"] if rev else "",
        "corrected": bool(rev), "metric_summary": result["metrics"], "report_id": result["report_id"],
        "disclaimer": HUMAN_RESPONSIBILITY,
    }
