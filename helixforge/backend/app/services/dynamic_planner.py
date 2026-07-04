"""Hybrid dynamic planner.

Asks the LLM (when enabled) for a structured execution plan, validates it
deterministically against hard dependency + safety rules, and falls back to the
fixed deterministic plan if the LLM is unavailable or the plan is invalid/unsafe.
The fixed plan is always the safe default. No plan may add wet-lab, synthesis,
reagent, reaction-condition, or dosage stages.
"""
from __future__ import annotations

import json
import uuid
from typing import Any, Optional

from app.llm import call_llm
from app.llm.schemas import LLMCallPurpose
from app.models.schemas import utcnow
from app.storage import db

# The only stage_ids a plan may contain.
ALLOWED_STAGES = {
    "tool_health", "dynamic_plan", "evidence_mining", "chembl_target_search", "clinical_precedent",
    "target_selection", "evidence_grading", "hypothesis_reasoning", "chembl_activities",
    "rdkit_validation", "activity_normalization", "medchem_review", "applicability_domain",
    "pareto_analysis", "true_rediscovery", "optimization_loop", "safety_lint", "semantic_critic",
    "claim_inventory", "professional_review", "report_build", "hybrid_snapshot",
}
# Any stage_id/purpose containing these is rejected outright (safety).
FORBIDDEN_TOKENS = ["synthesis", "wet_lab", "wetlab", "wet lab", "dosage", "dosing",
                    "reaction_condition", "reaction condition", "reagent", "purification",
                    "medical_advice", "medical advice", "treatment_recommendation"]

DETERMINISTIC_STAGE_ORDER = [
    ("tool_health", "OrchestratorAgent", ["-"]),
    ("evidence_mining", "EvidenceMinerAgent", ["PubMed"]),
    ("chembl_target_search", "TargetScoutAgent", ["ChEMBL"]),
    ("clinical_precedent", "ClinicalStrategyAgent", ["ClinicalTrials.gov"]),
    ("target_selection", "TargetScoutAgent", ["ChEMBL"]),
    ("evidence_grading", "EvidenceMinerAgent", ["-"]),
    ("hypothesis_reasoning", "HypothesisAgent", ["-"]),
    ("chembl_activities", "MoleculeDesignAgent", ["ChEMBL"]),
    ("rdkit_validation", "CheminformaticsValidatorAgent", ["RDKit"]),
    ("activity_normalization", "MoleculeDesignAgent", ["-"]),
    ("medchem_review", "CheminformaticsValidatorAgent", ["RDKit"]),
    ("applicability_domain", "CheminformaticsValidatorAgent", ["RDKit"]),
    ("pareto_analysis", "MoleculeDesignAgent", ["-"]),
    ("safety_lint", "SafetyAuditorAgent", ["-"]),
    ("claim_inventory", "CriticAgent", ["-"]),
    ("professional_review", "EvaluationAgent", ["-"]),
    ("report_build", "ReportBuilderAgent", ["-"]),
]


def deterministic_plan(condition: str, target_query: str,
                       tools_health: Optional[dict] = None) -> dict[str, Any]:
    """The fixed, always-valid fallback plan."""
    stages = []
    for sid, agent, tools in DETERMINISTIC_STAGE_ORDER:
        stages.append({
            "stage_id": sid, "agent": agent, "purpose": f"deterministic {sid.replace('_', ' ')}",
            "required_tools": [t for t in tools if t != "-"], "optional_tools": [],
            "depends_on": [], "success_criteria": [], "failure_recovery": ["continue deterministically"],
            "safety_constraints": ["no wet-lab/synthesis/dosage content"], "budget_class": "low",
            "rationale_summary": "fixed deterministic stage",
        })
    return {
        "objective": f"Prioritize {target_query} candidates for {condition} (in-silico, expert review).",
        "strategy_summary": "Deterministic tool-grounded pipeline with safety + governance gates.",
        "mode": "DETERMINISTIC_ONLY", "selected_stages": stages, "skipped_stages": [],
        "replanning_triggers": ["target_not_found", "no_valid_molecules", "tool_failure",
                                "safety_block", "claim_lint_block"],
        "expected_artifacts": ["report", "evidence", "molecule_leaderboard"],
        "risks": ["external API outage tolerated with partial results"],
        "cost_guard": {"estimated_llm_calls": 0, "estimated_cost_usd": 0.0},
    }


