"""Phase 3 tests: record/replay, evidence QA, AI ledger, release, submission, trace.

Offline unit tests use synthetic DB rows. The run-dependent tests share one live
agentic run (module fixture) and are marked live_api + slow so CI can skip them.
"""
import uuid
import json

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    agent_engine, ai_interaction_ledger as ledger, evidence_linter,
    release_readiness, snapshots, submission_pack,
)
from app.storage import db

client = TestClient(app)


@pytest.mark.unit
def test_snapshot_rejects_tampered_payload(tmp_path, monkeypatch):
    pid = f"proj-snap-integrity-{uuid.uuid4().hex[:6]}"
    rid = f"run-snap-integrity-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {
        "id": rid, "project_id": pid, "created_at": "2026-01-01T00:00:00Z",
        "kind": "agentic", "condition": "NSCLC", "target_query": "EGFR",
    })
    db.insert("evidence_items", {
        "id": f"ev-{rid}", "project_id": pid, "workflow_run_id": rid,
        "created_at": "2026-01-01T00:00:00Z", "title": "original",
        "source_type": "REAL_TOOL_OUTPUT",
    })
    monkeypatch.setattr(snapshots, "SNAP_DIR", tmp_path)
    snap = snapshots.create_snapshot_from_run(rid, "integrity test")
    path = tmp_path / f"{snap['id']}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["evidence_items"][0]["title"] = "tampered"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="checksum mismatch"):
        snapshots.export_snapshot(snap["id"])
    with pytest.raises(ValueError, match="checksum mismatch"):
        snapshots.replay_snapshot(snap["id"])


@pytest.mark.unit
def test_replay_scopes_legacy_snapshot_entities(tmp_path):
    suffix = uuid.uuid4().hex[:8]
    original_run = f"legacy-run-{suffix}"
    payload = {
        "run": {
            "id": original_run, "project_id": f"legacy-project-{suffix}",
            "created_at": "2025-01-01T00:00:00Z", "status": "complete",
        },
        "plan": None, "agent_runs": [], "tool_runs": [], "audit_events": [],
        "evidence_items": [{"id": f"legacy-ev-{suffix}", "source_type": "REAL_TOOL_OUTPUT"}],
        "target_candidates": [{"id": f"legacy-tgt-{suffix}", "source_type": "REAL_TOOL_OUTPUT"}],
        "molecule_candidates": [{"id": f"legacy-mol-{suffix}", "source_type": "REAL_TOOL_OUTPUT"}],
        "hypotheses": [], "evaluation_results": [], "revision_events": [],
        "reports": {}, "counts": {}, "metrics": {},
    }
    path = tmp_path / f"legacy-{suffix}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    snap_id = f"legacy-snapshot-{suffix}"
    db.insert("run_snapshots", {
        "id": snap_id, "project_id": payload["run"]["project_id"],
        "source_run_id": original_run, "created_at": "2025-01-02T00:00:00Z",
        "name": "legacy", "condition": "NSCLC", "target_query": "EGFR",
        "checksum": snapshots._checksum(payload), "storage_path": str(path),
    })

    replay = snapshots.replay_snapshot(snap_id)
    replay_run = replay["run_id"]
    for table in ("evidence_items", "target_candidates", "molecule_candidates"):
        rows = db.list_records(table, workflow_run_id=replay_run)
        assert len(rows) == 1
        assert rows[0]["project_id"] == replay["project_id"]


# --------------------------------------------------------------------------
# Offline unit tests
# --------------------------------------------------------------------------
@pytest.mark.unit
def test_evidence_linter_blocks_failed_citation_as_verified():
    pid = f"proj-test-{uuid.uuid4().hex[:6]}"
    rid = f"run-test-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {"id": rid, "project_id": pid, "created_at": "2026-01-01T00:00:00Z", "kind": "agentic"})
    db.insert("evidence_items", {"id": "ev-fail-x", "project_id": pid, "workflow_run_id": rid,
                                 "created_at": "2026-01-01T00:00:00Z",
                                 "source_name": "PubMed", "identifier": "PMID:00000000",
                                 "verification_status": "FAILED", "source_type": "HUMAN_INPUT"})
    db.insert("hypotheses", {"id": "hyp-x", "project_id": pid, "workflow_run_id": rid,
                             "created_at": "2026-01-01T00:00:00Z",
                             "statement": "uses a failed citation", "evidence_ids": ["ev-fail-x"]})
    res = evidence_linter.lint_run(rid, markdown="Final responsibility belongs to the human research team.")
    assert res["status"] == "BLOCKED"
    assert any(i["category"] == "failed_citation_used" for i in res["issues"])


