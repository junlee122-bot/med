"""Phase 8 integration tests: compute evaluation summary, release-readiness compute
categories (CPU-only never blocked by missing GPU), and export-safe compute submission
artifacts. No GPU/network/key."""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import compute_evaluation, compute_reports

client = TestClient(app)


# ---- Compute evaluation summary ----
@pytest.mark.unit
def test_compute_summary_has_all_dimensions():
    s = compute_evaluation.compute_summary(None)
    for key in ("cpu_model_quality", "ligand_screen", "active_learning", "optimization",
                "compute_efficiency", "reproducibility", "gpu_readiness"):
        assert key in s
    assert s["gpu_readiness"]["status"] == "CONFIGURED_NOT_RUN"


@pytest.mark.integration
def test_compute_summary_endpoint():
    r = client.get("/api/evaluation/compute-summary")
    assert r.status_code == 200
    assert r.json()["source_type"] == "HEURISTIC_ANALYSIS"


# ---- Release readiness compute categories ----
@pytest.mark.unit
def test_release_categories_gpu_never_blocks_cpu_submission():
    rc = compute_evaluation.release_categories(None)
    gpu = next(c for c in rc["categories"] if c["key"] == "GPU")
    assert gpu["blocks_submission"] is False
    assert gpu["status"] in ("CONFIGURED_NOT_RUN", "PARTIAL")
    # a GPU-less environment must not force NOT_READY solely because of GPU
    assert rc["status"] in ("SUBMISSION_READY", "PROPOSAL_READY", "TECHNICAL_DEMO_READY")


@pytest.mark.integration
def test_release_readiness_compute_endpoint():
    r = client.get("/api/release-readiness/compute")
    assert r.status_code == 200
    body = r.json()
    assert "cpu_only_note" in body
    assert body["blocking_count"] == 0 or all(
        c["blocks_submission"] or not c["blocking_issues"] for c in body["categories"])


# ---- Compute submission artifacts ----
@pytest.mark.unit
def test_all_compute_artifacts_export_safe():
    for kind in compute_reports.ARTIFACT_TYPES:
        art = compute_reports.generate(kind)
        assert art["export_safe"] is True, f"{kind} not export-safe: {art['safety_lint']}"
        assert art["safety_lint"]["status"] != "BLOCKED"


@pytest.mark.unit
def test_compute_artifacts_disclose_configured_not_run_and_no_binding_proof():
    gpu = compute_reports.generate("external_gpu_readiness")
    md = gpu["markdown"].lower()
    assert "configured_not_run" in md or "configured-not-run" in md
    cap = compute_reports.generate("cpu_scientific_capability")
    assert "not binding proof" in cap["markdown"].lower()


@pytest.mark.integration
def test_generate_compute_artifact_endpoint():
    r = client.post("/api/compute/artifacts/generate", json={"kind": "compute_security_appendix"})
    assert r.status_code == 200
    assert r.json()["export_safe"] is True
    all_r = client.post("/api/compute/artifacts/generate", json={"kind": "all"})
    assert len(all_r.json()["artifacts"]) == len(compute_reports.ARTIFACT_TYPES)


# ---- Compute-planner agent (Section 25) ----
@pytest.mark.integration
def test_compute_planner_agent_records_decisions_observable_only():
    r = client.post("/api/compute/plan-agent", json={"workflow_run_id": "agent-run-1"})
    assert r.status_code == 200
    body = r.json()
    assert body["compute_profile"]
    assert len(body["compute_decisions"]) > 0
    # observable trace only — no hidden chain-of-thought
    blob = str(body).lower()
    assert "<thinking>" not in blob and "chain-of-thought" not in blob
    # no GPU present ⇒ CPU substitutes, no shell
    assert "rm -rf" not in blob and "step-by-step synthesis" not in blob
    assert any(c["ok"] for c in body["validation_checks"] if c["check"] == "no_shell_or_synthesis_steps")


@pytest.mark.unit
def test_compute_planner_agent_no_gpu_uses_cpu_substitute():
    from app.agents.base import AgentContext
    from app.agents.compute_planner_agent import ComputePlannerAgent
    ctx = AgentContext(project_id="p", workflow_run_id="wr")
    out = ComputePlannerAgent().run(ctx)
    assert out.source_types == ["HEURISTIC_ANALYSIS"]
    assert all(d["selected_backend"] in ("LOCAL_CPU", "CONFIG_ONLY") for d in ctx.shared["compute_decisions"])


# ---- Hybrid pipeline records compute decisions ----
@pytest.mark.integration
def test_hybrid_pipeline_records_compute_decisions():
    from app.services import compute_aware_planner, hybrid_pipeline
    out = hybrid_pipeline.run_hybrid_pipeline({
        "condition": "NSCLC", "target_query": "EGFR", "mode": "DETERMINISTIC_ONLY",
        "max_pubmed_results": 2, "run_true_rediscovery": False, "run_optimization_loop": False,
        "run_semantic_critic": False,
    })
    assert out["compute_profile"]
    assert len(out["compute_decisions"]) > 0
    # decisions are persisted against the run and retrievable
    persisted = compute_aware_planner.get_decisions(out["workflow_run_id"])
    assert len(persisted) == len(out["compute_decisions"])
    # no GPU present ⇒ CPU substitutes only; no fabricated GPU result
    assert all(d["selected_backend"] in ("LOCAL_CPU", "CONFIG_ONLY") for d in out["compute_decisions"])
