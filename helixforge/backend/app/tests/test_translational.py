"""Translational readiness assessment tests.

Endpoint-free smoke tests for app.services.translational_readiness.assess_run.
They must stay robust to an empty DB and never allow a level implying wet-lab
or clinical success (the assessment is hard-capped at TRL_4).
"""
from __future__ import annotations

import uuid

import pytest

from app.models.schemas import SourceType, utcnow
from app.services import translational_readiness as tr
from app.storage import db

_ALLOWED = {
    "TRL_0_CONCEPT_ONLY",
    "TRL_1_IN_SILICO_HYPOTHESIS",
    "TRL_2_COMPUTATIONAL_PRIORITIZATION",
    "TRL_3_READY_FOR_EXPERT_REVIEW",
    "TRL_4_READY_FOR_EXPERIMENTAL_PLANNING",
}


def _seed_full_run() -> str:
    """Insert a run with targets + molecules + precedent + evidence."""
    pid = f"proj-{uuid.uuid4().hex[:8]}"
    rid = f"run-{uuid.uuid4().hex[:8]}"
    now = utcnow()
    db.insert("workflow_runs", {"id": rid, "project_id": pid, "created_at": now,
                                "kind": "agentic", "status": "complete",
                                "target_query": "EGFR", "condition": "NSCLC", "metrics": {}})
    db.insert("target_candidates", {"id": f"tgt-{uuid.uuid4().hex[:6]}", "project_id": pid,
                                    "created_at": now, "target_chembl_id": "CHEMBL203",
                                    "pref_name": "EGFR", "evidence_count": 5,
                                    "clinical_precedent_count": 3, "activity_availability": True,
                                    "score": 0.9, "source_type": SourceType.REAL_TOOL_OUTPUT.value})
    db.insert("molecule_candidates", {"id": f"mol-{uuid.uuid4().hex[:6]}", "project_id": pid,
                                      "created_at": now, "canonical_smiles": "CCO", "valid": True,
                                      "safety_status": "PASS", "composite_score": 0.7,
                                      "pchembl_value": 7.2,
                                      "source_type": SourceType.REAL_TOOL_OUTPUT.value})
    for i in range(3):
        db.insert("evidence_items", {"id": f"ev-{uuid.uuid4().hex[:6]}", "project_id": pid,
                                     "created_at": now, "source_name": "ClinicalTrials.gov",
                                     "verification_status": "VERIFIED", "evidence_direction": "support"})
    return rid


@pytest.mark.unit
def test_translational_readiness_capped_without_wetlab():
    a = tr.assess_run(None)
    assert a["readiness_level"] in _ALLOWED
    # Never exceeds the TRL_4 ceiling.
    order = tr._LEVEL_ORDER
    assert order.index(a["readiness_level"]) <= order.index("TRL_4_READY_FOR_EXPERIMENTAL_PLANNING")
    # Cap language must be surfaced somewhere in the assessment text.
    blob = str(a)
    assert "TRL_4" in blob or "wet-lab" in blob


@pytest.mark.unit
def test_translational_readiness_capped_even_with_full_run():
    """A fully populated run must still be capped at TRL_4 (never higher)."""
    rid = _seed_full_run()
    a = tr.assess_run(rid)
    assert a["readiness_level"] in _ALLOWED
    order = tr._LEVEL_ORDER
    assert order.index(a["readiness_level"]) <= order.index("TRL_4_READY_FOR_EXPERIMENTAL_PLANNING")
    assert any("TRL_4" in str(x) or "wet-lab" in str(x) for x in a["limitations"])


@pytest.mark.unit
def test_translational_readiness_lists_blocking_gaps():
    a = tr.assess_run(None)
    assert isinstance(a["blocking_gaps"], list)
    # With no complete wet-lab run the DB, gaps must be reported.
    runs = db.list_records("workflow_runs", limit=1)
    if not runs:
        assert len(a["blocking_gaps"]) > 0
    else:
        # Even a full run keeps the in-silico structural gaps (no wet-lab ever).
        assert len(a["blocking_gaps"]) > 0


@pytest.mark.unit
def test_translational_no_clinical_claim():
    a = tr.assess_run(None)
    blob = str(a).lower()
    forbidden = ["cure", "proven efficacy", "clinically validated", "approved by",
                 "safe and effective", "dosage", "mg/kg"]
    for term in forbidden:
        assert term not in blob, f"forbidden clinical-claim language present: {term!r}"


@pytest.mark.unit
def test_readiness_report_contains_human_review_needed():
    a = tr.assess_run(None)
    text = (a["disclaimer"] + " " + " ".join(a["limitations"])).lower()
    assert ("human review" in text) or ("책임은 연구자" in text) or ("전문가" in text)
