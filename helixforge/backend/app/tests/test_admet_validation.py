"""Tests for the ADMET baseline validation protocol.

These tests are robust to whichever optional dependencies (scikit-learn / RDKit)
are actually installed: they branch on the module's own SKLEARN/RDKIT flags and
skip the pieces that require an absent tool. The core provenance-honesty
invariants (no fabricated metrics, no safety overclaim, always-present
limitations) are asserted in every environment.
"""
from __future__ import annotations

import pytest

from app.services import admet_validation


@pytest.mark.unit
def test_admet_validation_skips_without_optional_dependencies(monkeypatch):
    """With sklearn forced off, no model is trained and no metrics are fabricated."""
    monkeypatch.setattr(admet_validation, "SKLEARN", False)
    result = admet_validation.run_validation(dataset_name="demo_logP", task="regression")
    assert result["status"] == "SKIPPED_MISSING_DEPENDENCY"
    assert result["source_type"] == "CONFIGURED_BUT_NOT_RUN"
    assert result["metrics"] == {}


@pytest.mark.unit
def test_no_admet_claim_without_trained_model(monkeypatch):
    """The skipped protocol must never assert safety/clinical claims."""
    monkeypatch.setattr(admet_validation, "SKLEARN", False)
    result = admet_validation.run_validation()
    text = str(result).lower()
    for banned in ("validated safety", "clinically", "safe and effective", "approved"):
        assert banned not in text


@pytest.mark.unit
def test_admet_report_contains_limitations(monkeypatch):
    """limitations must be a non-empty list in BOTH skipped and completed cases."""
    # Skipped case.
    monkeypatch.setattr(admet_validation, "SKLEARN", False)
    skipped = admet_validation.run_validation()
    assert isinstance(skipped["limitations"], list) and skipped["limitations"]

    # Completed case (only when both deps are truly available).
    monkeypatch.undo()
    if admet_validation.SKLEARN and admet_validation.RDKIT:
        completed = admet_validation.run_validation()
        assert isinstance(completed["limitations"], list) and completed["limitations"]


@pytest.mark.unit
@pytest.mark.local_tool
def test_duplicate_leakage_detected():
    """A canonical SMILES present on both sides of the split is flagged."""
    if not admet_validation.RDKIT:
        pytest.skip("RDKit not installed; canonicalization unavailable")
    lk = admet_validation.leakage_checks(["CCO", "CCN"], ["CCO", "c1ccccc1"])
    assert lk["duplicate_canonical_smiles_across_split"] >= 1


@pytest.mark.unit
@pytest.mark.local_tool
def test_baseline_output_labeled_correctly():
    """When both deps are present, a trained baseline is labeled BASELINE_MODEL_OUTPUT."""
    if not (admet_validation.SKLEARN and admet_validation.RDKIT):
        pytest.skip("scikit-learn and RDKit required to train a baseline")
    result = admet_validation.run_validation(dataset_name="demo_logP", task="regression")
    assert result["status"] == "COMPLETED"
    assert result["source_type"] == "BASELINE_MODEL_OUTPUT"
    # At least one genuinely numeric metric must be present.
    numeric = [v for v in result["metrics"].values() if isinstance(v, (int, float))]
    assert numeric, f"expected a numeric metric, got {result['metrics']}"
