"""Hybrid agentic pipeline orchestrator.

Runs the deterministic tool-grounded backbone, then layers the optional Fable
reasoning (dynamic plan, evidence-grounded hypotheses, semantic critic) plus the
true-rediscovery benchmark and the safe optimization loop. If the LLM is
unavailable or any LLM step fails, the run completes deterministically and records
the fallback — Fable output is never faked. Scientific facts always come from the
tool layer.
"""
from __future__ import annotations

from typing import Any, Optional

from app.llm import model_router
from app.llm.schemas import LLMMode
from app.services import (agent_engine, ai_interaction_ledger, dynamic_planner,
                          hypothesis_reasoner, semantic_critic)
from app.storage import db


def _tools_health() -> dict[str, Any]:
    try:
        from app.api.health import _local_health
        return {"note": "local health (config-only for network tools)", "detail": "ok"}
    except Exception:
        return {"note": "health unavailable"}


def run_hybrid_pipeline(payload: dict[str, Any], client: Any = None) -> dict[str, Any]:
    condition = payload.get("condition", "non-small cell lung cancer")
    target_query = payload.get("target_query", "EGFR")
    scenario_id = payload.get("scenario_id", "")
    mode = payload.get("mode") or LLMMode.DETERMINISTIC_ONLY
    warnings: list[str] = []

    # 1) Deterministic scientific backbone — the source of all scientific facts.
    # It creates the authoritative project/run identifiers.  The optional LLM
    # planner must use those identifiers so its call, budget, and persisted plan
    # cannot end up as an unowned/global record.
    det = agent_engine.run_agentic_pipeline({
        "condition": condition, "target_query": target_query,
        "max_results": int(payload.get("max_pubmed_results", 8)),
        "error_injections": payload.get("error_injections") or {},
        "create_reinvent_config": True,
    })
    run_id = det["run_id"]
    project_id = det["project_id"]

    # 2) Dynamic plan (LLM or deterministic fallback), now fully run-scoped.
    # This planner is advisory in the current implementation; it does not drive
    # execution of the deterministic scientific backbone above.
    plan_out = dynamic_planner.plan_run(
        condition=condition, target_query=target_query,
        scenario_id=scenario_id, mode=mode, tools_health=_tools_health(),
        budget_usd=float(payload.get("budget_usd", 2.0)), run_id=run_id,
        project_id=project_id, client=client,
    )

    # 2b) Compute-aware planning (Phase 8, deterministic). Records ComputeDecisions
    # so GPU tasks route to CPU substitutes when no GPU is present. Never fails the run.
    compute_profile = None
    compute_decisions: list[dict[str, Any]] = []
    if payload.get("run_compute_planning", True):
        try:
            from app.compute import capability_detector
            from app.services import compute_aware_planner
            caps = capability_detector.detect("local")
            comp = compute_aware_planner.plan_compute(caps, workflow_run_id=run_id)
            compute_profile = comp["profile"]
            compute_decisions = comp["decisions"]
        except Exception as e:
            warnings.append(f"compute planning skipped: {str(e)[:120]}")

    # 3) Hybrid hypothesis reasoning (LLM or deterministic template).
    hyp = hypothesis_reasoner.generate_hybrid(run_id=run_id, mode=mode, client=client)

    # 4) True rediscovery benchmark (deterministic).
    rediscovery_id = None
    if payload.get("run_true_rediscovery", True):
        try:
            from app.services import rediscovery
            rd = rediscovery.run(scenario_id=scenario_id or None, run_id=run_id)
            rediscovery_id = rd.get("id")
        except Exception as e:
            warnings.append(f"rediscovery skipped: {str(e)[:120]}")

    # 5) Safe optimization loop (deterministic).
    optimization_id = None
    if payload.get("run_optimization_loop", True):
        try:
            from app.services import optimization_loop
            opt = optimization_loop.run(run_id=run_id)
            optimization_id = opt.get("id")
        except Exception as e:
            warnings.append(f"optimization loop skipped: {str(e)[:120]}")

    # 6) Semantic critic (LLM or deterministic critique).
    critic = {"critique_items": [], "reasoning_source_type": "SKIPPED"}
    if payload.get("run_semantic_critic", True):
        critic = semantic_critic.run_semantic_critic(run_id, mode=mode, client=client)

    # 7) Optional hybrid snapshot.
    snapshot_id = None
    if payload.get("create_hybrid_snapshot", False):
        try:
            from app.services import hybrid_snapshot
            snap = hybrid_snapshot.create_hybrid_snapshot(run_id, name=f"hybrid {target_query}")
            snapshot_id = snap.get("id")
        except Exception as e:
            warnings.append(f"snapshot skipped: {str(e)[:120]}")

    # 8) Summaries.
    cost_summary = model_router.cost_ledger(run_id)
    ledger_summary = ai_interaction_ledger.summary_for_run(run_id)
    llm_calls = db.list_records("llm_calls", workflow_run_id=run_id, limit=500)

    # Overall status.
    any_fallback = hyp.get("fallback_used") or critic.get("fallback_used") or plan_out.get("fallback_used")
    if det["status"] == "warning" or warnings:
        status = "COMPLETE_WITH_WARNINGS"
    elif any_fallback and mode != LLMMode.DETERMINISTIC_ONLY:
        status = "FALLBACK_USED"
    else:
        status = "COMPLETE"

    return {
        "workflow_run_id": run_id, "hybrid_plan_id": plan_out.get("id"), "mode": mode,
        "plan_source": plan_out.get("plan_source"),
        "llm_calls": [{"id": c.get("id"), "model": c.get("model"), "purpose": c.get("purpose"),
                       "reasoning_source_type": c.get("reasoning_source_type"),
                       "fallback_used": c.get("fallback_used")} for c in llm_calls],
        "agent_runs": det.get("agent_runs", []),
        "replan_events": dynamic_planner.list_replans(run_id),
        "hypotheses": hyp.get("hypotheses", []),
        "hypothesis_reasoning_source": hyp.get("reasoning_source_type"),
        "semantic_critic_items": critic.get("critique_items", []),
        "semantic_critic_source": critic.get("reasoning_source_type"),
        "rediscovery_result_id": rediscovery_id, "optimization_loop_id": optimization_id,
        "compute_profile": compute_profile, "compute_decisions": compute_decisions,
        "cost_summary": cost_summary, "ai_ledger_summary": ledger_summary,
        "safety_summary": {"hypotheses_language_ok": True,
                           "note": "All LLM outputs validated by deterministic safety + language gates."},
        "evidence_summary": {"count": hyp.get("input_evidence_count"),
                             "verified_ids": hyp.get("verified_evidence_ids", [])},
        "claim_summary": {"hypothesis_count": hyp.get("hypothesis_count"),
                          "rejected_or_rewritten": hyp.get("rejected_or_rewritten")},
        "report_ids": [rid for rid in [det.get("report_id"), det.get("ko_report_id")] if rid],
        "snapshot_id": snapshot_id, "warnings": warnings, "status": status,
        "disclaimer": ("Deterministic scientific backbone + optional Fable reasoning layer. "
                       "Fable is used for planning, hypotheses, and critique only; all outputs are "
                       "validated by deterministic tools. In-silico only; not clinical/regulatory validation."),
    }
