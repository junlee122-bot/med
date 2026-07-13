"""Run-isolation and HTTP idempotency coverage for generated documents."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import professional_docs, scientific_whitepaper
from app.storage import db


def _seed_runs() -> tuple[str, str, str]:
    suffix = uuid.uuid4().hex[:10]
    project_id = f"doc-project-{suffix}"
    run_a = f"doc-run-a-{suffix}"
    run_b = f"doc-run-b-{suffix}"
    for run_id, created_at, target in (
        (run_a, "2026-04-01T00:00:00Z", "TARGET-A"),
        (run_b, "2026-04-02T00:00:00Z", "TARGET-B"),
    ):
        db.insert("workflow_runs", {
            "id": run_id,
            "project_id": project_id,
            "workflow_run_id": run_id,
            "kind": "agentic",
            "target_query": target,
            "metrics": {"top_target": target},
            "created_at": created_at,
        })
    return project_id, run_a, run_b


@pytest.mark.integration
def test_document_endpoints_are_exactly_run_scoped():
    project_id, run_a, run_b = _seed_runs()
    client = TestClient(app)

    assert professional_docs._gather_state(run_a)["run_count"] == 1
    assert scientific_whitepaper._gather(run_a)["run_count"] == 1

    proposal_a = client.post("/api/proposal/generate", json={
        "kind": "full_proposal_ko", "run_id": run_a,
    })
    proposal_b = client.post("/api/proposal/generate", json={
        "kind": "full_proposal_ko", "run_id": run_b,
    })
    assert proposal_a.status_code == proposal_b.status_code == 200
    assert proposal_a.json()["workflow_run_id"] == run_a
    assert proposal_b.json()["workflow_run_id"] == run_b

    doc_a = client.post("/api/professional-docs/generate", json={
        "doc_type": "model_card", "run_id": run_a,
    })
    doc_b = client.post("/api/professional-docs/generate", json={
        "doc_type": "model_card", "run_id": run_b,
    })
    assert doc_a.status_code == doc_b.status_code == 200

    wp_a = client.post("/api/whitepaper/generate", json={"lang": "en", "run_id": run_a})
    wp_b = client.post("/api/whitepaper/generate", json={"lang": "en", "run_id": run_b})
    assert wp_a.status_code == wp_b.status_code == 200

    sub_a = client.post("/api/submission/generate", json={
        "artifact_type": "judge_readme", "run_id": run_a,
    })
    sub_b = client.post("/api/submission/generate", json={
        "artifact_type": "judge_readme", "run_id": run_b,
    })
    assert sub_a.status_code == sub_b.status_code == 200

    proposals = client.get(f"/api/proposal/latest?run_id={run_a}").json()["artifacts"]
    assert proposals and {row["workflow_run_id"] for row in proposals} == {run_a}

    docs = client.get(f"/api/professional-docs?run_id={run_a}").json()["documents"]
    assert docs and {row["workflow_run_id"] for row in docs} == {run_a}
    assert client.get(
        f"/api/professional-docs/{doc_b.json()['id']}?run_id={run_a}"
    ).status_code == 404

    latest = client.get(f"/api/whitepaper/latest?lang=en&run_id={run_a}")
    assert latest.status_code == 200
    assert latest.json()["workflow_run_id"] == run_a

    submissions = client.get(f"/api/submission/artifacts?run_id={run_a}").json()["artifacts"]
    assert submissions and {row["workflow_run_id"] for row in submissions} == {run_a}
    assert client.get(
        f"/api/submission/artifacts/{sub_b.json()['id']}?run_id={run_a}"
    ).status_code == 404

    handoff = client.get(f"/api/hwpx/handoff?run_id={run_a}")
    assert handoff.status_code == 200
    assert handoff.json()["project_id"] == project_id
    assert handoff.json()["workflow_run_id"] == run_a


@pytest.mark.integration
def test_document_get_exports_do_not_write_records():
    _, run_a, _ = _seed_runs()
    client = TestClient(app)
    assert client.post("/api/proposal/generate", json={
        "kind": "all", "run_id": run_a,
    }).status_code == 200
    assert client.post("/api/professional-docs/generate", json={
        "doc_type": "model_card", "run_id": run_a,
    }).status_code == 200
    for lang in ("en", "ko"):
        assert client.post("/api/whitepaper/generate", json={
            "lang": lang, "run_id": run_a,
        }).status_code == 200
    assert client.post("/api/submission/generate", json={
        "artifact_type": "judge_readme", "run_id": run_a,
    }).status_code == 200

    tables = (
        "submission_artifacts",
        "professional_documents",
        "whitepapers",
        "evidence_claims",
        "medchem_reviews",
        "translational_assessments",
        "clinical_precedent_reviews",
    )
    before = {table: db.count(table) for table in tables}
    for path in (
        f"/api/proposal/export?run_id={run_a}",
        f"/api/professional-docs/bundle?run_id={run_a}",
        f"/api/whitepaper/export?run_id={run_a}",
        f"/api/submission/bundle?run_id={run_a}",
        f"/api/hwpx/handoff?run_id={run_a}",
    ):
        response = client.get(path)
        assert response.status_code == 200, (path, response.text)
    assert {table: db.count(table) for table in tables} == before


@pytest.mark.integration
def test_document_endpoints_reject_unknown_runs():
    missing = f"missing-doc-run-{uuid.uuid4().hex}"
    client = TestClient(app)
    requests = (
        ("post", "/api/proposal/generate", {"kind": "full_proposal_ko", "run_id": missing}),
        ("get", f"/api/proposal/latest?run_id={missing}", None),
        ("get", f"/api/proposal/export?run_id={missing}", None),
        ("post", "/api/professional-docs/generate", {"doc_type": "model_card", "run_id": missing}),
        ("get", f"/api/professional-docs?run_id={missing}", None),
        ("get", f"/api/professional-docs/bundle?run_id={missing}", None),
        ("post", "/api/whitepaper/generate", {"lang": "en", "run_id": missing}),
        ("get", f"/api/whitepaper/latest?run_id={missing}", None),
        ("get", f"/api/whitepaper/export?run_id={missing}", None),
        ("get", f"/api/submission/artifacts?run_id={missing}", None),
        ("get", f"/api/hwpx/handoff?run_id={missing}", None),
    )
    for method, path, payload in requests:
        response = getattr(client, method)(path, json=payload) if payload else getattr(client, method)(path)
        assert response.status_code == 404, (path, response.text)
