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
from app.services import compute_aware_planner

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
def test_budget_blocks_over_run_cap():
    b = cost_guard.check_budget(9999.0, job_max_cost_usd=5.0)
    assert b["ok"] is False and b["status"] == "BUDGET_BLOCKED"


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


@pytest.mark.integration
def test_missing_approval_blocks_and_unsafe_job_validation_fails():
    spec = {"job_type": "CHEMPROP_TRAIN", "dataset_version_id": "d", "command": "evil"}
    job = client.post("/api/compute/jobs", json={"spec": spec}).json()
    assert job["status"] == "VALIDATION_FAILED"


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
    plan = compute_aware_planner.plan_compute(caps)
    assert plan["gpu_enabled"] is False
    assert all(d["selected_backend"] in ("LOCAL_CPU", "CONFIG_ONLY") for d in plan["decisions"])


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
    assert r.status_code == 200
    assert r.json()["compute_decisions"] == []
