"""Regression: GET /api/report/{report_id} must retrieve agentic/hybrid reports
(rep-en-<run_id> / rep-ko-<run_id>) that store provenance as discrete fields
instead of a `json_audit` payload. Previously this 500'd on a KeyError."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import SourceType, utcnow
from app.storage import db

client = TestClient(app)


def _insert_agentic_report(lang: str) -> str:
    """Store a report exactly as report_builder_agent does — NO `json_audit` key."""
    rid = f"arun-{uuid.uuid4().hex[:8]}"
    rep_id = f"rep-{lang}-{rid}"
    db.insert("reports", {
        "id": rep_id, "project_id": f"p-{uuid.uuid4().hex[:6]}", "created_at": utcnow(),
        "workflow_run_id": rid, "type": f"{lang}_report",
        "title": f"HelixForge — EGFR Agentic Report ({lang.upper()})",
        "markdown": ("# HelixForge Agentic Report\n\nDeterministic scientific backbone. "
                     "This run used deterministic agents (no external LLM calls). "
                     "No wet-lab protocols, synthesis routes, or dosage are produced."),
        "language": lang, "safety_lint": {"status": "PASS"}, "export_safe": True,
        "source_type": SourceType.REAL_TOOL_OUTPUT.value})
    return rep_id


@pytest.mark.integration
def test_get_report_retrieves_agentic_en_report():
    rep_id = _insert_agentic_report("en")
    r = client.get(f"/api/report/{rep_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["report_id"] == rep_id
    assert body["markdown"].strip()
    # provenance surfaced without a stored json_audit
    assert isinstance(body["json_audit"], dict)
    assert body["json_audit"].get("source_type") == "REAL_TOOL_OUTPUT"


@pytest.mark.integration
def test_get_report_retrieves_agentic_ko_report():
    rep_id = _insert_agentic_report("ko")
    r = client.get(f"/api/report/{rep_id}")
    assert r.status_code == 200
    assert r.json()["report_id"] == rep_id


@pytest.mark.integration
def test_deterministic_report_does_not_claim_fable_used():
    rep_id = _insert_agentic_report("en")
    md = client.get(f"/api/report/{rep_id}").json()["markdown"].lower()
    assert "fable 5" not in md and "claude-fable" not in md
    assert "real_llm_output" not in md
    # deterministic fallback report is honest about no LLM calls
    assert "no external llm" in md or "deterministic" in md


@pytest.mark.integration
def test_get_report_still_supports_json_audit_reports():
    """Workflow reports that DO carry a json_audit payload keep working."""
    rep_id = f"rep-audit-{uuid.uuid4().hex[:8]}"
    db.insert("reports", {"id": rep_id, "project_id": "p1", "created_at": utcnow(),
                          "title": "Workflow Report", "markdown": "# R",
                          "json_audit": {"events": [], "counts": {}}})
    r = client.get(f"/api/report/{rep_id}")
    assert r.status_code == 200
    assert r.json()["json_audit"] == {"events": [], "counts": {}}


@pytest.mark.integration
def test_get_report_missing_returns_404():
    r = client.get("/api/report/rep-en-does-not-exist")
    assert r.status_code == 404
