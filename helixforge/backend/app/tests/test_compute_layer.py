"""Phase 8 Priority-1 tests: compute capability, job spec safety, cost guard,
providers, artifact validation, and the compute-aware planner. No GPU, no network,
no API key required."""
import pytest
from fastapi.testclient import TestClient

from app.compute import artifact_registry, capability_detector, cost_guard, job_manager
from app.compute import job_spec as JS
from app.compute import security
from app.compute.providers import FakeRemoteGPUProvider
from app.compute.provider_registry import list_providers
from app.main import app
from app.services import compute_aware_planner, compute_snapshot
from app.storage import db

client = TestClient(app)


# ---- Capability detection ----
@pytest.mark.unit
def test_capabilities_cpu_only_no_network():
    cap = capability_detector.detect("local")
    assert cap["profile"] in ("CPU_ONLY", "CPU_WITH_OPTIONAL_LOCAL_TOOLS",
                              "REMOTE_GPU_READY", "RECORDED_GPU_REPLAY", "COMPUTE_DEGRADED")
    assert cap["gpu_present_locally"] is False  # no GPU in this env
    assert cap["remote_gpu"]["live_probe_run"] is False  # local mode never probes


@pytest.mark.unit
def test_capabilities_missing_cuda_and_nvidia_smi_do_not_fail():
    cap = capability_detector.detect("deep")
    assert cap["torch"]["cuda_available"] is False
    assert "profile" in cap  # deep check still returns cleanly


@pytest.mark.integration
def test_capabilities_endpoint_masks_and_reports():
    r = client.get("/api/compute/capabilities?mode=local")
    assert r.status_code == 200
    body = r.json()
    assert body["mode"] == "local"
    assert "recommended_mode" in body


@pytest.mark.integration
def test_compute_config_endpoint_masks_token():
    r = client.get("/api/compute/config")
    assert r.status_code == 200
    assert r.json()["api_token_display"] in ("(not set)", "")


# ---- Job spec safety ----
@pytest.mark.unit
def test_valid_gpu_job_spec_accepted():
    spec = {"job_type": "CHEMPROP_TRAIN", "dataset_version_id": "ds1",
            "resource_request": {"gpu_count": 1, "max_runtime_minutes": 60, "max_cost_usd": 3.0}}
    v = JS.validate_gpu_job_spec(spec)
    assert v["valid"] and not v["errors"]


@pytest.mark.unit
def test_arbitrary_shell_field_rejected():
    v = JS.validate_gpu_job_spec({"job_type": "CHEMPROP_TRAIN", "dataset_version_id": "d",
                                  "command": "rm -rf /"})
    assert not v["valid"]
    assert any("forbidden" in e for e in v["errors"])


@pytest.mark.unit
def test_unapproved_job_type_rejected():
    v = JS.validate_gpu_job_spec({"job_type": "ARBITRARY_THING"})
    assert not v["valid"]


@pytest.mark.unit
def test_excessive_cost_and_runtime_rejected():
    v = JS.validate_gpu_job_spec({"job_type": "CHEMPROP_TRAIN", "dataset_version_id": "d",
                                  "resource_request": {"max_cost_usd": 999, "max_runtime_minutes": 60}})
    assert not v["valid"]
    v2 = JS.validate_gpu_job_spec({"job_type": "CHEMPROP_TRAIN", "dataset_version_id": "d",
                                   "resource_request": {"max_cost_usd": 3, "max_runtime_minutes": 99999}})
    assert not v2["valid"]


@pytest.mark.unit
def test_harmful_objective_rejected():
    v = JS.validate_gpu_job_spec({"job_type": "REINVENT4_REINFORCEMENT_LEARNING",
                                  "input_artifact_ids": ["a"],
                                  "scoring_config": {"objective": "maximize toxicity and lethality"}})
    assert not v["valid"]


