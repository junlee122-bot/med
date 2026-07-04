"""Phase 7 — hybrid pipeline endpoint, hybrid snapshot/replay, rediscovery + optimization wiring."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import hybrid_pipeline, hybrid_snapshot
from app.storage import db

client = TestClient(app)


@pytest.mark.slow
@pytest.mark.integration
def test_hybrid_pipeline_no_key_completes_deterministic(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    out = hybrid_pipeline.run_hybrid_pipeline({
        "condition": "non-small cell lung cancer", "target_query": "EGFR",
        "scenario_id": "egfr_nsclc", "mode": "DETERMINISTIC_ONLY",
        "max_pubmed_results": 3, "run_true_rediscovery": True,
        "run_optimization_loop": True, "run_semantic_critic": True,
    })
    assert out["status"] in ("COMPLETE", "COMPLETE_WITH_WARNINGS")
    assert out["workflow_run_id"]
    assert out["plan_source"] == "DETERMINISTIC_FALLBACK"
    assert out["hypothesis_reasoning_source"] == "DETERMINISTIC_FALLBACK"
    # rediscovery + optimization wired
    assert out["optimization_loop_id"] is not None


@pytest.mark.slow
@pytest.mark.integration
def test_hybrid_pipeline_report_contains_llm_disclosure(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    out = hybrid_pipeline.run_hybrid_pipeline({
        "condition": "NSCLC", "target_query": "EGFR", "max_pubmed_results": 3,
        "run_true_rediscovery": False, "run_optimization_loop": False})
    assert "deterministic" in out["disclaimer"].lower()
    assert "ai_ledger_summary" in out
    assert out["ai_ledger_summary"]["llm_used"] in (True, False)


# ---- Hybrid snapshot / replay ----
def _seed_min_run():
    pid = f"proj-sn-{uuid.uuid4().hex[:6]}"
    rid = f"arun-sn-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {"id": rid, "project_id": pid, "created_at": "2026-02-01T00:00:00Z",
                                "kind": "agentic", "target_query": "EGFR", "condition": "NSCLC",
                                "status": "complete"})
    db.insert("evidence_items", {"id": f"ev-{uuid.uuid4().hex[:6]}", "project_id": pid,
                                 "created_at": "2026-02-01T00:00:00Z", "source_name": "PubMed",
                                 "source_type": "REAL_TOOL_OUTPUT", "verification_status": "VERIFIED"})
    # a recorded LLM call for this run
    db.insert("llm_calls", {"id": f"llm-{uuid.uuid4().hex[:6]}", "run_id": rid, "project_id": pid,
                            "created_at": "2026-02-01T00:00:00Z", "model": "claude-sonnet-5",
                            "provider": "anthropic", "purpose": "DYNAMIC_PLANNING",
                            "reasoning_source_type": "REAL_LLM_OUTPUT",
                            "input_hash": "sha256:abc", "output_hash": "sha256:def",
                            "input_summary": "plan", "output_summary": "a plan",
                            "data": {"objective": "x"}, "fallback_used": False,
                            "full_system_prompt": None, "full_user_prompt": None,
                            "tokens_in": 100, "tokens_out": 80, "actual_cost_usd": 0.01})
    return rid, pid


@pytest.mark.integration
def test_hybrid_snapshot_records_llm_metadata():
    rid, pid = _seed_min_run()
    snap = hybrid_snapshot.create_hybrid_snapshot(rid)
    meta = snap["hybrid_meta"]
    assert meta["is_hybrid"] is True
    assert meta["llm_call_count"] >= 1
    assert "claude-sonnet-5" in meta["models_used"]


@pytest.mark.integration
def test_hybrid_snapshot_excludes_secrets():
    rid, pid = _seed_min_run()
    snap = hybrid_snapshot.create_hybrid_snapshot(rid)
    blob = str(snap["hybrid_meta"])
    assert "full_system_prompt" not in str(snap["hybrid_meta"].get("llm_calls"))
    # no full prompt fields leaked into snapshot
    for c in snap["hybrid_meta"]["llm_calls"]:
        assert "full_user_prompt" not in c


@pytest.mark.integration
def test_hybrid_replay_no_api_calls():
    rid, pid = _seed_min_run()
    snap = hybrid_snapshot.create_hybrid_snapshot(rid)
    rep = hybrid_snapshot.replay_hybrid(snap["id"])
    assert rep["live_api_calls"] == 0
    assert rep["no_live_calls"] is True


@pytest.mark.integration
def test_hybrid_replay_labels_recorded_llm_output():
    rid, pid = _seed_min_run()
    snap = hybrid_snapshot.create_hybrid_snapshot(rid)
    rep = hybrid_snapshot.replay_hybrid(snap["id"])
    assert rep["recorded_llm_call_count"] >= 1
    assert all(c["reasoning_source_type"] == "RECORDED_LLM_OUTPUT" for c in rep["llm_reasoning_replay"])


# ---- Endpoints ----
@pytest.mark.integration
def test_rediscovery_and_optimization_endpoints():
    assert client.get("/api/rediscovery/scenarios").status_code == 200
    assert client.get("/api/rediscovery/comparators?scenario_id=egfr_nsclc").status_code == 200
    r = client.post("/api/optimization-loop/run", json={})
    assert r.status_code == 200


@pytest.mark.integration
def test_hybrid_pipeline_endpoint_deterministic(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    r = client.post("/api/workflow/run-hybrid-agentic-pipeline",
                    json={"target_query": "EGFR", "condition": "NSCLC", "max_pubmed_results": 3,
                          "run_true_rediscovery": False, "run_optimization_loop": False,
                          "run_semantic_critic": False})
    assert r.status_code == 200
    assert r.json()["status"] in ("COMPLETE", "COMPLETE_WITH_WARNINGS")
