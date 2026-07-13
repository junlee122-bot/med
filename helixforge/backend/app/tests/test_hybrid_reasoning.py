"""Phase 7 — hybrid planner, evidence-grounded hypothesis reasoner, semantic critic.
Offline: FakeLLMClient injected; deterministic fallback covered."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import dynamic_planner, hypothesis_reasoner, semantic_critic
from app.storage import db
from app.tests.fakes.fake_llm_client import FakeLLMClient

client = TestClient(app)
DEV = "HYBRID_LLM_DEV"


def _seed_run(target="EGFR", condition="non-small cell lung cancer", with_evidence=True,
              verified=True, with_molecule=False):
    pid = f"proj-hy-{uuid.uuid4().hex[:6]}"
    rid = f"arun-hy-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {"id": rid, "project_id": pid, "created_at": "2026-02-01T00:00:00Z",
                                "kind": "agentic", "target_query": target, "condition": condition})
    ev_id = None
    if with_evidence:
        ev_id = f"ev-{uuid.uuid4().hex[:6]}"
        db.insert("evidence_items", {"id": ev_id, "project_id": pid, "workflow_run_id": rid,
                                     "created_at": "2026-02-01T00:00:00Z",
                                     "source_name": "PubMed", "source_type": "REAL_TOOL_OUTPUT",
                                     "verification_status": "VERIFIED" if verified else "FAILED",
                                     "evidence_direction": "support", "title": f"{target} in {condition}",
                                     "identifier": "12345678", "identifier_type": "PMID"})
    if with_molecule:
        db.insert("molecule_candidates", {"id": f"mol-{uuid.uuid4().hex[:6]}", "project_id": pid,
                                          "workflow_run_id": rid,
                                          "created_at": "2026-02-01T00:00:00Z", "canonical_smiles": "CCO",
                                          "label": "M1", "composite_score": 60, "valid": True,
                                          "safety_status": "PASS", "source_type": "REAL_TOOL_OUTPUT"})
    return rid, pid, ev_id


# ---- Dynamic planner ----
@pytest.mark.unit
def test_hybrid_planner_no_key_uses_fixed_stages(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    out = dynamic_planner.plan_run(condition="NSCLC", target_query="EGFR")
    assert out["plan_source"] == "DETERMINISTIC_FALLBACK"
    ids = [s["stage_id"] for s in out["plan"]["selected_stages"]]
    assert "evidence_mining" in ids and "report_build" in ids


@pytest.mark.unit
def test_hybrid_planner_validates_stage_dependencies():
    bad = {"objective": "x", "selected_stages": [
        {"stage_id": "hypothesis_reasoning", "purpose": "h"},
        {"stage_id": "evidence_mining", "purpose": "e"}]}  # wrong order
    v = dynamic_planner.validate_plan(bad)
    assert v["valid"] is False
    assert any("evidence_mining must precede" in e for e in v["errors"])


@pytest.mark.unit
def test_hybrid_planner_rejects_synthesis_stage():
    bad = {"objective": "x", "selected_stages": [
        {"stage_id": "evidence_mining", "purpose": "e"},
        {"stage_id": "synthesis_route_design", "purpose": "design a synthesis route"}]}
    v = dynamic_planner.validate_plan(bad)
    assert any("forbidden stage" in e for e in v["errors"])
    ids = [s["stage_id"] for s in v["sanitized_plan"]["selected_stages"]]
    assert "synthesis_route_design" not in ids


@pytest.mark.unit
def test_hybrid_planner_records_llm_call_mocked(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    rid, pid, _ = _seed_run()
    fake = FakeLLMClient(response="plan")
    out = dynamic_planner.plan_run(condition="NSCLC", target_query="EGFR", mode=DEV,
                                   run_id=rid, project_id=pid, client=fake)
    assert out["plan_source"] == "REAL_LLM_OUTPUT"
    assert len(fake.calls) == 1
    assert out["plan"]["selected_stages"]


@pytest.mark.integration
def test_hybrid_planner_replans_on_no_molecules(monkeypatch):
    rid, pid, _ = _seed_run()
    fake = FakeLLMClient(response="plan")
    out = dynamic_planner.replan(run_id=rid, failed_stage="chembl_activities",
                                 failure_summary="no valid molecules", condition="NSCLC",
                                 target_query="EGFR", mode=DEV, project_id=pid, client=fake)
    assert "revised_plan" in out
    assert dynamic_planner.list_replans(rid)


@pytest.mark.unit
def test_hybrid_plan_report_includes_observable_summary_only(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    fake = FakeLLMClient(response="plan")
    out = dynamic_planner.plan_run(condition="NSCLC", target_query="EGFR", mode=DEV, client=fake)
    blob = str(out).lower()
    assert "<thinking>" not in blob and "chain-of-thought" not in blob
    assert out["plan"]["selected_stages"][0]["rationale_summary"]


@pytest.mark.unit
def test_hybrid_planner_derives_project_and_rejects_mismatch(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    rid, pid, _ = _seed_run()
    planned = dynamic_planner.plan_run(
        condition="NSCLC", target_query="EGFR", run_id=rid,
    )
    assert planned["project_id"] == pid
    assert planned["workflow_run_id"] == rid
    with pytest.raises(ValueError, match="does not match"):
        dynamic_planner.plan_run(
            condition="NSCLC", target_query="EGFR", run_id=rid,
            project_id="wrong-project",
        )


@pytest.mark.integration
def test_hybrid_run_endpoints_reject_unknown_run():
    missing = f"missing-{uuid.uuid4().hex}"
    assert client.post("/api/workflow/plan-hybrid", json={
        "condition": "NSCLC", "target_query": "EGFR", "run_id": missing,
    }).status_code == 404
    assert client.get(f"/api/workflow/runs/{missing}/replans").status_code == 404
    assert client.get(f"/api/hypotheses/run/{missing}/hybrid").status_code == 404
    assert client.get(f"/api/critic/semantic/run/{missing}").status_code == 404
    assert client.post("/api/rediscovery/run", json={"run_id": missing}).status_code == 404
    assert client.post("/api/optimization-loop/run", json={"run_id": missing}).status_code == 404


# ---- Hypothesis reasoner ----
@pytest.mark.integration
def test_hybrid_hypothesis_no_key_fallback(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    rid, pid, ev = _seed_run()
    out = hypothesis_reasoner.generate_hybrid(run_id=rid)
    assert out["reasoning_source_type"] == "DETERMINISTIC_FALLBACK"
    assert out["hypothesis_count"] >= 1


@pytest.mark.integration
def test_hybrid_hypothesis_mocked_llm_valid_ids(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    rid, pid, ev = _seed_run()
    fake = FakeLLMClient(response="hypotheses", evidence_ids=[ev])
    out = hypothesis_reasoner.generate_hybrid(run_id=rid, mode=DEV, client=fake)
    assert out["reasoning_source_type"] == "REAL_LLM_OUTPUT"
    assert out["hypotheses"][0]["evidence_ids"] == [ev]


@pytest.mark.integration
def test_hybrid_hypothesis_rejects_fake_evidence_id(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    rid, pid, ev = _seed_run()
    fake = FakeLLMClient(response="fake_evidence")
    out = hypothesis_reasoner.generate_hybrid(run_id=rid, mode=DEV, client=fake)
    # the fabricated id must have been dropped
    assert all("ev-DOES-NOT-EXIST" not in str(h["evidence_ids"]) for h in out["hypotheses"])
    assert any("non-existent evidence" in n for n in out["validation_notes"])


@pytest.mark.integration
def test_hybrid_hypothesis_language_lint_blocks_and_rewrites(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    rid, pid, ev = _seed_run()
    fake = FakeLLMClient(response="overclaim", evidence_ids=[ev])
    out = hypothesis_reasoner.generate_hybrid(run_id=rid, mode=DEV, client=fake)
    # overclaim statement must be rewritten or dropped — no stored statement is BLOCKED
    from app.services.scientific_language_linter import check
    for h in out["hypotheses"]:
        assert check(h["statement"])["status"] != "BLOCKED"


@pytest.mark.integration
def test_hypothesis_report_discloses_llm_model_and_limits(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    rid, pid, ev = _seed_run()
    fake = FakeLLMClient(response="hypotheses", evidence_ids=[ev])
    out = hypothesis_reasoner.generate_hybrid(run_id=rid, mode=DEV, client=fake)
    assert out["model"]
    assert out["limitations"]
    assert "clinical" in out["disclaimer"].lower() or "임상" in out["disclaimer"]


# ---- Semantic critic ----
@pytest.mark.integration
def test_semantic_critic_no_key_fallback(monkeypatch):
    monkeypatch.setenv("HELIXFORGE_USE_LLM", "false")
    rid, pid, ev = _seed_run(with_molecule=True)
    out = semantic_critic.run_semantic_critic(rid)
    assert out["reasoning_source_type"] == "DETERMINISTIC_FALLBACK"


@pytest.mark.integration
def test_semantic_critic_mocked_overclaim_detected(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    rid, pid, ev = _seed_run(with_molecule=True)
    fake = FakeLLMClient(response="critic")
    out = semantic_critic.run_semantic_critic(rid, mode=DEV, client=fake)
    assert out["reasoning_source_type"] == "REAL_LLM_OUTPUT"
    assert out["critique_count"] >= 1
    assert any(i["category"] == "OVERCLAIM" for i in out["critique_items"])


@pytest.mark.integration
def test_semantic_critic_creates_revision_event(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    rid, pid, ev = _seed_run(with_molecule=True)
    fake = FakeLLMClient(response="critic")
    out = semantic_critic.run_semantic_critic(rid, mode=DEV, client=fake)
    assert out["revision_event_ids"]
    revs = [r for r in db.list_records("revision_events", limit=500) if r.get("workflow_run_id") == rid]
    assert any(r.get("source") == "semantic_critic" for r in revs)


@pytest.mark.integration
def test_semantic_critic_no_chain_of_thought_output(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    rid, pid, ev = _seed_run(with_molecule=True)
    fake = FakeLLMClient(response="critic")
    out = semantic_critic.run_semantic_critic(rid, mode=DEV, client=fake)
    blob = str(out).lower()
    assert "<thinking>" not in blob and "chain-of-thought" not in blob.replace("no hidden chain-of-thought", "")


@pytest.mark.integration
def test_semantic_critic_endpoints(monkeypatch):
    rid, pid, ev = _seed_run(with_molecule=True)
    r = client.post(f"/api/critic/semantic/run/{rid}", json={})
    assert r.status_code == 200
    assert client.get(f"/api/critic/semantic/run/{rid}").status_code == 200


@pytest.mark.integration
def test_hybrid_planner_endpoint(monkeypatch):
    r = client.post("/api/workflow/plan-hybrid", json={"condition": "NSCLC", "target_query": "EGFR"})
    assert r.status_code == 200
    assert "plan" in r.json()
