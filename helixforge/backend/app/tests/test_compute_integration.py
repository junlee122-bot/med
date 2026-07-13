"""Phase 8 integration tests: compute evaluation summary, release-readiness compute
categories (CPU-only never blocked by missing GPU), and export-safe compute submission
artifacts. No GPU/network/key."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import utcnow
from app.services import compute_evaluation, compute_reports
from app.storage import db

client = TestClient(app)


def _seed_run(project_id: str | None = None, run_id: str | None = None) -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:10]
    project_id = project_id or f"compute-project-{suffix}"
    run_id = run_id or f"compute-run-{suffix}"
    db.insert("workflow_runs", {
        "id": run_id, "project_id": project_id, "kind": "agentic",
        "status": "COMPLETED", "created_at": utcnow(),
    })
    return project_id, run_id


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


@pytest.mark.integration
def test_compute_summary_is_run_scoped_and_rejects_unknown_runs():
    project_a, run_a = _seed_run()
    project_b, run_b = _seed_run(project_id=project_a)
    for index, (project_id, run_id) in enumerate(((project_a, run_a), (project_b, run_b)), start=1):
        db.insert("cpu_models", {
            "id": f"model-{run_id}", "project_id": project_id, "run_id": run_id,
            "validation_status": "VALIDATED_BASELINE", "duplicate_leakage_count": index - 1,
            "sample_size_warning": None, "checksum": f"checksum-{index}", "seed": index,
            "created_at": utcnow(),
        })
        db.insert("dataset_versions", {
            "id": f"dataset-{run_id}", "project_id": project_id, "run_id": run_id,
            "created_at": utcnow(),
        })
        db.insert("optimization_loop_runs", {
            "id": f"optimization-{run_id}", "project_id": project_id, "run_id": run_id,
            "created_at": utcnow(),
        })
    db.insert("cpu_models", {
        "id": f"model-wrong-project-{run_a}", "project_id": "wrong-project",
        "run_id": run_a, "validation_status": "VALIDATED_BASELINE",
        "duplicate_leakage_count": 1, "created_at": utcnow(),
    })

    first = compute_evaluation.compute_summary(run_a)
    second = compute_evaluation.compute_summary(run_b)
    assert first["project_id"] == project_a
    assert second["project_id"] == project_b
    assert first["cpu_model_quality"]["model_count"] == 1
    assert second["cpu_model_quality"]["model_count"] == 1
    assert first["cpu_model_quality"]["leakage_flagged"] == 0
    assert second["cpu_model_quality"]["leakage_flagged"] == 1
    assert first["reproducibility"]["dataset_versions"] == 1
    assert second["reproducibility"]["dataset_versions"] == 1
    assert first["optimization"]["run_count"] == 1
    assert second["optimization"]["run_count"] == 1
    assert {row["id"] for row in client.get(
        "/api/datasets", params={"run_id": run_a},
    ).json()["datasets"]} == {f"dataset-{run_a}"}
    assert {row["id"] for row in client.get(
        "/api/cpu-models", params={"run_id": run_a},
    ).json()["models"]} == {f"model-{run_a}"}

    missing = f"missing-{uuid.uuid4().hex}"
    assert client.get(f"/api/evaluation/compute-summary/{missing}").status_code == 404
    assert client.get("/api/release-readiness/compute", params={"run_id": missing}).status_code == 404
    assert client.get("/api/datasets", params={"run_id": missing}).status_code == 404
    assert client.post("/api/cpu-models/train", json={
        "dataset": [], "run_id": missing,
    }).status_code == 404


# ---- Release readiness compute categories ----
@pytest.mark.unit
def test_release_categories_gpu_never_blocks_cpu_submission():
    rc = compute_evaluation.release_categories(None)
    gpu = next(c for c in rc["categories"] if c["key"] == "GPU")
    assert gpu["blocks_submission"] is False
    assert gpu["status"] in ("CONFIGURED_NOT_RUN", "PARTIAL")
    # A GPU-less environment must never be the reason a release is NOT_READY;
    # other missing CPU dependencies may still block it on a minimal CI host.
    assert not gpu["blocking_issues"]
    if rc["status"] == "NOT_READY":
        assert any(c["key"] != "GPU" and c["blocking_issues"] for c in rc["categories"])


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
    assert all_r.status_code == 200
    assert len(all_r.json()["artifacts"]) == len(compute_reports.ARTIFACT_TYPES)


@pytest.mark.integration
def test_compute_artifact_routes_and_run_ownership():
    project_id, run_id = _seed_run()
    types = client.get("/api/compute/artifacts/types")
    assert types.status_code == 200
    assert types.json()["types"] == compute_reports.ARTIFACT_TYPES

    generated = client.post("/api/compute/artifacts/generate", json={
        "kind": "compute_security_appendix", "run_id": run_id,
    })
    assert generated.status_code == 200
    artifact = generated.json()
    assert artifact["project_id"] == project_id
    assert artifact["run_id"] == run_id
    assert artifact["workflow_run_id"] == run_id
    assert db.list_records(
        "submission_artifacts", project_id=project_id, workflow_run_id=run_id,
    )[0]["id"] == artifact["id"]

    missing = f"missing-{uuid.uuid4().hex}"
    assert client.post("/api/compute/artifacts/generate", json={
        "kind": "compute_security_appendix", "run_id": missing,
    }).status_code == 404
    assert client.post("/api/compute/artifacts/generate", json={
        "kind": "all", "run_id": missing,
    }).status_code == 404


# ---- Compute-planner agent (Section 25) ----
@pytest.mark.integration
def test_compute_planner_agent_records_decisions_observable_only():
    project_id, run_id = _seed_run()
    r = client.post("/api/compute/plan-agent", json={"workflow_run_id": run_id})
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
    assert all(decision["project_id"] == project_id for decision in body["compute_decisions"])
    assert client.post("/api/compute/plan-agent", json={
        "workflow_run_id": run_id, "project_id": "different-project",
    }).status_code == 404
    assert client.post("/api/compute/plan-agent", json={
        "workflow_run_id": f"missing-{uuid.uuid4().hex}",
    }).status_code == 404


@pytest.mark.unit
def test_compute_planner_agent_no_gpu_uses_cpu_substitute(monkeypatch: pytest.MonkeyPatch):
    from app.agents.base import AgentContext
    from app.agents.compute_planner_agent import ComputePlannerAgent
    from app.compute import capability_detector
    project_id, run_id = _seed_run()
    monkeypatch.setattr(capability_detector, "detect", lambda _mode: {
        "profile": "CPU_ONLY", "recorded_gpu_artifacts": {"job_types": []},
    })
    ctx = AgentContext(project_id=project_id, workflow_run_id=run_id)
    out = ComputePlannerAgent().run(ctx)
    assert out.source_types == ["HEURISTIC_ANALYSIS"]
    assert all(d["selected_backend"] in ("LOCAL_CPU", "CONFIG_ONLY") for d in ctx.shared["compute_decisions"])


# ---- Hybrid pipeline records compute decisions ----
@pytest.mark.integration
def test_hybrid_pipeline_records_compute_decisions(monkeypatch: pytest.MonkeyPatch):
    from app.compute import capability_detector
    from app.services import compute_aware_planner, hybrid_pipeline
    monkeypatch.setattr(capability_detector, "detect", lambda _mode: {
        "profile": "CPU_ONLY", "recorded_gpu_artifacts": {"job_types": []},
    })
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
