"""Phase 5 — activity normalization, medchem review, applicability, language lint."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    activity_normalization as an,
    applicability_domain as ad,
    medchem_review as mc,
    scientific_language_linter as sll,
)

client = TestClient(app)


# ---- Activity normalization ----
@pytest.mark.unit
def test_convert_um_to_nm():
    r = an.normalize_record({"standard_type": "IC50", "standard_relation": "=",
                             "standard_value": 1, "standard_units": "uM", "assay_confidence_score": 9})
    assert r["normalized_value_nm"] == 1000.0
    assert r["unit_conversion_status"] == "OK"


@pytest.mark.unit
def test_convert_mm_to_nm():
    r = an.normalize_record({"standard_type": "Ki", "standard_relation": "=",
                             "standard_value": 2, "standard_units": "mM"})
    assert r["normalized_value_nm"] == 2_000_000.0


@pytest.mark.unit
def test_unsupported_unit_warns():
    r = an.normalize_record({"standard_type": "IC50", "standard_value": 5, "standard_units": "ug.mL-1"})
    assert r["unit_conversion_status"] == "UNSUPPORTED"
    assert any("unsupported" in w.lower() for w in r["warnings"])


@pytest.mark.unit
def test_relation_less_than_penalty():
    eq = an.normalize_record({"standard_type": "IC50", "standard_relation": "=", "standard_value": 100, "standard_units": "nM"})
    lt = an.normalize_record({"standard_type": "IC50", "standard_relation": "<", "standard_value": 100, "standard_units": "nM"})
    assert lt["relation_penalty"] > eq["relation_penalty"]
    assert lt["reliability_score"] < eq["reliability_score"]


@pytest.mark.unit
def test_missing_assay_confidence_conservative():
    r = an.normalize_record({"standard_type": "IC50", "standard_relation": "=", "standard_value": 10, "standard_units": "nM"})
    assert r["assay_confidence_status"] == "UNKNOWN"


@pytest.mark.unit
def test_ic50_not_mixed_with_ec50():
    recs = [{"molecule_chembl_id": "M1", "standard_type": "IC50", "standard_relation": "=", "standard_value": 10, "standard_units": "nM"},
            {"molecule_chembl_id": "M1", "standard_type": "EC50", "standard_relation": "=", "standard_value": 10, "standard_units": "nM"}]
    out = an.normalize_activities(recs)
    assert "IC50" in out["endpoint_summaries"] and "EC50" in out["endpoint_summaries"]
    assert out["endpoint_summaries"]["IC50"]["count"] == 1
    assert out["endpoint_summaries"]["EC50"]["count"] == 1


@pytest.mark.unit
def test_outlier_flagging():
    recs = [{"molecule_chembl_id": f"M{i}", "standard_type": "IC50", "standard_relation": "=",
             "standard_value": 100, "standard_units": "nM"} for i in range(8)]
    recs.append({"molecule_chembl_id": "Mout", "standard_type": "IC50", "standard_relation": "=",
                 "standard_value": 1, "standard_units": "M"})  # 1 M = huge, extreme pchembl
    out = an.normalize_activities(recs)
    assert any(r["outlier_flag"] for r in out["normalized"])


@pytest.mark.unit
def test_duplicate_activity_grouping():
    recs = [{"molecule_chembl_id": "Mdup", "standard_type": "IC50", "standard_relation": "=", "standard_value": 10, "standard_units": "nM"},
            {"molecule_chembl_id": "Mdup", "standard_type": "IC50", "standard_relation": "=", "standard_value": 12, "standard_units": "nM"}]
    out = an.normalize_activities(recs)
    dgids = [r["duplicate_group_id"] for r in out["normalized"] if r["duplicate_group_id"]]
    assert len(dgids) >= 1


@pytest.mark.unit
def test_candidate_score_uses_activity_reliability():
    high = an.molecule_activity_reliability([{"molecule_chembl_id": "M", "standard_type": "IC50",
        "standard_relation": "=", "standard_value": 5, "standard_units": "nM",
        "pchembl_value": 8.3, "assay_confidence_score": 9}])
    low = an.molecule_activity_reliability([{"molecule_chembl_id": "M", "standard_type": "IC50",
        "standard_relation": ">", "standard_value": 5, "standard_units": "ug.mL-1"}])
    assert high["reliability_score"] > low["reliability_score"]
    assert high["confidence_tier"] == "high"


# ---- MedChem ----
@pytest.mark.unit
@pytest.mark.local_tool
def test_medchem_invalid_molecule_rejected():
    r = mc.review_molecule("not_a_smiles")
    assert r["medchem_status"] in ("REJECT_INVALID", "LOW_CONFIDENCE")


@pytest.mark.unit
@pytest.mark.local_tool
def test_veber_and_lead_likeness_computed():
    r = mc.review_molecule("CC(=O)Oc1ccccc1C(=O)O")  # aspirin
    if r.get("rdkit_valid"):
        assert "veber_review" in r and "pass" in r["veber_review"]
        assert "lead_likeness_review" in r


@pytest.mark.unit
@pytest.mark.local_tool
def test_medchem_alerts_do_not_include_synthesis_details():
    r = mc.review_molecule("O=CCl")  # acyl halide alert
    text = str(r).lower()
    for banned in ("reflux", "reagent", "step 1", "dissolve", "heat to", "yield"):
        assert banned not in text


@pytest.mark.unit
@pytest.mark.local_tool
def test_medchem_report_no_overclaim():
    r = mc.review_molecule("CC(=O)Oc1ccccc1C(=O)O")
    text = str(r).lower()
    for banned in ("cure", "proven efficacy", "clinically validated", "safe and effective"):
        assert banned not in text


# ---- Applicability ----
@pytest.mark.unit
@pytest.mark.local_tool
def test_applicability_unknown_without_reference():
    r = ad.assess_molecule("CCO", [])
    assert r["domain_status"] == "UNKNOWN"


@pytest.mark.unit
@pytest.mark.local_tool
@pytest.mark.skipif(not ad.RDKIT, reason="RDKit unavailable")
def test_applicability_out_of_domain_low_similarity():
    r = ad.assess_molecule("CCO", ["c1ccc2c(c1)ncc3c2CCCC3", "C1CCCCC1CCCCCCNc1ncncn1"])
    assert r["domain_status"] in ("OUT_OF_DOMAIN", "BORDERLINE", "IN_DOMAIN")
    assert r["nearest_neighbor_similarity"] is not None


@pytest.mark.unit
@pytest.mark.local_tool
@pytest.mark.skipif(not ad.RDKIT, reason="RDKit unavailable")
def test_applicability_duplicate_low_novelty():
    r = ad.assess_molecule("CC(=O)Oc1ccccc1C(=O)O", ["CC(=O)Oc1ccccc1C(=O)O", "CCO"])
    assert r["is_near_duplicate"] is True
    assert r["confidence_adjustment"] <= 0


# ---- Scientific language lint ----
@pytest.mark.unit
def test_language_lint_blocks_clinical_validation_claim():
    assert sll.check("This is clinically validated and safe and effective.")["status"] == "BLOCKED"


@pytest.mark.unit
def test_language_lint_blocks_korean_overclaim():
    assert sll.check("임상 검증 완료. 안전성이 보장된다.")["status"] == "BLOCKED"


@pytest.mark.unit
def test_language_rewrite_conservative():
    r = sll.rewrite_safe("We discovered a drug with proven efficacy.")
    assert r["changed"] is True
    assert "discovered a drug" not in r["rewritten"].lower()


@pytest.mark.unit
def test_language_lint_forbidden_not_auto_paraphrased():
    r = sll.rewrite_safe("합성 경로: step-by-step synthesis.")
    # forbidden content remains flagged (not silently rewritten away)
    assert r["residual_status"] == "BLOCKED"


# ---- Endpoints ----
@pytest.mark.integration
def test_professional_science_endpoints():
    assert client.post("/api/activities/normalize", json={"records": []}).status_code == 200
    assert client.post("/api/medchem/review-molecule", json={"smiles": "CCO"}).status_code == 200
    assert client.post("/api/applicability/assess-molecule", json={"smiles": "CCO", "reference_smiles": ["CCN"]}).status_code == 200
    assert client.post("/api/language-lint/check", json={"text": "cures cancer guaranteed"}).status_code == 200
