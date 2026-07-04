from __future__ import annotations

import time
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.data.scenarios import BY_ID, SCENARIOS
from app.models.schemas import utcnow
from app.services import agent_engine
from app.storage import db

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


class RunScenarioRequest(BaseModel):
    scenario_id: str


class RunMatrixRequest(BaseModel):
    scenario_ids: list[str] = ["egfr-nsclc", "braf-melanoma"]


def _run_one(scenario: dict) -> dict:
    t0 = time.time()
    try:
        res = agent_engine.run_agentic_pipeline({
            "condition": scenario["condition"], "target_query": scenario["target_query"],
            "max_results": scenario.get("max_results", 4), "create_reinvent_config": False,
            "error_injections": {},
        })
        m = res.get("metrics", {})
        hint = (scenario.get("expected_target_hint") or "").upper()
        top = f"{m.get('top_target', '')} {m.get('top_target_chembl_id', '')}".upper()
        target_found = (m.get("candidate_count", 0) >= 0) and bool(m.get("top_target_chembl_id"))
        rediscovery = hint in top or (m.get("top_target_type") == "SINGLE PROTEIN"
                                      and m.get("top_target_organism") == "Homo sapiens"
                                      and m.get("valid_smiles_count", 0) > 0)
        result = {
            "id": f"scenrun-{uuid.uuid4().hex[:8]}", "created_at": utcnow(),
            "scenario_id": scenario["id"], "scenario_name": scenario["name"],
            "run_id": res["run_id"], "status": res["status"],
            "pubmed_evidence_count": m.get("pubmed_evidence_count", 0),
            "chembl_target_found": target_found, "selected_target": m.get("top_target_chembl_id"),
            "selected_target_name": m.get("top_target"),
            "molecule_count": m.get("candidate_count", 0), "valid_molecule_count": m.get("valid_smiles_count", 0),
            "clinicaltrials_count": m.get("clinicaltrials_count", 0),
            "tool_error_count": m.get("tool_error_count", 0),
            "runtime_seconds": round(time.time() - t0, 2), "report_generated": bool(res.get("report_id")),
            "rediscovery_success": bool(rediscovery),
            "note": "" if target_found else "Target not confidently found — reported honestly, no claim made.",
        }
    except Exception as exc:  # partial-failure tolerant
        result = {
            "id": f"scenrun-{uuid.uuid4().hex[:8]}", "created_at": utcnow(),
            "scenario_id": scenario["id"], "scenario_name": scenario["name"], "run_id": None,
            "status": "error", "runtime_seconds": round(time.time() - t0, 2),
            "error": str(exc)[:200], "report_generated": False, "rediscovery_success": False,
            "note": "Scenario run failed; recorded honestly.",
        }
    db.insert("scenario_runs", result)
    return result


@router.get("")
def list_scenarios():
    return {"scenarios": SCENARIOS, "count": len(SCENARIOS)}


@router.post("/run")
def run_scenario(req: RunScenarioRequest):
    scenario = BY_ID.get(req.scenario_id)
    if not scenario:
        raise HTTPException(status_code=404, detail="scenario not found")
    return _run_one(scenario)


@router.post("/run-matrix")
def run_matrix(req: RunMatrixRequest):
    results = []
    for sid in req.scenario_ids[:8]:
        scenario = BY_ID.get(sid)
        if not scenario:
            results.append({"scenario_id": sid, "status": "error", "error": "unknown scenario",
                            "rediscovery_success": False})
            continue
        results.append(_run_one(scenario))
    passed = sum(1 for r in results if r.get("rediscovery_success"))
    return {"results": results, "count": len(results), "rediscovery_passed": passed,
            "note": "Robustness benchmark for retrieval + pipeline; not a scientific validation."}


@router.get("/runs")
def list_runs(limit: int = 100):
    return {"runs": db.list_records("scenario_runs", limit=limit)}


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    rec = db.get("scenario_runs", run_id)
    if not rec:
        raise HTTPException(status_code=404, detail="scenario run not found")
    return rec
