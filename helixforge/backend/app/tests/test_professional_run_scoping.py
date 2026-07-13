"""Regression coverage for exact workflow-run scoping in professional views."""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    activity_normalization,
    applicability_domain,
    evidence_grading,
    identity_normalization,
    medchem_review,
    pareto_optimization,
    professional_release,
    red_team,
    red_team_pro,
    release_readiness,
    target_biology_review,
    translational_readiness,
)
from app.storage import db


def _seed_two_runs() -> tuple[str, str, str, str]:
    suffix = uuid.uuid4().hex[:10]
    project_id = f"scope-project-{suffix}"
    run_a, run_b = f"scope-run-a-{suffix}", f"scope-run-b-{suffix}"
    db.insert("workflow_runs", {
        "id": run_a, "project_id": project_id, "kind": "agentic",
        "condition": "condition-a", "target_query": "TARGETA",
        "created_at": "2026-01-01T00:00:00Z",
    })
    db.insert("workflow_runs", {
        "id": run_b, "project_id": project_id, "kind": "agentic",
        "condition": "condition-b", "target_query": "TARGETB",
        "created_at": "2026-01-02T00:00:00Z",
    })
    for run_id, mol_id, smiles, valid in (
        (run_a, f"mol-a-{suffix}", "CCO", True),
        (run_b, f"mol-b-{suffix}", "not-a-smiles", False),
    ):
        db.insert("molecule_candidates", {
            "id": mol_id, "project_id": project_id, "workflow_run_id": run_id,
            "canonical_smiles": smiles, "valid": valid, "safety_status": "PASS",
            "descriptors": {"mol_weight": 46.1, "logp": -0.3, "hbd": 1,
                            "hba": 1, "tpsa": 20.2},
            "created_at": "2026-01-02T00:00:00Z",
        })
    target_a = f"target-a-{suffix}"
    db.insert("target_candidates", {
        "id": target_a, "project_id": project_id, "workflow_run_id": run_a,
        "target_chembl_id": "CHEMBL-A", "pref_name": "TARGETA", "score": 1,
        "created_at": "2026-01-01T00:00:00Z",
    })
    db.insert("evidence_items", {
        "id": f"evidence-a-{suffix}", "project_id": project_id,
        "workflow_run_id": run_a, "target_chembl_id": "CHEMBL-A",
        "source_name": "PubMed", "source_type": "REAL_TOOL_OUTPUT",
        "verification_status": "VERIFIED", "created_at": "2026-01-01T00:00:00Z",
    })
    return project_id, run_a, run_b, target_a


@pytest.mark.integration
def test_professional_services_do_not_mix_runs_in_same_project():
    _, run_a, run_b, target_a = _seed_two_runs()

    activity = activity_normalization.normalize_run(run_a)
    assert set(activity["molecule_reliability"]) == {target_a.replace("target", "mol")}

    medchem = medchem_review.review_run(run_a)
    assert [row["molecule_id"] for row in medchem["reviews"]] == [target_a.replace("target", "mol")]

    applicability = applicability_domain.assess_run(run_a)
    assert [row["molecule_id"] for row in applicability["results"]] == [target_a.replace("target", "mol")]

    pareto = pareto_optimization.run(run_a)
    assert [row["molecule_id"] for row in pareto["all_candidates"]] == [target_a.replace("target", "mol")]

    biology = target_biology_review.review_run(run_a)
    assert biology["count"] == 1
    assert biology["reviews"][0]["target_id"] == target_a

    readiness = translational_readiness.assess_run(run_a)
    assert readiness["target_readiness"]["target_count"] == 1
    assert readiness["molecule_readiness"]["molecule_count"] == 1

    assert evidence_grading.grade_target_candidates(run_a)["count"] == 1
    assert evidence_grading.grade_target_candidates(run_b)["count"] == 0
    assert evidence_grading.grade_molecule_candidates(run_a)["count"] == 1
    assert evidence_grading.grade_molecule_candidates(run_b)["count"] == 1

    identities_a = identity_normalization.normalize_run(run_a)
    identities_b = identity_normalization.normalize_run(run_b)
    assert len(identities_a["targets"]) == 1 and len(identities_a["molecules"]) == 1
    assert len(identities_b["targets"]) == 0 and len(identities_b["molecules"]) == 1

    release_run_a = release_readiness.compute(run_a)
    release_run_b = release_readiness.compute(run_b)
    valid_a = next(c for c in release_run_a["checks"]["molecule_readiness"]
                   if "RDKit-valid" in c["label"])
    valid_b = next(c for c in release_run_b["checks"]["molecule_readiness"]
                   if "RDKit-valid" in c["label"])
    assert valid_a["ok"] is True
    assert valid_b["ok"] is False

    release_a = professional_release.compute(run_a)
    release_b = professional_release.compute(run_b)
    category_a = next(row for row in release_a["categories"] if row["key"] == "C")
    category_b = next(row for row in release_b["categories"] if row["key"] == "C")
    assert category_a["score"] == 100
    assert category_b["score"] == 0


