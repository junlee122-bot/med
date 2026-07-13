"""Phase 8 Priority-3 tests: GPU worker contracts (configured-not-run), CPU
scientific demo, GPU dry-run (no submission), and compute record/replay. No GPU,
no network, no key, no paid job."""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.compute import gpu_worker_contracts
from app.main import app
from app.services import compute_snapshot, cpu_demo
from app.storage import db

client = TestClient(app)


@pytest.mark.integration
def test_compute_snapshot_cost_summary_is_snapshot_scoped():
    suffix = uuid.uuid4().hex[:10]
    run_id, project_id = f"cost-run-{suffix}", f"cost-project-{suffix}"
    job_id, other_job_id = f"cost-job-{suffix}", f"other-job-{suffix}"
    db.insert("workflow_runs", {
        "id": run_id, "project_id": project_id, "created_at": "2026-01-01T00:00:00Z",
    })
    db.insert("compute_jobs", {
        "id": job_id, "project_id": project_id, "workflow_run_id": run_id,
        "created_at": "2026-01-01T00:00:00Z",
    })
    db.insert("compute_cost_events", {
        "id": f"cost-event-{suffix}", "compute_job_id": job_id,
        "event_type": "actual_cost", "estimated_cost_usd": 1.5,
        "actual_cost_usd": 1.25, "created_at": "2026-01-01T00:00:00Z",
    })
    snap = compute_snapshot.create_from_run(run_id)
    db.insert("compute_cost_events", {
        "id": f"other-cost-event-{suffix}", "compute_job_id": other_job_id,
        "event_type": "actual_cost", "estimated_cost_usd": 999,
        "actual_cost_usd": 999, "created_at": "2026-01-01T00:00:00Z",
    })

    summary = compute_snapshot.cost_summary(snap["id"])
    assert summary["event_count"] == 1
    assert summary["estimated_total_usd"] == 1.5
    assert summary["actual_total_usd"] == 1.25


# ---- GPU worker contracts ----
@pytest.mark.unit
def test_all_worker_contracts_configured_not_run():
    lc = gpu_worker_contracts.list_contracts()
    assert lc["count"] >= 8
    assert all(c["status"] == "GPU_CONFIGURED_NOT_RUN" for c in lc["contracts"])
    assert all(c["cpu_substitute"] for c in lc["contracts"])


@pytest.mark.unit
def test_worker_output_rejects_docking_without_protocol():
    r = gpu_worker_contracts.validate_worker_output("GNINA_SCREEN", ["predictions", "logs"], has_protocol=False)
    assert r["accepted"] is False
    assert any("protocol" in x for x in r["reasons"])


@pytest.mark.unit
def test_worker_output_rejects_metrics_without_split():
    r = gpu_worker_contracts.validate_worker_output("CHEMPROP_TRAIN",
                                                    ["model_checkpoint", "metrics", "predictions",
                                                     "applicability", "logs"], has_split=False)
    assert r["accepted"] is False


@pytest.mark.unit
def test_worker_spec_build_uses_allowlist():
    v = gpu_worker_contracts.build_job_spec("CHEMPROP_TRAIN", input_artifact_ids=["a"], dataset_version_id="d")
    assert v["valid"] is True


@pytest.mark.integration
def test_worker_contracts_endpoint():
    r = client.get("/api/compute/worker-contracts")
    assert r.status_code == 200
    assert r.json()["source_type"] == "GPU_CONFIGURED_NOT_RUN"


# ---- CPU scientific demo ----
@pytest.mark.integration
def test_cpu_scientific_demo_completes_without_gpu_or_key():
    r = client.post("/api/demo/run-cpu-scientific-demo", json={"target": "EGFR"})
    assert r.status_code == 200
    body = r.json()
    assert body["gpu_used"] is False
    assert body["llm_key_required"] is False
    assert body["gpu_escalation"]["submitted"] is False
    # honest labels, no fabricated GPU result
    assert body["source_type"] == "COMPUTE_FALLBACK_OUTPUT"
    assert "not binding proof" in " ".join(body["limitations"]).lower()


@pytest.mark.integration
def test_cpu_demo_report_has_no_fabricated_gpu_result():
    body = client.post("/api/demo/run-cpu-scientific-demo", json={"target": "EGFR"}).json()
    md = body["report_markdown"].lower()
    assert "gpu present locally" in md and "false" in md
    assert "nothing submitted" in md or "no provider call" in md or "dry run" in md


# ---- GPU dry run ----
@pytest.mark.integration
def test_gpu_readiness_dry_run_makes_no_submission():
    r = client.post("/api/demo/run-gpu-readiness-dry-run", json={"target": "EGFR"})
    body = r.json()
    assert body["provider_submissions"] == 0
    assert body["submitted"] is False
    assert body["approval_status"] == "PENDING"
    assert all(s["submitted"] is False for s in body["job_specs"])
    assert body["safety_readiness"]["arbitrary_command_absent"] is True


# ---- Compute record/replay ----
@pytest.mark.integration
def test_compute_snapshot_replay_no_provider_call_and_no_secrets():
    # seed a run with a compute decision
    from app.services import compute_aware_planner
    from app.compute import capability_detector
    db.insert("workflow_runs", {
        "id": "csnap-run", "project_id": "csnap-project",
        "created_at": "2026-01-01T00:00:00Z",
    })
    caps = capability_detector.detect("local")
    compute_aware_planner.plan_compute(caps, workflow_run_id="csnap-run")
    snap = compute_snapshot.create_from_run("csnap-run")
    assert "credentials" in snap["excludes"]
    rep = compute_snapshot.replay(snap["id"])
    assert rep["provider_call_made"] is False
    assert rep["cost_usd"] == 0.0
    man = compute_snapshot.manifest(snap["id"])
    assert man["contains_credentials"] is False


@pytest.mark.integration
def test_compute_snapshot_endpoints():
    from app.services import compute_aware_planner
    from app.compute import capability_detector
    db.insert("workflow_runs", {
        "id": "csnap-ep", "project_id": "csnap-project",
        "created_at": "2026-01-01T00:00:00Z",
    })
    compute_aware_planner.plan_compute(capability_detector.detect("local"), workflow_run_id="csnap-ep")
    snap = client.post("/api/snapshots/create-compute-from-run/csnap-ep").json()
    rep = client.post(f"/api/snapshots/{snap['id']}/replay-compute").json()
    assert rep["provider_call_made"] is False
    man = client.get(f"/api/snapshots/{snap['id']}/compute-manifest").json()
    assert man["decision_count"] >= 1
