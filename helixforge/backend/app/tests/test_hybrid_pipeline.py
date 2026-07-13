"""Phase 7 — hybrid pipeline endpoint, hybrid snapshot/replay, rediscovery + optimization wiring."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import hybrid_pipeline, hybrid_snapshot
from app.storage import db

client = TestClient(app)


@pytest.mark.unit
def test_hybrid_pipeline_persists_run_scoped_plan_and_planner_call(monkeypatch):
    suffix = uuid.uuid4().hex[:8]
    run_id = f"hybrid-scope-run-{suffix}"
    project_id = f"hybrid-scope-project-{suffix}"

    def fake_backbone(_payload):
        db.insert("projects", {"id": project_id, "created_at": "2026-01-01T00:00:00Z"})
        db.insert("workflow_runs", {
            "id": run_id, "project_id": project_id,
            "created_at": "2026-01-01T00:00:00Z", "status": "complete",
        })
        return {"run_id": run_id, "project_id": project_id, "status": "complete",
                "agent_runs": []}

    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    monkeypatch.setattr(hybrid_pipeline.agent_engine, "run_agentic_pipeline", fake_backbone)
    monkeypatch.setattr(
        hybrid_pipeline.hypothesis_reasoner, "generate_hybrid",
        lambda **_kwargs: {
            "fallback_used": True, "reasoning_source_type": "DETERMINISTIC_FALLBACK",
            "hypotheses": [], "hypothesis_count": 0,
        },
    )
    result = hybrid_pipeline.run_hybrid_pipeline({
        "condition": "NSCLC", "target_query": "EGFR", "mode": "DETERMINISTIC_ONLY",
        "run_true_rediscovery": False, "run_optimization_loop": False,
        "run_semantic_critic": False,
    })

    plan = db.get("hybrid_plans", result["hybrid_plan_id"])
    assert plan["run_id"] == run_id
    assert plan["project_id"] == project_id
    planner_calls = [
        call for call in db.list_records("llm_calls", workflow_run_id=run_id)
        if call.get("purpose") == "DYNAMIC_PLANNING"
    ]
    assert planner_calls
    assert all(call.get("project_id") == project_id for call in planner_calls)


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
    db.insert("llm_calls", {
        "id": f"llm-secret-{uuid.uuid4().hex[:6]}", "run_id": rid, "project_id": pid,
        "created_at": "2026-02-01T00:00:01Z", "purpose": "SECRET_REDACTION_TEST",
        "reasoning_source_type": "REAL_LLM_OUTPUT", "data": {
            "nested": {"api_key": "must-not-survive", "safe": "ok"},
        }, "fallback_used": False,
    })
    snap = hybrid_snapshot.create_hybrid_snapshot(rid)
    blob = str(snap["hybrid_meta"])
    assert "must-not-survive" not in blob
    assert "***REDACTED***" in blob
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


@pytest.mark.integration
def test_hybrid_replay_preserves_fallback_source_label():
    rid, pid = _seed_min_run()
    db.insert("llm_calls", {
        "id": f"llm-fallback-{uuid.uuid4().hex[:6]}", "run_id": rid, "project_id": pid,
        "created_at": "2026-02-01T00:00:02Z", "purpose": "FALLBACK_TEST",
        "reasoning_source_type": "DETERMINISTIC_FALLBACK", "fallback_used": True,
        "input_hash": "sha256:fallback-input", "output_hash": "sha256:fallback-output",
        "data": {"fallback": True},
    })
    snap = hybrid_snapshot.create_hybrid_snapshot(rid)
    rep = hybrid_snapshot.replay_hybrid(snap["id"])
    fallback = next(c for c in rep["llm_reasoning_replay"] if c["purpose"] == "FALLBACK_TEST")
    assert fallback["reasoning_source_type"] == "DETERMINISTIC_FALLBACK"
    assert fallback["replayable"] is False


@pytest.mark.integration
def test_hybrid_replay_rejects_tampered_metadata():
    rid, _ = _seed_min_run()
    snap = hybrid_snapshot.create_hybrid_snapshot(rid)
    meta = db.get("snapshot_artifacts", f"hybmeta-{snap['id']}")
    meta["llm_calls"][0]["output_summary"] = "tampered"
    db.insert("snapshot_artifacts", meta)
    with pytest.raises(ValueError, match="checksum mismatch"):
        hybrid_snapshot.replay_hybrid(snap["id"])


# ---- Endpoints ----
@pytest.mark.integration
def test_rediscovery_and_optimization_endpoints():
    assert client.get("/api/rediscovery/scenarios").status_code == 200
    assert client.get("/api/rediscovery/comparators?scenario_id=egfr_nsclc").status_code == 200
    r = client.post("/api/optimization-loop/run", json={})
    assert r.status_code == 200


@pytest.mark.integration
@pytest.mark.live_api
@pytest.mark.slow
def test_hybrid_pipeline_endpoint_deterministic(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    r = client.post("/api/workflow/run-hybrid-agentic-pipeline",
                    json={"target_query": "EGFR", "condition": "NSCLC", "max_pubmed_results": 3,
                          "run_true_rediscovery": False, "run_optimization_loop": False,
                          "run_semantic_critic": False})
    assert r.status_code == 200
    assert r.json()["status"] in ("COMPLETE", "COMPLETE_WITH_WARNINGS")
