"""Unit tests for the professional-docs and scientific-whitepaper generators.

These are offline-safe: the generators degrade to honest "no run yet" text when
the DB is empty, so the assertions hold without any seeded run. They enforce the
governance guarantees (limitations present, no clinical overclaim, honest
source typing, human-responsibility disclaimer) rather than exact wording.
"""
from __future__ import annotations

import pytest

from app.services import professional_docs
from app.services import scientific_whitepaper
from app.services.professional_docs import ProfessionalDocType as DT


@pytest.mark.unit
def test_model_card_contains_limitations():
    md = professional_docs.generate(DT.MODEL_CARD)["markdown"].lower()
    assert "limitation" in md
    assert "clinically validated" not in md
    assert "regulatory approval granted" not in md


@pytest.mark.unit
def test_data_card_contains_sources_and_rights():
    md = professional_docs.generate(DT.DATA_CARD)["markdown"].lower()
    assert "sources" in md
    assert ("rights" in md) or ("attribution" in md)


@pytest.mark.unit
def test_validation_protocol_no_overclaim():
    md = professional_docs.generate(DT.VALIDATION_PROTOCOL)["markdown"].lower()
    assert "proven efficacy" not in md
    assert "clinically validated" not in md


@pytest.mark.unit
def test_risk_register_contains_safety_risks():
    md = professional_docs.generate(DT.RISK_REGISTER)["markdown"].lower()
    assert "safety" in md
    assert "mitigation" in md


@pytest.mark.unit
def test_traceability_matrix_links_requirements_to_evidence():
    md = professional_docs.generate(DT.TRACEABILITY_MATRIX)["markdown"].lower()
    assert "requirement" in md
    assert ("evidence" in md) or ("verification" in md) or ("test" in md)


@pytest.mark.unit
def test_what_we_do_not_claim_sheet_contains_no_wetlab():
    md = professional_docs.generate(DT.WHAT_WE_DO_NOT_CLAIM)["markdown"].lower()
    assert "wet-lab" in md
    assert ("do not claim" in md) or ("not claim" in md)


@pytest.mark.unit
def test_real_vs_replay_sheet_clear():
    md = professional_docs.generate(DT.REAL_VS_REPLAY_VS_NOT_RUN)["markdown"]
    assert "CONFIGURED_BUT_NOT_RUN" in md
    assert "RECORDED" in md


@pytest.mark.unit
def test_bundle_generates():
    documents = professional_docs.bundle()["documents"]
    assert len(documents) >= 6


@pytest.mark.unit
def test_whitepaper_contains_professional_sections():
    md = scientific_whitepaper.generate("en")["markdown"]
    assert "Evidence and claim grading" in md
    assert "Applicability domain" in md
    assert "Limitations" in md


@pytest.mark.unit
def test_whitepaper_no_clinical_overclaim():
    md = scientific_whitepaper.generate("en")["markdown"].lower()
    for term in ("cure", "proven efficacy", "clinically validated", "regulatory approval granted"):
        assert term not in md, f"forbidden overclaim present: {term!r}"


@pytest.mark.unit
def test_whitepaper_includes_limitations():
    md = scientific_whitepaper.generate("en")["markdown"].lower()
    assert "limitation" in md


@pytest.mark.unit
def test_whitepaper_source_legend_complete():
    md = scientific_whitepaper.generate("en")["markdown"]
    assert "CONFIGURED_BUT_NOT_RUN" in md
    assert "HEURISTIC_ANALYSIS" in md


@pytest.mark.unit
def test_whitepaper_korean():
    md = scientific_whitepaper.generate("ko")["markdown"]
    assert "책임은 연구자" in md