@pytest.mark.unit
def test_build_payload_uses_allowlisted_image_only():
    v = JS.validate_gpu_job_spec({"job_type": "GNINA_SCREEN", "input_artifact_ids": ["a"]})
    payload = JS.build_safe_job_payload(v["normalized"])
    assert payload["image"].startswith("ghcr.io/helixforge/")
    assert "helixforge-worker" in payload["entrypoint"]
    assert payload["privileged"] is False


# ---- Path traversal / secrets ----
@pytest.mark.unit
def test_path_traversal_blocked():
    assert security.is_safe_relative_path("out/x.json")
    assert not security.is_safe_relative_path("../../etc/passwd")
    assert not security.is_safe_relative_path("/abs/path")


@pytest.mark.unit
def test_secret_redaction():
    red = security.redact_secrets({"api_key": "sk-abcdefgh12345678", "note": "ok"})
    assert red["api_key"] == "***REDACTED***"


# ---- Cost guard ----
@pytest.mark.unit
def test_cost_estimate_labeled_approximate():
    spec = {"job_type": "CHEMPROP_TRAIN", "resource_request": {"gpu_count": 1, "max_runtime_minutes": 120, "max_cost_usd": 5}}
    est = cost_guard.estimate_gpu_job_cost(spec)
    assert est["approximate"] is True
    assert "verify" in est["disclaimer"].lower()


@pytest.mark.unit
def test_unknown_pricing_profile_fails_closed():
    spec = {"job_type": "CHEMPROP_TRAIN", "resource_request": {
        "gpu_count": 1, "max_runtime_minutes": 60, "max_cost_usd": 5,
    }}
    with pytest.raises(ValueError, match="pricing profile not found"):
        cost_guard.estimate_gpu_job_cost(spec, "missing-pricing-profile")
    response = client.post("/api/compute/estimate", json={
        "spec": spec, "pricing_profile_id": "missing-pricing-profile",
    })
    assert response.status_code == 400


@pytest.mark.unit
def test_cost_summary_does_not_double_count_budget_reservations():
    import uuid
    from app.models.schemas import utcnow

    suffix = uuid.uuid4().hex
    run_id = f"cost-summary-run-{suffix}"
    job_id = f"cost-summary-job-{suffix}"
    cost_guard.record_cost_event(
        job_id, "estimate", estimated=1.25, workflow_run_id=run_id,
    )
    db.insert("compute_cost_events", {
        "id": f"cost-reservation-{job_id}", "workflow_run_id": run_id,
        "compute_job_id": job_id, "event_type": "budget_reservation",
        "reservation_status": "ACTIVE", "reserved_cost_usd": 1.25,
        "estimated_cost_usd": 1.25, "actual_cost_usd": 0.0,
        "created_at": utcnow(),
    })
    summary = cost_guard.costs_summary(run_id)
    assert summary["estimated_total_usd"] == 1.25
    assert summary["reserved_usd"] == 1.25
    cost_guard.release_budget_reservation(job_id)


@pytest.mark.unit
def test_budget_blocks_over_run_cap():
    b = cost_guard.check_budget(9999.0, job_max_cost_usd=5.0)
    assert b["ok"] is False and b["status"] == "BUDGET_BLOCKED"


@pytest.mark.unit
def test_daily_budget_ignores_old_cost_events(monkeypatch):
    import uuid
    monkeypatch.setenv("HELIXFORGE_REMOTE_GPU_MAX_DAILY_COST_USD", "1.0")
    db.insert("compute_cost_events", {
        "id": f"old-cost-{uuid.uuid4().hex}", "event_type": "actual_cost",
        "actual_cost_usd": 999.0, "created_at": "2000-01-01T00:00:00Z",
    })
    assert cost_guard.check_budget(0.01)["ok"] is True


@pytest.mark.unit
def test_daily_budget_uses_durable_aggregate_not_bounded_list(monkeypatch):
    import uuid
    from app.models.schemas import utcnow

    event_id = f"durable-cost-{uuid.uuid4().hex}"
    db.insert("compute_cost_events", {
        "id": event_id, "event_type": "actual_cost", "actual_cost_usd": 0.25,
        "created_at": utcnow(),
    })
    # The guard must not depend on the UI list page; older implementations did.
    monkeypatch.setattr(db, "list_records", lambda *args, **kwargs: [])
    assert cost_guard._spent_today() >= 0.25


