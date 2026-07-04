"""Red-team suite tests: every adversarial probe must be defended, and the
Phase-4 high-value services (scorecard, plausibility, HWPX handoff, run configs)
must behave. These exercise EXISTING safety/honesty gates — no hazardous content."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import (
    hwpx_handoff, red_team, rubric_scorecard, run_config, scientific_plausibility,
)

client = TestClient(app)


# ---- Red-team suite ----
@pytest.mark.unit
def test_red_team_suite_all_scenarios_defended():
    res = red_team.run_suite()
    assert res["total"] == 18, "expected 18 red-team scenarios"
    failed = [r for r in res["results"] if not r["defended"]]
    assert res["status"] == "PASS", f"undefended scenarios: {[(f['id'], f['name'], f.get('error')) for f in failed]}"
    assert res["passed"] == res["total"]


@pytest.mark.unit
def test_red_team_covers_multiple_categories():
    res = red_team.run_suite()
    cats = set(res["by_category"].keys())
    assert {"safety", "overclaim", "provenance", "governance", "false_positive"}.issubset(cats)


@pytest.mark.unit
def test_red_team_does_not_falsely_block_own_policy():
    res = red_team.run_suite()
    fp = [r for r in res["results"] if r["category"] == "false_positive"]
    assert fp and all(r["defended"] for r in fp)


@pytest.mark.integration
def test_red_team_endpoint():
    r = client.get("/api/red-team/run")
    assert r.status_code == 200
    assert r.json()["status"] == "PASS"


# ---- Rubric scorecard ----
@pytest.mark.unit
def test_rubric_scorecard_weights_sum_to_100():
    assert sum(c["weight"] for c in rubric_scorecard.CRITERIA) == 100


@pytest.mark.unit
def test_rubric_scorecard_is_conservative_and_labeled():
    card = rubric_scorecard.compute()
    assert card["source_type"] == "HEURISTIC_ANALYSIS"
    assert "self-assessment" in card["disclaimer"].lower()
    assert 0 <= card["total_score"] <= 100
    # scientific validity must document a ceiling (no wet-lab validation)
    sci = next(c for c in card["criteria"] if c["key"] == "scientific_validity")
    assert sci["cap_reason"] and "습식" in sci["cap_reason"]
    assert sci["self_score"] <= 0.8


@pytest.mark.integration
def test_rubric_scorecard_endpoint():
    r = client.get("/api/rubric/scorecard")
    assert r.status_code == 200
    assert "criteria" in r.json()


# ---- Scientific plausibility ----
@pytest.mark.unit
def test_plausibility_flags_implausible_descriptors():
    mol = {"id": "m1", "valid": True, "descriptors": {"mol_weight": 2000, "logp": 12, "hbd": 20, "hba": 30, "tpsa": 400},
           "source_type": "REAL_TOOL_OUTPUT"}
    res = scientific_plausibility._check_molecule(mol)
    assert res["verdict"] == "IMPLAUSIBLE"


@pytest.mark.unit
def test_plausibility_accepts_druglike():
    mol = {"id": "m2", "valid": True, "descriptors": {"mol_weight": 350, "logp": 2.5, "hbd": 2, "hba": 5, "tpsa": 75},
           "source_type": "REAL_TOOL_OUTPUT"}
    assert scientific_plausibility._check_molecule(mol)["verdict"] == "PLAUSIBLE"


@pytest.mark.unit
def test_plausibility_run_handles_no_run():
    res = scientific_plausibility.check_run("nonexistent-run-id")
    assert res["status"] in ("NO_RUN", "REVIEW_REQUIRED", "PASS")


# ---- HWPX handoff ----
@pytest.mark.unit
def test_hwpx_handoff_blocks_are_export_safe():
    h = hwpx_handoff.build_handoff()
    assert h["block_count"] >= 8
    assert h["all_blocks_export_safe"] is True
    # paste text must be plain (no markdown backticks/bold)
    assert all("`" not in b["paste_text"] and "**" not in b["paste_text"] for b in h["blocks"])


# ---- Run config wizard ----
@pytest.mark.unit
def test_run_config_presets_are_real_targets():
    cfg = run_config.list_configs()
    assert len(cfg["presets"]) >= 6
    assert any(p["recommended"] for p in cfg["presets"])


@pytest.mark.unit
def test_run_config_validation_rejects_bad_input():
    bad = run_config.validate({"target_query": "", "max_results": 999})
    assert bad["valid"] is False
    assert len(bad["errors"]) >= 2


@pytest.mark.unit
def test_run_config_validation_normalizes_payload():
    ok = run_config.validate({"target_query": "BRAF", "condition": "melanoma", "max_results": 10})
    assert ok["valid"] is True
    assert ok["normalized_payload"]["target_query"] == "BRAF"


@pytest.mark.integration
def test_run_configs_endpoint():
    r = client.get("/api/run-configs")
    assert r.status_code == 200
    assert "presets" in r.json()
