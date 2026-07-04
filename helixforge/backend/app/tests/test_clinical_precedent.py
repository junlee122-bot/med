"""Clinical precedent review — safety + logic unit tests.

Verifies the module never emits efficacy/treatment/dosing language, correctly
classifies endpoint categories, labels an empty trial set as no precedent, and
surfaces trial-termination signals.
"""
from __future__ import annotations

import uuid

import pytest

from app.models.schemas import utcnow
from app.services import clinical_precedent_review as cpr
from app.storage import db


def _trial(title: str = "", claim: str = "") -> dict:
    return {
        "title": title,
        "claim": claim,
        "identifier_type": "NCT",
        "source_name": "ClinicalTrials.gov",
    }


@pytest.mark.unit
def test_clinical_precedent_no_efficacy_claim():
    trials = [
        _trial("Phase 2 study of drug X in advanced NSCLC", "Overall survival at 24 months"),
        _trial("Safety and tolerability of agent Y", "adverse events monitored"),
        _trial("Objective response rate of regimen Z", "response evaluated per RECIST"),
    ]
    review = cpr._review_trials("non-small cell lung cancer", "EGFR", trials)
    blob = str(review).lower()
    for forbidden in ("proven efficacy", "cure", "is effective", "recommended treatment", "dosage"):
        assert forbidden not in blob, f"forbidden phrase present: {forbidden!r}"
    assert "precedent" in review["disclaimer"].lower()
    assert review["precedent_strength"] in cpr.PRECEDENT_STRENGTHS


@pytest.mark.unit
def test_endpoint_category_extraction():
    assert cpr.classify_endpoint_category("Overall survival at 24 months") == "survival"
    assert cpr.classify_endpoint_category("Objective response rate") == "response_rate"
    assert cpr.classify_endpoint_category("Safety and tolerability") == "safety_tolerability"
    assert cpr.classify_endpoint_category("random text") == "other_unknown"


@pytest.mark.unit
def test_no_trials_labeled_no_precedent():
    # Helper on an empty trial list.
    empty = cpr._review_trials("some condition", "SOME_TARGET", [])
    assert empty["trial_count"] == 0
    assert empty["precedent_strength"] == "NO_PRECEDENT_FOUND"

    # Full path: a fresh run whose project has no evidence items.
    pid = f"proj-cpr-{uuid.uuid4().hex[:8]}"
    rid = f"run-cpr-{uuid.uuid4().hex[:8]}"
    db.insert("workflow_runs", {
        "id": rid, "project_id": pid, "created_at": utcnow(),
        "kind": "real_pipeline", "metrics": {}, "target_query": "SOME_TARGET",
        "condition": "some condition",
    })
    review = cpr.review_run(rid)
    assert review["run_id"] == rid
    assert review["trial_count"] == 0
    assert review["precedent_strength"] == "NO_PRECEDENT_FOUND"


@pytest.mark.unit
def test_termination_signal_detected():
    trials = [_trial("Study terminated early due to enrollment")]
    review = cpr._review_trials("cond", "target", trials)
    assert review["failure_or_termination_signals"]
    assert any("terminated" in s.lower() for s in review["failure_or_termination_signals"])