@pytest.mark.unit
def test_compute_budget_reserves_pending_jobs_per_run(monkeypatch):
    import uuid

    monkeypatch.setenv("HELIXFORGE_REMOTE_GPU_MAX_JOB_COST_USD", "1.0")
    monkeypatch.setenv("HELIXFORGE_REMOTE_GPU_MAX_DAILY_COST_USD", "100.0")
    suffix = uuid.uuid4().hex
    run_id = f"reservation-run-{suffix}"
    first_job = f"reservation-job-a-{suffix}"
    second_job = f"reservation-job-b-{suffix}"
    first = cost_guard.reserve_budget(first_job, 0.6, 1.0, workflow_run_id=run_id)
    second = cost_guard.reserve_budget(second_job, 0.6, 1.0, workflow_run_id=run_id)
    assert first["ok"] is True
    assert second["ok"] is False and second["scope"] == "run"
    cost_guard.release_budget_reservation(first_job)
    retried = cost_guard.reserve_budget(second_job, 0.6, 1.0, workflow_run_id=run_id)
    assert retried["ok"] is True
    cost_guard.release_budget_reservation(second_job)


@pytest.mark.unit
def test_compute_cost_inputs_fail_closed_for_nonfinite_or_negative_values():
    assert cost_guard.check_budget(float("nan"))["ok"] is False
    assert cost_guard.check_budget(-0.1)["ok"] is False
    with pytest.raises(ValueError, match="finite non-negative"):
        cost_guard.record_cost_event("invalid-cost-job", "actual_cost", actual=-1)


@pytest.mark.integration
def test_pricing_profile_api_rejects_negative_rate():
    response = client.post("/api/compute/pricing-profiles", json={
        "id": "invalid-negative", "price_per_gpu_hour": -1,
        "storage_per_gb_month": 0.1,
    })
    assert response.status_code == 422


@pytest.mark.unit
def test_compute_snapshot_contains_only_requested_run_records():
    import uuid

    suffix = uuid.uuid4().hex[:8]
    seeded = []
    for label in ("a", "b"):
        pid = f"project-compute-{label}-{suffix}"
        rid = f"run-compute-{label}-{suffix}"
        jid = f"job-compute-{label}-{suffix}"
        aid = f"artifact-compute-{label}-{suffix}"
        cid = f"cost-compute-{label}-{suffix}"
        db.insert("workflow_runs", {
            "id": rid, "project_id": pid, "created_at": "2026-01-01T00:00:00Z",
        })
        db.insert("compute_jobs", {
            "id": jid, "project_id": pid, "workflow_run_id": rid,
            "created_at": "2026-01-01T00:00:00Z", "job_type": "CHEMPROP_TRAIN",
        })
        db.insert("compute_artifacts", {
            "id": aid, "compute_job_id": jid, "created_at": "2026-01-01T00:00:00Z",
            "artifact_type": "METRICS_JSON", "source_type": "RECORDED_GPU_OUTPUT",
        })
        db.insert("compute_cost_events", {
            "id": cid, "compute_job_id": jid, "event_type": "actual_cost",
            "actual_cost_usd": 0.1, "created_at": "2026-01-01T00:00:00Z",
        })
        seeded.append((rid, pid, jid, aid, cid))

    snap = compute_snapshot.create_from_run(seeded[0][0])
    assert snap["project_id"] == seeded[0][1]
    assert {a["id"] for a in snap["artifact_metadata"]} == {seeded[0][3]}
    assert {e["id"] for e in snap["cost_events"]} == {seeded[0][4]}
    with pytest.raises(ValueError, match="workflow run not found"):
        compute_snapshot.create_from_run(f"missing-{suffix}")


