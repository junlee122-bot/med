"""Phase 7 — docs describe the Fable role honestly and carry the right limitations."""
from pathlib import Path

import pytest

DOCS = Path(__file__).resolve().parent.parent.parent.parent / "docs"
P7_DOCS = ["HYBRID_FABLE5_AGENTIC_LAYER.md", "LLM_ROUTER_AND_COST_GUARD.md",
           "TRUE_RETROSPECTIVE_REDISCOVERY.md", "SAFE_OPTIMIZATION_LOOP.md",
           "HYBRID_SAFETY_AND_FALLBACK.md", "HYBRID_REPLAY_MODE.md", "PHASE7_CHANGELOG.md",
           "FABLE5_USAGE_RUNBOOK_EN.md", "FABLE5_USAGE_RUNBOOK_KO.md"]


def _read(name: str) -> str:
    return (DOCS / name).read_text(encoding="utf-8")


@pytest.mark.unit
def test_phase7_docs_exist():
    for d in P7_DOCS:
        assert (DOCS / d).exists(), f"missing doc {d}"


@pytest.mark.unit
def test_docs_no_autonomous_overclaim():
    for d in P7_DOCS:
        low = _read(d).lower()
        assert "17 agents are fully autonomous" not in low
        assert "discovered a drug" not in low
        assert "validated efficacy" not in low


@pytest.mark.unit
def test_docs_describe_fable_role():
    low = _read("HYBRID_FABLE5_AGENTIC_LAYER.md").lower()
    assert "dynamic planning" in low
    assert "hypothesis" in low
    assert "critic" in low or "critique" in low
    assert "deterministic" in low and "fallback" in low


@pytest.mark.unit
def test_docs_include_cost_guard():
    low = _read("LLM_ROUTER_AND_COST_GUARD.md").lower()
    assert "budget" in low and ("cost guard" in low or "cost ledger" in low)


@pytest.mark.unit
def test_docs_include_true_rediscovery_limitations():
    low = _read("TRUE_RETROSPECTIVE_REDISCOVERY.md").lower()
    assert "does not prove" in low
    assert "limitation" in low


@pytest.mark.unit
def test_docs_include_optimization_loop_limitations():
    low = _read("SAFE_OPTIMIZATION_LOOP.md").lower()
    assert "no synthesis" in low
    assert "limitation" in low


@pytest.mark.unit
def test_changelog_states_fable_optional_and_fallback():
    low = _read("PHASE7_CHANGELOG.md").lower()
    assert "optional" in low and "fallback" in low
    assert "no hidden chain-of-thought" in low