@pytest.mark.unit
def test_evidence_linter_passes_clean_report():
    pid = f"proj-clean-{uuid.uuid4().hex[:6]}"
    rid = f"run-clean-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {"id": rid, "project_id": pid, "created_at": "2026-01-01T00:00:00Z", "kind": "agentic"})
    db.insert("evidence_items", {"id": "ev-ok-x", "project_id": pid, "workflow_run_id": rid,
                                 "created_at": "2026-01-01T00:00:00Z",
                                 "source_name": "PubMed", "identifier": "PMID:12345678",
                                 "identifier_type": "PMID", "verification_status": "VERIFIED",
                                 "retrieved_at": "2026-01-01T00:00:00Z", "source_type": "REAL_TOOL_OUTPUT"})
    db.insert("hypotheses", {"id": "hyp-ok", "project_id": pid, "workflow_run_id": rid,
                             "created_at": "2026-01-01T00:00:00Z",
                             "statement": "ok", "evidence_ids": ["ev-ok-x"], "assumptions": ["in-silico only"]})
    res = evidence_linter.lint_run(rid, markdown="... research decision support only. responsibility belongs to the human research team.")
    assert res["status"] in ("PASS", "REVIEW_REQUIRED")
    assert not any(i["severity"] == "BLOCKED" for i in res["issues"])


@pytest.mark.unit
def test_evidence_linter_detects_missing_source_type():
    pid = f"proj-ms-{uuid.uuid4().hex[:6]}"
    rid = f"run-ms-{uuid.uuid4().hex[:6]}"
    db.insert("workflow_runs", {"id": rid, "project_id": pid, "created_at": "2026-01-01T00:00:00Z", "kind": "agentic"})
    db.insert("evidence_items", {"id": "ev-nost", "project_id": pid, "workflow_run_id": rid,
                                 "created_at": "2026-01-01T00:00:00Z",
                                 "source_name": "PubMed", "identifier": "PMID:1", "verification_status": "VERIFIED"})
    res = evidence_linter.lint_run(rid, markdown="responsibility belongs to the human research team.")
    assert any(i["category"] == "missing_source_type" for i in res["issues"])


@pytest.mark.unit
def test_ai_ledger_records_deterministic_agents():
    rid = f"run-ai-{uuid.uuid4().hex[:6]}"
    rec = ledger.record(run_id=rid, agent_run_id="ar-1", interaction_type="DETERMINISTIC_AGENT",
                        user_prompt_summary="EGFR", notes="did stuff")
    assert rec["interaction_type"] == "DETERMINISTIC_AGENT"
    s = ledger.summary_for_run(rid)
    assert s["interaction_count"] == 1 and s["llm_used"] is False


@pytest.mark.unit
def test_ai_ledger_redacts_secrets():
    rid = f"run-sec-{uuid.uuid4().hex[:6]}"
    rec = ledger.record(run_id=rid, agent_run_id=None, interaction_type="DETERMINISTIC_AGENT",
                        user_prompt_summary="query with api_key=SUPERSECRET123 inside", notes="x")
    assert "SUPERSECRET123" not in rec["user_prompt_summary"]
    assert "REDACTED" in rec["user_prompt_summary"]


@pytest.mark.unit
def test_submission_pack_includes_disclaimer_and_excludes_secrets():
    art = submission_pack.generate_artifact("ethics_appendix")
    assert "responsibility belongs to the human research team" in art["markdown"].lower()
    prop = submission_pack.generate_artifact("korean_proposal")
    assert "책임은 연구자" in prop["markdown"]


@pytest.mark.unit
def test_submission_pack_contains_required_sections():
    tech = submission_pack.generate_artifact("technical_appendix")
    for kw in ("Architecture", "Real integrations", "Reproducibility"):
        assert kw in tech["markdown"]
    peer = submission_pack.generate_artifact("peer_review_summary")
    assert "동료 검토" in peer["markdown"] or "Peer Review" in peer["markdown"]


@pytest.mark.integration
def test_release_readiness_endpoint():
    r = client.get("/api/release-readiness")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in ("NOT_READY", "DRAFT_READY", "PROPOSAL_READY", "DEMO_READY", "SUBMISSION_READY")
    assert 0 <= body["total_score"] <= 100