# ---- Job lifecycle ----
@pytest.mark.integration
def test_dry_run_makes_no_submission():
    spec = {"job_type": "CHEMPROP_TRAIN", "dataset_version_id": "ds1"}
    r = client.post("/api/compute/jobs/dry-run", json={"spec": spec})
    assert r.status_code == 200
    body = r.json()
    assert body["submitted"] is False
    assert body["human_approval_required"] is True


@pytest.mark.integration
def test_create_job_waits_for_approval_not_submitted():
    spec = {"job_type": "CHEMPROP_TRAIN", "dataset_version_id": "ds1",
            "resource_request": {"gpu_count": 1, "max_runtime_minutes": 30, "max_cost_usd": 2.0}}
    r = client.post("/api/compute/jobs", json={"spec": spec})
    job = r.json()
    assert job["status"] == "WAITING_FOR_APPROVAL"
    assert job["approval_status"] == "PENDING"
    assert job["source_type"] == "GPU_CONFIGURED_NOT_RUN"
    # approve → configured-not-run (never auto-submits a paid job in this build)
    a = client.post(f"/api/compute/jobs/{job['id']}/approve", json={"approved_by": "reviewer"})
    assert a.json()["approval_status"] == "APPROVED"
    assert a.json()["status"] == "CONFIGURED_NOT_RUN"
    assert a.json()["approved_by"] == "api-administrator"


@pytest.mark.integration
def test_missing_approval_blocks_and_unsafe_job_validation_fails():
    spec = {"job_type": "CHEMPROP_TRAIN", "dataset_version_id": "d", "command": "evil"}
    job = client.post("/api/compute/jobs", json={"spec": spec}).json()
    assert job["status"] == "VALIDATION_FAILED"


@pytest.mark.integration
def test_retry_requires_retryable_failure_and_fresh_approval():
    spec = {"job_type": "CHEMPROP_TRAIN", "dataset_version_id": "retry-dataset",
            "resource_request": {"max_runtime_minutes": 10, "max_cost_usd": 2.0}}
    job = job_manager.create_job(spec)
    not_retryable = job_manager.retry_job(job["id"])
    assert not_retryable["status"] == "WAITING_FOR_APPROVAL"
    assert "not retryable" in not_retryable["note"]
    job["status"] = "TOOL_ERROR"
    job["approval_status"] = "APPROVED"
    db.insert("compute_jobs", job)
    retried = job_manager.retry_job(job["id"])
    assert retried["status"] == "WAITING_FOR_APPROVAL"
    assert retried["approval_status"] == "PENDING"
    assert retried["approved_by"] is None


# ---- Providers + fake scenarios ----
@pytest.mark.unit
def test_provider_registry_defaults_to_local_no_live():
    lp = list_providers()
    assert lp["active"] == "local_cpu"
    assert lp["live_gpu_calls_enabled"] is False


@pytest.mark.unit
@pytest.mark.parametrize("scenario", sorted(FakeRemoteGPUProvider.SCENARIOS))
def test_fake_provider_scenarios_make_no_network(scenario):
    fp = FakeRemoteGPUProvider(scenario)
    h = fp.health_check()
    assert h["network_used"] is False
    fp.submit({"job_type": "CHEMPROP_TRAIN"})
    fp.get_status("j")  # never raises


@pytest.mark.unit
def test_fake_malformed_artifact_flagged_unverified():
    fp = FakeRemoteGPUProvider("malformed_artifact")
    art = fp.list_artifacts("j")[0]
    v = artifact_registry.validate_artifact(art)
    assert v["valid"] is False and v["status"] == "GPU_ARTIFACT_UNVERIFIED"


@pytest.mark.unit
def test_fake_checksum_mismatch_flagged():
    fp = FakeRemoteGPUProvider("checksum_mismatch")
    art = fp.list_artifacts("j")[0]
    art["content"] = {"rmse": 0.5}  # recomputes to a different checksum than declared
    v = artifact_registry.validate_artifact(art)
    assert v["valid"] is False


