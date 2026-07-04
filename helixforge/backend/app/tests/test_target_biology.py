"""Phase 5 — target biology plausibility review (deterministic, conservative).

Verifies the review never fabricates pathway biology, keeps clinical precedent
distinct from efficacy, flags missing biomarker data, and emits only high-level
research-need next steps (no wet-lab protocol content).
"""
from __future__ import annotations

import pytest

from app.services import target_biology_review as tbr


def _egfr_target():
    return {
        "id": "tgt-EGFR",
        "target_chembl_id": "CHEMBL203",
        "pref_name": "EGFR",
        "organism": "Homo sapiens",
        "target_type": "SINGLE PROTEIN",
        "evidence_count": 6,
        "clinical_precedent_count": 3,
        "activity_availability": True,
    }


def _empty_target():
    return {
        "id": "tgt-ORPHAN",
        "target_chembl_id": "CHEMBL999999",
        "pref_name": "ORPHANX",
        "organism": "Homo sapiens",
        "target_type": "SINGLE PROTEIN",
        "evidence_count": 0,
        "clinical_precedent_count": 0,
        "activity_availability": False,
    }


@pytest.mark.unit
def test_target_biology_review_requires_evidence_or_assumption():
    r = tbr.review_target(_empty_target(), [])
    # Zero-evidence target must be low confidence and carry explicit uncertainty.
    assert r["confidence"] < 0.5
    assert len(r["uncertainty_reasons"]) > 0
    # And at least one dimension flags missing evidence.
    assert any("evidence" in d["uncertainty"].lower() for d in r["dimensions"] if d["uncertainty"])


@pytest.mark.unit
def test_target_biology_no_fabricated_pathway():
    r = tbr.review_target(_empty_target(), [])
    text = (r["pathway_context"] + " " + r["mechanism_summary"]).lower()
    # Honest deferral, not an invented pathway name.
    assert "expert" in text or "not" in text
    # No fabricated specific canonical pathway names.
    for invented in ("mapk", "pi3k", "wnt signaling", "jak-stat", "ras/raf"):
        assert invented not in text


@pytest.mark.unit
def test_target_review_warns_missing_biomarker():
    r = tbr.review_target(_egfr_target(), [])
    in_next_steps = any("biomarker" in s.lower() for s in r["expert_next_steps"])
    bm_dim = next(d for d in r["dimensions"] if d["name"] == "Biomarker availability")
    weak_biomarker_dim = bm_dim["score"] <= 2 and "biomarker" in bm_dim["uncertainty"].lower()
    assert in_next_steps or weak_biomarker_dim


@pytest.mark.unit
def test_target_review_clinical_precedent_is_not_efficacy():
    r = tbr.review_target(_egfr_target(), [])
    status_text = r["clinical_precedent_status"].lower()
    for banned in ("efficacy", "proven", "cure"):
        assert banned not in status_text
    cp_dim = next(d for d in r["dimensions"] if d["name"] == "Clinical precedent")
    assert "precedent" in cp_dim["rationale"].lower()


@pytest.mark.unit
def test_target_review_high_level_next_steps_no_protocol():
    r = tbr.review_target(_egfr_target(), [])
    joined = " ".join(r["expert_next_steps"]).lower()
    for banned in ("reagent", "reaction", "dissolve", "heat to", "dose", "dosage",
                   "mg", "synthesis", "protocol step"):
        assert banned not in joined
    assert 2 <= len(r["expert_next_steps"]) <= 4


@pytest.mark.unit
def test_review_run_smoke():
    out = tbr.review_run(None)
    assert "reviews" in out
    assert "status_distribution" in out
    assert isinstance(out["reviews"], list)
    assert isinstance(out["status_distribution"], dict)