def validate_plan(plan: dict[str, Any], tools_health: Optional[dict] = None) -> dict[str, Any]:
    """Deterministic plan validation. Returns {valid, errors, warnings, sanitized_plan}."""
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(plan, dict):
        return {"valid": False, "errors": ["plan is not an object"], "warnings": [], "sanitized_plan": None}
    stages = plan.get("selected_stages")
    if not isinstance(stages, list) or not stages:
        return {"valid": False, "errors": ["selected_stages missing/empty"], "warnings": [], "sanitized_plan": None}

    ids: list[str] = []
    for st in stages:
        sid = (st.get("stage_id") or "").strip()
        purpose = (st.get("purpose") or "").lower()
        blob = f"{sid} {purpose}".lower()
        if any(tok in blob for tok in FORBIDDEN_TOKENS):
            errors.append(f"forbidden stage rejected: '{sid}' (unsafe content)")
            continue
        if sid not in ALLOWED_STAGES:
            warnings.append(f"unknown stage '{sid}' dropped")
            continue
        ids.append(sid)

    def before(a: str, b: str) -> bool:
        """True unless both present and a is NOT before b."""
        if a in ids and b in ids:
            return ids.index(a) < ids.index(b)
        return True

    # Hard dependency rules.
    if not before("evidence_mining", "hypothesis_reasoning"):
        errors.append("evidence_mining must precede hypothesis_reasoning")
    if not before("target_selection", "chembl_activities"):
        errors.append("target_selection must precede molecule screening")
    if not before("rdkit_validation", "pareto_analysis"):
        warnings.append("rdkit_validation should precede molecule recommendation")
    if not before("safety_lint", "report_build"):
        errors.append("safety_lint must run before report_build")
    if not before("claim_inventory", "report_build"):
        warnings.append("claim_inventory should precede final report")
    if "hypothesis_reasoning" in ids and "evidence_grading" not in ids:
        warnings.append("LLM hypotheses used without evidence_grading stage")

    # Tool availability: mark Vina/REINVENT optional.
    for st in stages:
        req = st.get("required_tools") or []
        if any(t in ("AutoDock Vina", "Vina", "REINVENT4") for t in req):
            warnings.append(f"stage '{st.get('stage_id')}' lists Vina/REINVENT4 as required — treated as optional")

    sanitized = dict(plan)
    sanitized["selected_stages"] = [st for st in stages
                                    if (st.get("stage_id") in ALLOWED_STAGES
                                        and not any(tok in f"{st.get('stage_id','')} {st.get('purpose','')}".lower()
                                                    for tok in FORBIDDEN_TOKENS))]
    valid = not errors and bool(sanitized["selected_stages"])
    return {"valid": valid, "errors": errors, "warnings": warnings, "sanitized_plan": sanitized}


def _tools_summary(tools_health: Optional[dict]) -> str:
    if not tools_health:
        return "tool health unknown (assume PubMed/ChEMBL/ClinicalTrials/RDKit/TDC available; Vina/REINVENT4 configured-not-run)"
    return json.dumps(tools_health)[:600]


