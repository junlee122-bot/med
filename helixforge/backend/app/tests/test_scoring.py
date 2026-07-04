"""Offline-safe unit tests for the scoring engine and safety lint."""
import pytest

from app.services import scoring
from app.services.safety_lint import lint_report, rewrite_overclaims

pytestmark = pytest.mark.unit


def test_molecule_scoring_invalid_zero():
    res = scoring.score_molecule({"valid": False, "smiles": "C1CC(C("})
    assert res["score"] == 0.0
    assert "Reject" in res["recommendation"]


def test_molecule_scoring_blocked_do_not_advance():
    res = scoring.score_molecule({"valid": True, "qed": 0.9, "lipinski_pass": True,
                                  "activity_proxy_score": 0.9, "safety_status": "BLOCKED"})
    assert res["recommendation"] == "Do not advance"


def test_molecule_scoring_high_quality_reasonable():
    res = scoring.score_molecule({"valid": True, "qed": 0.85, "lipinski_pass": True,
                                  "activity_proxy_score": 0.8, "descriptor_druglikeness_score": 0.9,
                                  "tdc_readiness_score": 0.7, "provenance_confidence": 0.8,
                                  "novelty_or_diversity_proxy": 0.6, "safety_status": "PASS", "uncertainty": 0.1})
    assert res["score"] >= 55


def test_target_scoring_conservative_with_missing_data():
    res = scoring.score_target({})  # everything missing
    assert res["warnings"], "missing inputs must emit warnings"
    assert 0 <= res["score"] <= 100
    # A fully-specified strong target should outscore the empty one.
    strong = scoring.score_target({
        "target_name_match": 1.0, "target_type_score": 1.0, "organism_score": 1.0,
        "chembl_confidence_score": 0.9, "pubmed_evidence_score": 1.0,
        "clinical_precedent_score": 1.0, "molecule_activity_availability": 1.0,
        "safety_penalty": 0.0, "uncertainty_penalty": 0.0})
    assert strong["score"] > res["score"]


def test_safety_lint_blocks_forbidden_report():
    md = "## Synthesis\nStep-by-step synthesis with reaction conditions and reagent list.\n"
    res = lint_report(md)
    assert res["status"] == "BLOCKED"
    assert res["export_safe"] is False


def test_safety_lint_flags_missing_disclaimer():
    res = lint_report("A neutral report with no disclaimer.")
    assert res["status"] in ("REVIEW_REQUIRED", "BLOCKED")


def test_rewrite_overclaims():
    res = rewrite_overclaims("This is a validated cure with proven efficacy.")
    assert res["changed"]
    assert "validated cure" not in res["rewritten"].lower()
    assert "in-silico hypothesis for expert review" in res["rewritten"]