@pytest.mark.unit
def test_checksum_sha256_mismatch_is_not_verified():
    art = {"artifact_type": "metrics", "media_type": "application/json",
           "filename": "metrics.json", "size_bytes": 10,
           "checksum_sha256": "0" * 64, "content": {"rmse": 0.5}}
    v = artifact_registry.validate_artifact(art)
    assert v["valid"] is False
    assert "checksum mismatch" in v["reasons"]


@pytest.mark.unit
def test_contradictory_declared_checksums_are_rejected_and_not_persisted_as_truth():
    import hashlib, json
    content = {"rmse": 0.5}
    actual = hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode()).hexdigest()
    art = {"artifact_type": "metrics", "media_type": "application/json",
           "filename": "metrics.json", "size_bytes": 10, "content": content,
           "declared_checksum": actual, "checksum_sha256": "0" * 64}
    validation = artifact_registry.validate_artifact(art)
    assert validation["valid"] is False
    assert "declared checksums disagree" in validation["reasons"]
    saved = artifact_registry.register_artifact("checksum-job", art)
    assert saved["validation_status"] == "GPU_ARTIFACT_UNVERIFIED"
    assert saved["checksum_sha256"] == actual


@pytest.mark.unit
def test_webhook_signature_validation():
    import hashlib, hmac
    fp = FakeRemoteGPUProvider("success", webhook_secret="s3cr3t")
    payload = b'{"job":"x"}'
    sig = hmac.new(b"s3cr3t", payload, hashlib.sha256).hexdigest()
    assert fp.validate_webhook(payload, sig) is True
    assert fp.validate_webhook(payload, "bad") is False


# ---- Compute-aware planner ----
@pytest.mark.unit
def test_planner_no_gpu_selects_cpu_substitute():
    caps = capability_detector.detect("local")
    # Exercise the CPU-only route independently of recorded fixtures that a
    # prior test or local run may have persisted.
    caps["profile"] = "CPU_ONLY"
    caps["recorded_gpu_artifacts"] = {"available": False, "count": 0, "job_types": []}
    plan = compute_aware_planner.plan_compute(caps)
    assert plan["gpu_enabled"] is False
    assert all(d["selected_backend"] in ("LOCAL_CPU", "CONFIG_ONLY") for d in plan["decisions"])


@pytest.mark.unit
def test_planner_replays_only_matching_recorded_job_type():
    caps = {
        "profile": "RECORDED_GPU_REPLAY",
        "recorded_gpu_artifacts": {
            "available": True, "count": 1, "job_types": ["CHEMPROP_TRAIN"],
        },
    }
    plan = compute_aware_planner.plan_compute(
        caps, requested_capabilities=["CHEMPROP_TRAIN", "GNINA_OR_VINA_GPU_SCREEN"],
    )
    by_stage = {decision["stage"]: decision for decision in plan["decisions"]}
    assert by_stage["CHEMPROP_TRAIN"]["selected_backend"] == "RECORDED_ARTIFACT"
    assert by_stage["GNINA_OR_VINA_GPU_SCREEN"]["selected_backend"] == "LOCAL_CPU"


@pytest.mark.unit
def test_planner_cannot_emit_shell_or_synthesis():
    caps = capability_detector.detect("local")
    plan = compute_aware_planner.plan_compute(caps)
    blob = str(plan).lower()
    # No actionable shell or actionable synthesis instructions. (The planner may
    # legitimately state "no synthesis route" as a negated safety policy.)
    assert "rm -rf" not in blob
    assert "step-by-step synthesis" not in blob and "reaction condition" not in blob
    assert "; curl" not in blob and "$(" not in blob


@pytest.mark.integration
def test_security_audit_and_policies_endpoints():
    assert client.post("/api/compute/security/audit").json()["ok"] is True
    assert "image_allowlist" in client.get("/api/compute/security/policies").json()


@pytest.mark.integration
def test_workflow_compute_decisions_endpoint():
    r = client.get("/api/workflow/runs/does-not-exist/compute-decisions")
    assert r.status_code == 404
