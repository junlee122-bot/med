"""Phase 5 — docking protocol governance (honest capture, never binding proof)."""
from __future__ import annotations

import pytest

from app.services import docking_protocol as dp


@pytest.mark.unit
def test_docking_protocol_no_fake_score():
    rec = dp.create_protocol(mode="NOT_CONFIGURED")
    assert rec["scoring_status"] == "NO_SCORE"
    assert rec["source_type"] == "CONFIGURED_BUT_NOT_RUN"


@pytest.mark.unit
def test_docking_protocol_lints_missing_box():
    rec = dp.create_protocol(mode="REAL_VINA_FIXTURE_RUN", score=-8.5, box_center=None)
    result = dp.lint_protocol(rec)
    assert result["status"] == "BLOCKED"


@pytest.mark.unit
def test_fixture_only_status_honest():
    rec = dp.create_protocol(mode="FIXTURE_ONLY")
    assert rec["redocking_validation_status"] == "NOT_PERFORMED"
    assert rec["decoy_validation_status"] == "NOT_PERFORMED"


@pytest.mark.unit
def test_docking_report_no_binding_proof_claim():
    rec = dp.create_protocol(mode="NOT_CONFIGURED")
    text = str(rec).lower()
    assert "binding proof" not in text
    assert "binding confirmed" not in text
    assert any("prioritization signal" in lim.lower() for lim in rec["limitations"])


@pytest.mark.unit
def test_job_spec_has_no_prep_instructions():
    spec = dp.generate_job_spec("R1", [0, 0, 0], [20, 20, 20])
    text = str(spec).lower()
    for banned in ("reflux", "reagent", "dissolve", "add ", "protonate step",
                   "minimize with", "prepare the receptor by"):
        assert banned not in text


@pytest.mark.unit
def test_run_smoke():
    out = dp.run(None)
    assert isinstance(out, dict)
    assert "protocol" in out
    assert "lint" in out
