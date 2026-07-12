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