def plan_run(*, condition: str, target_query: str, scenario_id: str = "",
             mode: Optional[str] = None, tools_health: Optional[dict] = None,
             budget_usd: float = 2.0, safety_strictness: str = "presentation_safe",
             user_goals: str = "", previous_failures: Optional[list] = None,
             run_id: Optional[str] = None, project_id: Optional[str] = None,
             client: Any = None) -> dict[str, Any]:
    """Produce a validated plan. Uses the LLM if enabled; else the deterministic plan."""
    det = deterministic_plan(condition, target_query, tools_health)
    user_prompt = (
        f"Disease/condition: {condition}\nTarget query: {target_query}\nScenario: {scenario_id}\n"
        f"Tools health: {_tools_summary(tools_health)}\nBudget USD: {budget_usd}\n"
        f"Safety strictness: {safety_strictness}\nUser goals: {user_goals or 'standard in-silico prioritization'}\n"
        f"Previous failures: {previous_failures or 'none'}\n"
        "Produce the plan JSON per the schema."
    )
    res = call_llm(purpose=LLMCallPurpose.DYNAMIC_PLANNING, prompt_template_id="dynamic_planner",
                   user_prompt=user_prompt, required_keys=["objective", "selected_stages"],
                   list_keys=["selected_stages"], mode=mode, run_id=run_id, project_id=project_id,
                   client=client)

    plan_source = res.reasoning_source_type
    validation = {"valid": True, "errors": [], "warnings": [], "sanitized_plan": det}
    if res.ok and res.data:
        validation = validate_plan(res.data, tools_health)
        if validation["valid"]:
            plan = validation["sanitized_plan"]
        else:
            plan = det
            plan_source = "DETERMINISTIC_FALLBACK"
    else:
        plan = det

    plan_id = f"hplan-{uuid.uuid4().hex[:10]}"
    payload = {
        "id": plan_id, "run_id": run_id, "project_id": project_id, "created_at": utcnow(),
        "condition": condition, "target_query": target_query, "scenario_id": scenario_id,
        "requested_mode": mode, "plan_source": plan_source, "model": res.model,
        "llm_call_id": res.llm_call_id, "fallback_used": res.fallback_used,
        "fallback_reason": res.fallback_reason, "plan": plan,
        "validation": {k: validation[k] for k in ("valid", "errors", "warnings")},
        "deterministic_fallback_available": True,
    }
    try:
        db.insert("hybrid_plans", payload)
    except Exception:
        pass
    return payload


def get_plan(plan_id: str) -> Optional[dict]:
    return db.get("hybrid_plans", plan_id)


# ---- Replanning ----
def replan(*, run_id: str, failed_stage: str, failure_summary: str, condition: str,
           target_query: str, mode: Optional[str] = None, project_id: Optional[str] = None,
           client: Any = None) -> dict[str, Any]:
    """On a stage failure, ask the planner to revise if LLM is enabled+budgeted; else
    apply deterministic recovery. Records a ReplanEvent."""
    user_prompt = (
        f"A stage failed and the plan must be revised.\nCondition: {condition}\nTarget: {target_query}\n"
        f"Failed stage: {failed_stage}\nFailure summary: {failure_summary}\n"
        "Produce a revised plan JSON that recovers from this failure, per the schema."
    )
    res = call_llm(purpose=LLMCallPurpose.REPLANNING, prompt_template_id="dynamic_planner",
                   user_prompt=user_prompt, required_keys=["objective", "selected_stages"],
                   list_keys=["selected_stages"], mode=mode, run_id=run_id, project_id=project_id,
                   client=client)
    if res.ok and res.data:
        v = validate_plan(res.data)
        recovered_plan = v["sanitized_plan"] if v["valid"] else deterministic_plan(condition, target_query)
        source = res.reasoning_source_type if v["valid"] else "DETERMINISTIC_FALLBACK"
    else:
        recovered_plan = deterministic_plan(condition, target_query)
        source = "DETERMINISTIC_FALLBACK"

    event = {
        "id": f"replan-{uuid.uuid4().hex[:10]}", "run_id": run_id, "project_id": project_id,
        "created_at": utcnow(), "failed_stage": failed_stage, "failure_summary": failure_summary,
        "plan_source": source, "model": res.model, "recovery": "revised plan produced",
        "revised_stage_ids": [s.get("stage_id") for s in recovered_plan.get("selected_stages", [])],
    }
    try:
        db.insert("replan_events", event)
    except Exception:
        pass
    return {"replan_event": event, "revised_plan": recovered_plan, "plan_source": source}


def list_replans(run_id: str) -> list[dict]:
    return [r for r in db.list_records("replan_events", limit=500) if r.get("run_id") == run_id]