@pytest.mark.integration
def test_professional_endpoints_reject_unknown_run_ids():
    client = TestClient(app)
    missing = f"missing-{uuid.uuid4().hex}"
    paths = [
        f"/api/activities/run/{missing}/summary",
        f"/api/medchem/run/{missing}",
        f"/api/applicability/run/{missing}",
        f"/api/target-biology/run/{missing}",
        f"/api/translational/readiness/{missing}",
        f"/api/clinical/precedent-review/{missing}",
        f"/api/optimization/pareto/run/{missing}",
        f"/api/release-readiness/professional/latest?run_id={missing}",
        f"/api/source-types/audit?run_id={missing}",
        f"/api/evidence-grades/run/{missing}",
        f"/api/identity/run/{missing}",
        f"/api/docking/protocol/run/{missing}",
        f"/api/release-readiness?run_id={missing}",
        f"/api/submission/bundle?run_id={missing}",
    ]
    for path in paths:
        assert client.get(path).status_code == 404, path


@pytest.mark.integration
def test_run_scoped_gets_return_explicit_empty_results_without_writes():
    _, _, run_id, _ = _seed_two_runs()
    client = TestClient(app)
    cases = [
        ("activity_normalizations", f"/api/activities/run/{run_id}/summary"),
        ("medchem_reviews", f"/api/medchem/run/{run_id}"),
        ("applicability_results", f"/api/applicability/run/{run_id}"),
        ("target_biology_reviews", f"/api/target-biology/run/{run_id}"),
        ("translational_assessments", f"/api/translational/readiness/{run_id}"),
        ("clinical_precedent_reviews", f"/api/clinical/precedent-review/{run_id}"),
        ("pareto_analyses", f"/api/optimization/pareto/run/{run_id}"),
        ("identity_normalizations", f"/api/identity/run/{run_id}"),
        ("professional_evaluations",
         f"/api/release-readiness/professional/latest?run_id={run_id}"),
        ("docking_protocols", f"/api/docking/protocol/run/{run_id}"),
    ]
    for table, path in cases:
        before = db.count(table, workflow_run_id=run_id)
        assert before == 0
        response = client.get(path)
        assert response.status_code == 200, path
        assert response.json()["status"] == "NOT_COMPUTED", path
        assert db.count(table, workflow_run_id=run_id) == before, path

    activity = client.get(f"/api/activities/run/{run_id}/summary").json()
    assert activity["normalized"] == []
    assert activity["endpoint_summaries"] == {}
    assert activity["molecule_reliability"] == {}


@pytest.mark.integration
def test_run_scoped_gets_return_persisted_records_without_recomputing():
    _, run_id, _, _ = _seed_two_runs()
    client = TestClient(app)

    release = client.post(
        "/api/release-readiness/professional", params={"run_id": run_id}
    ).json()
    activity = client.post(
        "/api/activities/normalize", params={"run_id": run_id}, json={"records": []}
    ).json()
    medchem = client.post("/api/medchem/review-run", params={"run_id": run_id}).json()
    applicability = client.post("/api/applicability/run", params={"run_id": run_id}).json()
    biology = client.post("/api/target-biology/review-run", params={"run_id": run_id}).json()
    readiness = client.post("/api/translational/readiness/run", params={"run_id": run_id}).json()
    clinical = client.post("/api/clinical/precedent-review", params={"run_id": run_id}).json()
    pareto = client.post("/api/optimization/pareto/run", params={"run_id": run_id}).json()
    identity = client.post("/api/identity/normalize-run", params={"run_id": run_id}).json()
    docking = client.post(f"/api/docking/protocol/run/{run_id}").json()

    cases = [
        ("activity_normalizations", f"/api/activities/run/{run_id}/summary",
         activity["id"], lambda body: body["id"]),
        ("medchem_reviews", f"/api/medchem/run/{run_id}",
         medchem["id"], lambda body: body["id"]),
        ("applicability_results", f"/api/applicability/run/{run_id}",
         applicability["id"], lambda body: body["id"]),
        ("target_biology_reviews", f"/api/target-biology/run/{run_id}",
         biology["id"], lambda body: body["id"]),
        ("translational_assessments", f"/api/translational/readiness/{run_id}",
         readiness["id"], lambda body: body["id"]),
        ("clinical_precedent_reviews", f"/api/clinical/precedent-review/{run_id}",
         clinical["id"], lambda body: body["id"]),
        ("pareto_analyses", f"/api/optimization/pareto/run/{run_id}",
         pareto["id"], lambda body: body["id"]),
        ("identity_normalizations", f"/api/identity/run/{run_id}",
         identity["id"], lambda body: body["id"]),
        ("professional_evaluations",
         f"/api/release-readiness/professional/latest?run_id={run_id}",
         release["id"], lambda body: body["id"]),
        ("docking_protocols", f"/api/docking/protocol/run/{run_id}",
         docking["protocol"]["id"], lambda body: body["protocol"]["id"]),
    ]
    for table, path, expected_id, get_id in cases:
        before = db.count(table, workflow_run_id=run_id)
        first = client.get(path)
        second = client.get(path)
        assert first.status_code == 200 and second.status_code == 200, path
        assert get_id(first.json()) == expected_id, path
        assert get_id(second.json()) == expected_id, path
        assert db.count(table, workflow_run_id=run_id) == before, path


@pytest.mark.integration
def test_red_team_suites_do_not_persist_probe_runs_or_reports():
    before_run_count = db.count("workflow_runs")
    before_report_count = db.count("reports")
    runs = db.list_records("workflow_runs", limit=1)
    latest_before = runs[0]["id"] if runs else None

    assert red_team.run_suite()["status"] == "PASS"
    assert red_team_pro.run_suite()["status"] == "PASS"

    runs_after = db.list_records("workflow_runs", limit=1)
    latest_after = runs_after[0]["id"] if runs_after else None
    assert db.count("workflow_runs") == before_run_count
    assert db.count("reports") == before_report_count
    assert latest_after == latest_before
