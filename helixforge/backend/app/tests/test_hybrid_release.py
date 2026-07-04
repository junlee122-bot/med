"""Phase 7 — release readiness + rubric reflect the hybrid Fable layer."""
import pytest

from app.services import release_readiness, rubric_scorecard


@pytest.mark.integration
def test_release_readiness_includes_hybrid_categories():
    r = release_readiness.compute()
    assert "hybrid_readiness" in r["checks"]
    labels = " ".join(c["label"] for c in r["checks"]["hybrid_readiness"]).lower()
    assert "hybrid planning" in labels
    assert "hypothesis reasoning" in labels
    assert "semantic critic" in labels
    assert "cost guard" in labels
    assert "true rediscovery" in labels
    assert "optimization loop" in labels


@pytest.mark.integration
def test_release_still_allows_deterministic_demo_with_warning():
    # Hybrid checks are NON-blocking: a deterministic project is never blocked by
    # the absence of a Fable run.
    r = release_readiness.compute()
    for c in r["checks"]["hybrid_readiness"]:
        assert c["blocking"] is False
    assert r["status"] in ("NOT_READY", "DRAFT_READY", "PROPOSAL_READY", "DEMO_READY", "SUBMISSION_READY")


@pytest.mark.integration
def test_release_warns_if_no_llm_snapshot():
    # In a fresh DB with no real LLM run/snapshot, a (non-blocking) warning is present.
    r = release_readiness.compute()
    if r["hybrid_summary"]["real_llm_calls"] == 0 and r["hybrid_summary"]["hybrid_snapshots"] == 0:
        assert any("fable" in w.lower() or "hybrid" in w.lower() for w in r["warnings"])


@pytest.mark.unit
def test_rubric_scorecard_mentions_fable_layer():
    card = rubric_scorecard.compute()
    blob = str(card).lower()
    assert "fable" in blob or "하이브리드" in blob


@pytest.mark.integration
def test_release_rubric_mapping_mentions_hybrid():
    r = release_readiness.compute()
    assert "fable" in r["rubric_mapping"]["agent_originality"].lower()
    assert "hybrid_summary" in r
