"""Phase 5 — evidence hierarchy and claim grading tests."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import evidence_grading as eg
from app.services.evidence_grading import ClaimType, EvidenceGrade

client = TestClient(app)


@pytest.mark.unit
def test_computational_only_claim_downgraded():
    ev = [{"id": "e1", "source_name": "RDKit", "source_type": "REAL_TOOL_OUTPUT", "evidence_direction": "support"}]
    claim = {"claim_text": "molecule is drug-like", "claim_type": ClaimType.MOLECULE_DRUGLIKENESS,
             "linked_evidence_ids": ["e1"]}
    g = eg.grade_claim(claim, ev)
    # computational support may not be graded strong; druglikeness is capped preliminary
    assert g["evidence_grade"] in (EvidenceGrade.C_PRELIMINARY, EvidenceGrade.D_WEAK, EvidenceGrade.E_UNVERIFIED)


@pytest.mark.unit
def test_clinical_trial_precedent_not_efficacy_claim():
    ev = [{"id": "n1", "source_name": "ClinicalTrials.gov", "identifier_type": "NCT",
           "source_type": "REAL_TOOL_OUTPUT", "evidence_direction": "support"},
          {"id": "n2", "source_name": "ClinicalTrials.gov", "identifier_type": "NCT",
           "source_type": "REAL_TOOL_OUTPUT", "evidence_direction": "support"}]
    claim = {"claim_text": "target has clinical precedent", "claim_type": ClaimType.CLINICAL_PRECEDENT,
             "linked_evidence_ids": ["n1", "n2"]}
    g = eg.grade_claim(claim, ev)
    # precedent is capped at B — never A/efficacy
    assert g["evidence_grade"] != EvidenceGrade.A_STRONG
    assert "efficacy" in g["reviewer_note"].lower()


@pytest.mark.unit
def test_failed_citation_grade_unverified():
    ev = [{"id": "f1", "source_name": "PubMed", "source_type": "REAL_TOOL_OUTPUT",
           "verification_status": "FAILED", "evidence_direction": "support"}]
    claim = {"claim_text": "x associated with y", "claim_type": ClaimType.DISEASE_TARGET_ASSOCIATION,
             "linked_evidence_ids": ["f1"]}
    g = eg.grade_claim(claim, ev)
    assert g["evidence_grade"] == EvidenceGrade.E_UNVERIFIED


@pytest.mark.unit
def test_contradiction_downgrades_claim():
    ev = [{"id": "s1", "source_name": "ChEMBL", "source_type": "REAL_TOOL_OUTPUT", "evidence_direction": "support"},
          {"id": "c1", "source_name": "PubMed", "source_type": "REAL_TOOL_OUTPUT", "evidence_direction": "contradict"},
          {"id": "c2", "source_name": "PubMed", "source_type": "REAL_TOOL_OUTPUT", "evidence_direction": "contradict"}]
    claim = {"claim_text": "molecule active", "claim_type": ClaimType.MOLECULE_ACTIVITY,
             "linked_evidence_ids": ["s1", "c1", "c2"]}
    g = eg.grade_claim(claim, ev)
    assert g["evidence_grade"] == EvidenceGrade.F_CONTRADICTED
    assert g["contradiction_count"] == 2


@pytest.mark.unit
def test_report_lint_detects_unsupported_strong_claim():
    md = "Our system proved the molecule is clinically validated and cures the disease."
    res = eg.detect_unsupported_strong_claims(md)
    assert res["status"] in ("REVIEW_REQUIRED", "BLOCKED")
    assert res["count"] >= 1


@pytest.mark.unit
def test_report_lint_korean_overclaim():
    md = "우리는 신약을 발견했다. 임상 효과가 입증됐다. 책임은 연구자에게 있습니다."
    res = eg.detect_unsupported_strong_claims(md)
    assert res["status"] in ("REVIEW_REQUIRED", "BLOCKED")


@pytest.mark.unit
def test_claim_grade_export_contains_levels():
    ev = [{"id": "s1", "source_name": "ChEMBL", "source_type": "REAL_TOOL_OUTPUT", "evidence_direction": "support"}]
    g = eg.grade_claim({"claim_text": "x", "claim_type": ClaimType.MOLECULE_ACTIVITY,
                        "linked_evidence_ids": ["s1"]}, ev)
    assert g["evidence_levels"]
    assert all(lvl.startswith("LEVEL_") for lvl in g["evidence_levels"])


@pytest.mark.unit
def test_downgrade_claim_language_softens():
    r = eg.downgrade_claim_language("This is proven and validated.", EvidenceGrade.E_UNVERIFIED)
    assert r["changed"] is True
    assert "proven" not in r["text"].lower()


@pytest.mark.integration
def test_evidence_grades_run_endpoint():
    r = client.post("/api/evidence-grades/compute")
    assert r.status_code == 200
    body = r.json()
    assert "grade_distribution" in body and "total_claims" in body


@pytest.mark.integration
def test_evidence_grades_lint_endpoint():
    r = client.post("/api/evidence-grades/lint-report", json={"markdown": "This cures cancer, guaranteed."})
    assert r.status_code == 200
    assert r.json()["count"] >= 1
