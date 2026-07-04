"""Phase 5 — multi-objective Pareto optimisation over candidate molecules."""
import pytest

from app.services import pareto_optimization as pareto


@pytest.mark.unit
def test_pareto_identifies_non_dominated():
    mols = [
        {"id": "m1", "label": "A", "descriptors": {"qed": 0.9}, "pchembl_value": 9.0,
         "safety_status": "PASS", "composite_score": 90, "valid": True},
        {"id": "m2", "label": "B", "descriptors": {"qed": 0.5}, "pchembl_value": 6.0,
         "safety_status": "PASS", "composite_score": 50, "valid": True},
        {"id": "m3", "label": "C", "descriptors": {"qed": 0.3}, "pchembl_value": 5.0,
         "safety_status": "REVIEW_REQUIRED", "composite_score": 30, "valid": True},
    ]
    res = pareto.compute(mols)
    front_ids = {c["molecule_id"] for c in res["front"]}
    assert "m1" in front_ids  # the dominant molecule is on the front

    by_id = {c["molecule_id"]: c for c in res["all_candidates"]}
    assert by_id["m1"]["dominated"] is False
    assert by_id["m2"]["dominated"] is True
    assert by_id["m3"]["dominated"] is True
    assert by_id["m1"]["dominance_count"] == 2
    assert by_id["m1"]["pareto_rank"] == 1


@pytest.mark.unit
def test_missing_objective_penalizes_confidence():
    full = {"id": "full", "label": "Full", "descriptors": {"qed": 0.8}, "pchembl_value": 8.0,
            "safety_status": "PASS", "composite_score": 70, "valid": True}
    sparse = {"id": "sparse", "label": "Sparse", "descriptors": {},
              "safety_status": "PASS", "valid": True}  # no pchembl, no composite, no qed
    res = pareto.compute([full, sparse])
    by_id = {c["molecule_id"]: c for c in res["all_candidates"]}
    assert by_id["full"]["confidence"] > by_id["sparse"]["confidence"]
    assert len(by_id["sparse"]["missing_objectives"]) > len(by_id["full"]["missing_objectives"])


@pytest.mark.unit
def test_pareto_tradeoff_summary():
    mols = [
        {"id": "m1", "label": "A", "descriptors": {"qed": 0.9}, "pchembl_value": 9.0,
         "safety_status": "PASS", "composite_score": 90, "valid": True},
        {"id": "m2", "label": "B", "descriptors": {"qed": 0.5}, "pchembl_value": 6.0,
         "safety_status": "PASS", "composite_score": 50, "valid": True},
        {"id": "m3", "label": "C", "descriptors": {}, "safety_status": "REVIEW_REQUIRED",
         "valid": True},
    ]
    res = pareto.compute(mols)
    for c in res["all_candidates"]:
        assert isinstance(c["tradeoff_summary"], str)
        assert c["tradeoff_summary"].strip() != ""


@pytest.mark.unit
def test_no_single_best_overclaim():
    # Genuine trade-off: A has best activity but weaker safety; B is the opposite.
    mols = [
        {"id": "A", "label": "HighActivity", "descriptors": {"qed": 0.6}, "pchembl_value": 9.0,
         "safety_status": "REVIEW_REQUIRED", "composite_score": 60, "valid": True},
        {"id": "B", "label": "HighSafety", "descriptors": {"qed": 0.6}, "pchembl_value": 5.0,
         "safety_status": "PASS", "composite_score": 60, "valid": True},
    ]
    res = pareto.compute(mols)
    assert res["no_single_best"] is True
    # Neither molecule dominates the other, so both are on the front.
    front_ids = {c["molecule_id"] for c in res["front"]}
    assert front_ids == {"A", "B"}
    by_id = {c["molecule_id"]: c for c in res["all_candidates"]}
    assert by_id["A"]["dominated"] is False
    assert by_id["B"]["dominated"] is False


@pytest.mark.unit
def test_pareto_run_smoke():
    res = pareto.run(None)
    assert isinstance(res, dict)
    assert "front" in res
    assert "all_candidates" in res