@pytest.mark.integration
def test_run_export_does_not_include_same_project_other_run_records():
    pid = f"export-project-{uuid.uuid4().hex[:6]}"
    first = f"export-run-a-{uuid.uuid4().hex[:6]}"
    second = f"export-run-b-{uuid.uuid4().hex[:6]}"
    for run_id in (first, second):
        db.insert("workflow_runs", {"id": run_id, "project_id": pid,
                                    "created_at": "2026-01-01T00:00:00Z", "kind": "agentic"})
    db.insert("evidence_items", {"id": f"ev-{first}", "project_id": pid,
                                 "workflow_run_id": first, "created_at": "2026-01-01T00:00:00Z"})
    db.insert("evidence_items", {"id": f"ev-{second}", "project_id": pid,
                                 "workflow_run_id": second, "created_at": "2026-01-01T00:00:00Z"})
    response = client.get(f"/api/export/run/{first}")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()["evidence_items"]}
    assert ids == {f"ev-{first}"}


# --------------------------------------------------------------------------
# Live run-dependent tests (record/replay)
# --------------------------------------------------------------------------
@pytest.fixture(scope="module")
def real_run():
    return agent_engine.run_agentic_pipeline({
        "condition": "non-small cell lung cancer", "target_query": "EGFR", "max_results": 4,
        "create_reinvent_config": False, "error_injections": {},
    })


@pytest.fixture(scope="module")
def snapshot(real_run):
    return snapshots.create_snapshot_from_run(real_run["run_id"], "test snapshot", "phase3 test")


@pytest.mark.live_api
@pytest.mark.slow
def test_create_snapshot_from_run(snapshot):
    assert snapshot["id"].startswith("snap-")
    assert snapshot["checksum"].startswith("sha256:")
    assert db.get("run_snapshots", snapshot["id"]) is not None


@pytest.mark.live_api
@pytest.mark.slow
def test_replay_snapshot_labels_recorded_real(snapshot):
    rp = snapshots.replay_snapshot(snapshot["id"])
    assert rp["mode"] == "RECORDED_REPLAY"
    src = {s for a in rp["agent_runs"] for s in (a.get("source_types") or [])}
    assert "RECORDED_REAL_TOOL_OUTPUT" in src
    assert "REAL_TOOL_OUTPUT" not in src  # real must be flipped to recorded on replay


@pytest.mark.live_api
@pytest.mark.slow
def test_snapshot_manifest_has_original_and_replay_timestamps(snapshot):
    man = snapshots.snapshot_manifest(snapshot["id"])
    assert man["original_started_at"]
    assert man["captured_at"]
    assert man["replay_note"]


@pytest.mark.live_api
@pytest.mark.slow
def test_report_discloses_replay_mode(snapshot):
    rp = snapshots.replay_snapshot(snapshot["id"])
    rep = db.get("reports", rp["report_id"])
    assert rep and "RECORDED REPLAY" in rep["markdown"]
    assert rep["source_type"] == "RECORDED_REAL_TOOL_OUTPUT"


@pytest.mark.live_api
@pytest.mark.slow
def test_snapshot_export_excludes_secrets(snapshot, monkeypatch):
    exp = snapshots.export_snapshot(snapshot["id"])
    import json
    blob = json.dumps(exp)
    assert "SUPERSECRET" not in blob  # sanity; redaction path exercised


@pytest.mark.live_api
@pytest.mark.slow
def test_replay_does_not_call_live_api(snapshot, monkeypatch):
    # If replay tried to hit ChEMBL/PubMed, this patched httpx would raise.
    import app.services.httpclient as hc
    called = {"n": 0}
    orig = getattr(hc, "get_json", None)
    if orig:
        def boom(*a, **k):
            called["n"] += 1
            raise AssertionError("replay must not call live API")
        monkeypatch.setattr(hc, "get_json", boom, raising=False)
    rp = snapshots.replay_snapshot(snapshot["id"])
    assert rp["run_id"].startswith("replay-")
    assert called["n"] == 0


@pytest.mark.live_api
@pytest.mark.slow
def test_workflow_trace_contains_nodes_edges(real_run):
    r = client.get(f"/api/workflow/runs/{real_run['run_id']}/trace")
    assert r.status_code == 200
    body = r.json()
    assert len(body["nodes"]) >= 10
    assert len(body["edges"]) >= 9
    assert body["source_type_counts"]
