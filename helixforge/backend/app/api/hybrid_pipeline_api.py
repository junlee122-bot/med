from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import hybrid_pipeline, hybrid_snapshot
from app.services.optimization_loop import reinvent_bridge
from app.services.rediscovery import comparator_library, rediscovery_report
from app.storage import db

router = APIRouter(prefix="/api", tags=["hybrid-pipeline"])


# ---- Hybrid pipeline (§11) ----
class ErrorInjections(BaseModel):
    invalid_smiles: bool = False
    fake_citation: bool = False
    tool_failure: bool = False
    safety_flag: bool = False
    overclaim: bool = False
    contradictory_evidence: bool = False


class HybridPipelineRequest(BaseModel):
    condition: str = "non-small cell lung cancer"
    target_query: str = "EGFR"
    scenario_id: str = "egfr_nsclc"
    mode: str = "DETERMINISTIC_ONLY"
    max_pubmed_results: int = 8
    max_chembl_targets: int = 12
    max_chembl_activities: int = 50
    max_trials: int = 8
    run_true_rediscovery: bool = True
    run_optimization_loop: bool = True
    run_semantic_critic: bool = True
    create_hybrid_snapshot: bool = False
    budget_usd: float = 2.00
    safety_strictness: str = "presentation_safe"
    error_injections: ErrorInjections = ErrorInjections()


@router.post("/workflow/run-hybrid-agentic-pipeline")
def run_hybrid_agentic_pipeline(req: HybridPipelineRequest):
    payload = req.model_dump()
    payload["error_injections"] = req.error_injections.model_dump()
    return hybrid_pipeline.run_hybrid_pipeline(payload)


# ---- Hybrid snapshot + replay (§8) ----
@router.post("/snapshots/create-hybrid-from-run/{run_id}")
def snapshots_create_hybrid(run_id: str):
    if not db.get("workflow_runs", run_id):
        raise HTTPException(status_code=404, detail="run not found")
    return hybrid_snapshot.create_hybrid_snapshot(run_id)


@router.post("/snapshots/{snapshot_id}/replay-hybrid")
def snapshots_replay_hybrid(snapshot_id: str):
    try:
        return hybrid_snapshot.replay_hybrid(snapshot_id)
    except ValueError as exc:
        status = 409 if "checksum" in str(exc) else 404
        raise HTTPException(status_code=status, detail=str(exc)) from exc


@router.get("/snapshots/{snapshot_id}/llm-ledger")
def snapshots_llm_ledger(snapshot_id: str):
    try:
        return hybrid_snapshot.llm_ledger(snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/snapshots/{snapshot_id}/cost-summary")
def snapshots_cost_summary(snapshot_id: str):
    try:
        return hybrid_snapshot.cost_summary(snapshot_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


# ---- True rediscovery (§9) ----
class RediscoveryRequest(BaseModel):
    scenario_id: str | None = None
    run_id: str | None = None


@router.post("/rediscovery/run")
def rediscovery_run(req: RediscoveryRequest):
    from app.services import rediscovery
    try:
        return rediscovery.run(scenario_id=req.scenario_id, run_id=req.run_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/rediscovery/run/{result_id}")
def rediscovery_get(result_id: str):
    r = db.get("rediscovery_runs", result_id)
    if not r:
        raise HTTPException(status_code=404, detail="rediscovery result not found")
    return r


@router.get("/rediscovery/run/{result_id}/report")
def rediscovery_report_get(result_id: str):
    r = db.get("rediscovery_runs", result_id)
    if not r:
        raise HTTPException(status_code=404, detail="rediscovery result not found")
    return {"result_id": result_id, "markdown": rediscovery_report.build_report(r)}


@router.get("/rediscovery/comparators")
def rediscovery_comparators(scenario_id: str = "egfr_nsclc"):
    return comparator_library.get_comparators(scenario_id)


@router.get("/rediscovery/scenarios")
def rediscovery_scenarios():
    return {"scenarios": comparator_library.list_scenarios(),
            "library_valid": comparator_library.validate_library()}


# ---- Safe optimization loop (§10) ----
class OptimizationRequest(BaseModel):
    run_id: str | None = None
    target_id: str | None = None
    mode: str | None = None
    generations: int = 2


@router.post("/optimization-loop/run")
def optimization_loop_run(req: OptimizationRequest):
    from app.services import optimization_loop
    try:
        return optimization_loop.run(run_id=req.run_id, target_id=req.target_id,
                                     mode=req.mode, generations=req.generations)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/optimization-loop/run/{loop_id}")
def optimization_loop_get(loop_id: str):
    r = db.get("optimization_loop_runs", loop_id)
    if not r:
        raise HTTPException(status_code=404, detail="optimization loop run not found")
    return r


@router.get("/optimization-loop/run/{loop_id}/trace")
def optimization_loop_trace(loop_id: str):
    r = db.get("optimization_loop_runs", loop_id)
    if not r:
        raise HTTPException(status_code=404, detail="optimization loop run not found")
    return {"loop_id": loop_id, "generation_records": r.get("generation_records", []),
            "mode": r.get("mode"), "reinvent_status": reinvent_bridge.status()}


@router.get("/optimization-loop/run/{loop_id}/report")
def optimization_loop_report(loop_id: str):
    r = db.get("optimization_loop_runs", loop_id)
    if not r:
        raise HTTPException(status_code=404, detail="optimization loop run not found")
    lines = [f"# Tool-based Molecule Optimization Loop", "",
             f"Mode: **{r.get('mode')}** (SELECTION_LOOP = re-ranking existing candidates; "
             "LOCAL_HEURISTIC_GENERATION = in-silico analog suggestions; REINVENT4 = external, if configured).",
             f"Generations: {r.get('generations')}", "",
             "## What was actually run",
             f"- candidate_count_by_generation: {r.get('candidate_count_by_generation')}",
             f"- valid_count_by_generation: {r.get('valid_count_by_generation')}",
             f"- rejected_count_by_generation: {r.get('rejected_count_by_generation')}",
             f"- safety_block_count: {r.get('safety_block_count')}",
             f"- best_score_by_generation: {r.get('best_score_by_generation')}", "",
             f"Improvement: {r.get('improvement_summary')}", "",
             "## Limitations", ""]
    for lim in r.get("limitations", []):
        lines.append(f"- {lim}")
    lines += ["", "> In-silico candidate prioritization only. No synthesis routes, reaction conditions, "
              "reagents, or dosing. Not experimental validation. Final responsibility belongs to the human team."]
    return {"loop_id": loop_id, "markdown": "\n".join(lines)}
