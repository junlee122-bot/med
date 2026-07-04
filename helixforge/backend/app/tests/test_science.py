"""Scientific-depth tests: ChEMBL assay analysis, molecule diversity, scenarios."""
import pytest
from fastapi.testclient import TestClient

from app.data.scenarios import BY_ID, SCENARIOS
from app.main import app
from app.services import chembl_analysis, molecule_diversity

client = TestClient(app)


@pytest.mark.unit
def test_assay_summary_handles_missing_pchembl():
    acts = [{"activity_type": "IC50", "standard_units": "nM", "standard_value": "12",
             "molecule_chembl_id": "CHEMBL1"},
            {"activity_type": "IC50", "standard_units": "nM", "standard_value": "50",
             "molecule_chembl_id": "CHEMBL2"}]
    s = chembl_analysis.assay_quality_summary("CHEMBL203", acts)
    assert s["pchembl_available_count"] == 0
    assert any("pChEMBL" in w for w in s["warnings"])
    assert s["unique_molecule_count"] == 2


@pytest.mark.unit
def test_activity_proxy_units_conservative():
    # no comparable value → conservative default + ASSUMPTION label
    p = chembl_analysis.activity_proxy({"standard_units": "%", "standard_value": "80"})
    assert p["source_type"] == "ASSUMPTION"
    assert p["warning"]
    # nM value without pChEMBL → heuristic conversion, labeled HEURISTIC_ANALYSIS
    p2 = chembl_analysis.activity_proxy({"standard_units": "nM", "standard_value": "10"})
    assert p2["source_type"] == "HEURISTIC_ANALYSIS"
    assert 0.0 <= p2["score"] <= 1.0


@pytest.mark.local_tool
def test_duplicate_canonical_smiles_detected():
    if not molecule_diversity.rdkit_available():
        pytest.skip("RDKit not available")
    d = molecule_diversity.analyze_diversity(["CCO", "OCC", "c1ccccc1"])  # CCO and OCC are the same
    assert d["available"]
    assert len(d["duplicates"]) == 1


@pytest.mark.local_tool
def test_scaffold_count_computed_if_rdkit_available():
    if not molecule_diversity.rdkit_available():
        pytest.skip("RDKit not available")
    d = molecule_diversity.analyze_diversity(["c1ccccc1C", "c1ccccc1CC", "CCO"])
    assert d["scaffold_count"] >= 1
    assert d["diversity_score"] is not None


@pytest.mark.unit
def test_scenario_presets_load():
    r = client.get("/api/scenarios")
    assert r.status_code == 200
    assert r.json()["count"] == len(SCENARIOS) == 8
    assert "egfr-nsclc" in BY_ID


@pytest.mark.integration
def test_run_matrix_partial_failure_tolerant():
    # Unknown scenario ids must not crash the matrix.
    r = client.post("/api/scenarios/run-matrix", json={"scenario_ids": ["does-not-exist", "also-missing"]})
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 2
    assert all(x["status"] == "error" for x in body["results"])
    assert body["rediscovery_passed"] == 0


@pytest.mark.integration
def test_scenario_result_no_claim_when_target_not_found():
    # An unknown scenario yields an honest error result with no rediscovery claim.
    r = client.post("/api/scenarios/run-matrix", json={"scenario_ids": ["bogus"]})
    res = r.json()["results"][0]
    assert res["rediscovery_success"] is False
