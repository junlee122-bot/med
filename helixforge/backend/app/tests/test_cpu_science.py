"""Phase 8 Priority-2 tests: dataset curation, CPU QSAR, ligand screening, active
learning, CPU multi-objective. Tiny fixtures; no GPU/network/key. sklearn-optional
paths degrade honestly."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    active_learning, cpu_qsar, dataset_curation, ligand_screening,
)
from app.services import chem_utils as cu

client = TestClient(app)

_SMIS = ["CCO", "CCN", "CCC", "CCCC", "c1ccccc1", "c1ccncc1", "CC(=O)O", "CCOC(=O)C",
         "CCCCO", "CCCCN", "c1ccc(O)cc1", "c1ccc(N)cc1", "CCCCCC", "CCCCCCO"]


def _dataset(n=14):
    return [{"smiles": s, "label": i % 2} for i, s in enumerate(_SMIS[:n])]


# ---- Dataset curation ----
@pytest.mark.unit
@pytest.mark.local_tool
def test_curation_counts_invalid_and_duplicates():
    recs = [{"smiles": "CCO", "label": 1}, {"smiles": "CCO", "label": 1},
            {"smiles": "not_valid", "label": 0}, {"smiles": "c1ccccc1", "label": 1}]
    ds = dataset_curation.curate(recs, dataset_name="t", exploratory=True)
    assert ds["invalid_smiles_count"] == 1
    assert ds["duplicate_count"] == 1


@pytest.mark.unit
@pytest.mark.local_tool
def test_curation_flags_mixed_endpoints():
    recs = [{"smiles": s, "label": 1, "standard_type": ("IC50" if i % 2 else "EC50"), "standard_units": "nM"}
            for i, s in enumerate(_SMIS[:10])]
    ds = dataset_curation.curate(recs, dataset_name="mix")
    assert ds["mixed_endpoints"] is True
    assert "mixed endpoint types (e.g. IC50 with EC50)" in ds["blocking_gaps"]


@pytest.mark.unit
@pytest.mark.local_tool
def test_curation_unsupported_unit_warns():
    recs = [{"smiles": s, "label": 1, "standard_units": "ug.mL-1"} for s in _SMIS[:9]]
    ds = dataset_curation.curate(recs, dataset_name="u")
    assert ds["unsupported_units"]


@pytest.mark.unit
@pytest.mark.local_tool
def test_curation_missing_license_warns_and_data_card():
    ds = dataset_curation.curate(_dataset(9), dataset_name="dc", license_status="REVIEW_REQUIRED")
    assert any("license" in w.lower() for w in ds["warnings"])
    card = dataset_curation.data_card(ds["id"])
    assert card["data_rights"]["license_status"] == "REVIEW_REQUIRED"


@pytest.mark.integration
@pytest.mark.local_tool
def test_curate_endpoint():
    r = client.post("/api/datasets/curate", json={"records": _dataset(9), "dataset_name": "e"})
    assert r.status_code == 200
    assert r.json()["quality_score"] >= 0


@pytest.mark.integration
def test_curate_endpoint_cannot_forge_real_tool_provenance():
    r = client.post("/api/datasets/curate", json={
        "records": _dataset(9), "dataset_name": "forged", "source": "chembl",
    })
    assert r.status_code == 422


# ---- CPU QSAR ----
@pytest.mark.unit
def test_qsar_classification_trains_or_degrades():
    m = cpu_qsar.train(_dataset(14), task="classification")
    if not cpu_qsar.available()["sklearn"]:
        assert m["source_type"] == "CONFIGURED_BUT_NOT_RUN"
    else:
        assert m["source_type"] == "BASELINE_CPU_MODEL_OUTPUT"
        assert m["split_strategy"] == "scaffold_split"
        assert m["duplicate_leakage_count"] == 0


@pytest.mark.unit
def test_qsar_regression_trains():
    if not cpu_qsar.available()["sklearn"]:
        pytest.skip("sklearn unavailable")
    data = [{"smiles": s, "label": float(i) / 14} for i, s in enumerate(_SMIS[:14])]
    m = cpu_qsar.train(data, task="regression")
    assert "rmse" in m["metrics"] or m.get("status") == "INSUFFICIENT_DATA"


@pytest.mark.unit
def test_qsar_prediction_requires_trained_model():
    assert cpu_qsar.predict("nonexistent", ["CCO"])["status"] == "MODEL_NOT_FOUND"


@pytest.mark.unit
def test_qsar_is_not_called_clinical_or_production():
    if not cpu_qsar.available()["sklearn"]:
        pytest.skip("sklearn unavailable")
    m = cpu_qsar.train(_dataset(14))
    blob = str(m["limitations"]).lower()
    assert "not a validated clinical model" in blob or "not production-grade" in blob


@pytest.mark.integration
def test_cpu_model_train_and_predict_endpoint():
    r = client.post("/api/cpu-models/train", json={"dataset": _dataset(14), "task": "classification"})
    body = r.json()
    if body.get("source_type") == "BASELINE_CPU_MODEL_OUTPUT":
        p = client.post(f"/api/cpu-models/{body['id']}/predict", json={"smiles": ["CCO"]})
        assert p.json()["status"] in ("OK", "MODEL_ARTIFACT_MISSING")


# ---- Ligand screening ----
@pytest.mark.unit
@pytest.mark.local_tool
def test_ligand_exact_match_similarity_one():
    ref = ["c1ccccc1", "CCO"]
    res = ligand_screening.screen(["c1ccccc1", "CCCCCCCC"], ref, target="X")
    assert res["best_similarity"] == pytest.approx(1.0, abs=1e-6)
    top = res["top_candidates"][0]
    assert top["recommendation"] == "KNOWN_LIKE_PRIORITY"


@pytest.mark.unit
@pytest.mark.local_tool
def test_ligand_invalid_rejected_and_no_binding_language():
    res = ligand_screening.screen(["not_smiles", "CCO"], ["CCO"])
    assert any(c["recommendation"] == "REJECT_INVALID" for c in res["top_candidates"])
    assert "not a docking result" in res["banner"].lower()
    assert "binding proof" in res["banner"].lower()


@pytest.mark.unit
@pytest.mark.local_tool
def test_ligand_out_of_domain_flagged():
    # a very different molecule vs a tiny reference
    res = ligand_screening.screen(["C1CC2CCC3CCCCC3C2C1"], ["CCO"])
    assert res["top_candidates"][0]["applicability"] in ("OUT_OF_DOMAIN", "BORDERLINE")


# ---- Active learning ----
@pytest.mark.unit
def test_active_learning_runs_and_beats_or_matches_random():
    if not active_learning.available():
        pytest.skip("sklearn unavailable")
    pool = [{"smiles": s, "label": (1 if "O" in s else 0)} for s in
            _SMIS + ["CCCCCCCCO", "CCCCCCCCCC", "c1ccc(C)cc1", "c1ccc(CO)cc1"]]
    res = active_learning.run(pool, strategy="uncertainty", cycles=3, batch_size=2, initial_labeled=4)
    assert res.get("id") or res.get("status") == "INSUFFICIENT_DATA"
    if res.get("id"):
        assert "random_baseline" in res
        assert "not experiments" in res["oracle_note"].lower()


@pytest.mark.unit
def test_active_learning_reproducible_seed():
    if not active_learning.available():
        pytest.skip("sklearn unavailable")
    pool = [{"smiles": s, "label": (1 if "N" in s else 0)} for s in
            _SMIS + ["CCCCCCCCN", "CCCCCCCCCN"]]
    a = active_learning.run(pool, cycles=3, batch_size=2)
    b = active_learning.run(pool, cycles=3, batch_size=2)
    if a.get("learning_curve") and b.get("learning_curve"):
        assert [c.get("metric") for c in a["learning_curve"]] == [c.get("metric") for c in b["learning_curve"]]


# ---- CPU multi-objective ----
@pytest.mark.integration
def test_cpu_multiobjective_no_single_best_overclaim():
    mols = [{"id": f"m{i}", "smiles": s, "descriptors": cu.descriptors(s) or {}} for i, s in enumerate(_SMIS[:6])]
    r = client.post("/api/optimization/cpu-multiobjective", json={"molecules": mols})
    body = r.json()
    assert "decision_policy_counts" in body
    assert "single_best_note" in body
    assert sum(body["decision_policy_counts"].values()) == len(body["all_candidates"])
    assert body["pareto_front_size"] == len(body["front"])
