"""Agentic-layer tests.

The run-dependent tests share ONE agentic pipeline run (module-scoped fixture)
to keep live-API usage bounded. They are marked live_api + slow so CI can skip
them; the scoring/lint unit tests (test_scoring.py) run offline.
"""
import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import agent_engine
from app.storage import db

client = TestClient(app)


@pytest.fixture(scope="module")
def agentic_run():
    return agent_engine.run_agentic_pipeline({
        "condition": "non-small cell lung cancer", "target_query": "EGFR", "max_results": 6,
        "create_reinvent_config": False,
        "error_injections": {"invalid_smiles": True, "fake_citation": True, "overclaim": True,
                             "tool_failure": True, "safety_flag": True, "contradictory_evidence": True},
    })


@pytest.mark.live_api
@pytest.mark.slow
def test_agent_engine_plan_created(agentic_run):
    assert agentic_run["plan"] and agentic_run["plan"]["stages"]
    assert db.get("agent_plans", agentic_run["plan"]["id"]) is not None


@pytest.mark.live_api
@pytest.mark.slow
def test_agent_run_persisted(agentic_run):
    assert len(agentic_run["agent_runs"]) >= 16
    first = agentic_run["agent_runs"][0]
    assert db.get("agent_runs", first["id"]) is not None


@pytest.mark.live_api
@pytest.mark.slow
def test_agentic_pipeline_partial_failure_tolerant(agentic_run):
    # A tool failure was injected; the pipeline must still complete all stages.
    assert agentic_run["status"] in ("complete", "warning")
    stages = {r["stage"] for r in agentic_run["agent_runs"]}
    assert "report_generation" in stages  # reached the end despite the injected outage


@pytest.mark.live_api
@pytest.mark.slow
def test_invalid_smiles_revision_event(agentic_run):
    cats = {r["reason_category"] for r in agentic_run["revision_events"]}
    assert "invalid_structure" in cats
    assert agentic_run["metrics"]["invalid_smiles_caught"] >= 1


@pytest.mark.live_api
@pytest.mark.slow
def test_fake_citation_revision_event(agentic_run):
    cats = {r["reason_category"] for r in agentic_run["revision_events"]}
    assert "fake_citation" in cats
    assert agentic_run["metrics"]["failed_citation_count"] >= 1


@pytest.mark.live_api
@pytest.mark.slow
def test_overclaim_revision_event(agentic_run):
    cats = {r["reason_category"] for r in agentic_run["revision_events"]}
    assert "overclaim" in cats


@pytest.mark.live_api
@pytest.mark.slow
def test_report_contains_disclaimer(agentic_run):
    rep = db.get("reports", agentic_run["report_id"])
    assert rep and "responsibility belongs to the human research team" in rep["markdown"].lower()
    ko = db.get("reports", agentic_run["ko_report_id"])
    assert ko and "책임은 연구자" in ko["markdown"]


@pytest.mark.live_api
@pytest.mark.slow
def test_report_does_not_mark_configured_but_not_run_as_real(agentic_run):
    from app.services.safety_lint import lint_report
    rep = db.get("reports", agentic_run["report_id"])
    res = lint_report(rep["markdown"])
    assert not any(f["category"] == "provenance" for f in res["findings"])


@pytest.mark.live_api
@pytest.mark.slow
def test_evaluation_summary_counts_source_types(agentic_run):
    m = agentic_run["metrics"]
    assert m["real_tool_output_count"] >= 1
    assert "configured_not_run_count" in m and "tool_error_count" in m
    r = client.get(f"/api/evaluation/runs/{agentic_run['run_id']}")
    assert r.status_code == 200
    assert r.json()["metrics_flat"]


@pytest.mark.live_api
@pytest.mark.slow
def test_export_bundle_contains_manifest(agentic_run):
    r = client.get(f"/api/export/run/{agentic_run['run_id']}")
    assert r.status_code == 200
    body = r.json()
    assert "manifest" in body and body["manifest"]["run_id"] == agentic_run["run_id"]
    assert "report_markdown" in body and body["agent_runs"]


@pytest.mark.integration
def test_tool_health_timeout_does_not_hang():
    t0 = time.time()
    r = client.get("/api/tools/health", params={"live": False, "timeout_seconds": 2})
    elapsed = time.time() - t0
    assert r.status_code == 200
    assert len(r.json()["tools"]) == 9
    # Per-tool 2s cap over 9 tools bounds worst case well under 30s.
    assert elapsed < 30


@pytest.mark.integration
def test_agents_catalog_endpoint():
    r = client.get("/api/agents")
    assert r.status_code == 200
    assert r.json()["count"] >= 16


@pytest.mark.integration
def test_safety_lint_endpoint_blocks_forbidden():
    r = client.post("/api/safety/lint-report", json={"markdown": "reaction conditions and reagent list here"})
    assert r.status_code == 200
    assert r.json()["status"] == "BLOCKED"
