"""Provider-neutral compute providers.

RemoteComputeProvider is the interface every backend implements. Implementations:
- LocalCPUProvider    — runs CPU jobs in-process (no network).
- RecordedArtifactProvider — replays captured artifacts (no network, zero cost).
- GenericRESTGPUProvider   — talks to a generic REST GPU control plane. DISABLED by
  default; makes NO paid/network call unless remote is enabled AND the live-test env
  flag is set. Health check is local-only unless live=True is explicitly requested.
- FakeRemoteGPUProvider    — deterministic fake for tests (success/timeout/budget/
  safety/malformed/checksum/500/cancel/partial). Never touches the network.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Any

from app.compute.config import get_compute_config
from app.compute.schemas import ExecutionBackend
from app.models.schemas import utcnow


class RemoteComputeProvider:
    provider_type = "base"
    display_name = "Base Provider"

    def health_check(self, live: bool = False) -> dict[str, Any]:
        raise NotImplementedError

    def estimate_cost(self, job_spec: dict[str, Any]) -> dict[str, Any]:
        from app.compute.cost_guard import estimate_gpu_job_cost
        return estimate_gpu_job_cost(job_spec)

    def submit(self, job_spec: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def get_status(self, remote_job_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def cancel(self, remote_job_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def list_artifacts(self, remote_job_id: str) -> list[dict[str, Any]]:
        raise NotImplementedError

    def download_artifact(self, remote_job_id: str, artifact_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def validate_webhook(self, payload: bytes, signature: str) -> bool:
        return False

    def normalize_error(self, error: Any) -> dict[str, Any]:
        return {"error": str(error)[:300], "provider": self.provider_type}


class LocalCPUProvider(RemoteComputeProvider):
    provider_type = "local_cpu"
    display_name = "Local CPU"

    def health_check(self, live: bool = False) -> dict[str, Any]:
        import os
        return {"healthy": True, "backend": ExecutionBackend.LOCAL_CPU,
                "logical_cores": os.cpu_count() or 1, "detail": "Local CPU always available.",
                "network_used": False, "checked_at": utcnow()}

    def submit(self, job_spec: dict[str, Any]) -> dict[str, Any]:
        # Local CPU jobs are executed by local_cpu_worker, not "submitted" remotely.
        return {"accepted": True, "backend": ExecutionBackend.LOCAL_CPU,
                "note": "Local CPU jobs run via the local worker, not a remote submission."}


class RecordedArtifactProvider(RemoteComputeProvider):
    provider_type = "recorded"
    display_name = "Recorded Artifacts (replay)"

    def health_check(self, live: bool = False) -> dict[str, Any]:
        from app.storage import db
        n = len([a for a in db.list_records("compute_artifacts", limit=500)
                 if a.get("source_type") == "RECORDED_GPU_OUTPUT"])
        return {"healthy": True, "backend": ExecutionBackend.RECORDED_ARTIFACT,
                "recorded_artifact_count": n, "detail": "Replay only; no live cost.",
                "network_used": False, "checked_at": utcnow()}

    def estimate_cost(self, job_spec: dict[str, Any]) -> dict[str, Any]:
        return {"estimated_cost_usd": 0.0, "approximate": False,
                "note": "Recorded replay has zero live cost.", "estimated_at": utcnow()}


class GenericRESTGPUProvider(RemoteComputeProvider):
    """Generic REST control-plane client. Contract:
    POST /v1/jobs · GET /v1/jobs/{id} · POST /v1/jobs/{id}/cancel · GET /v1/jobs/{id}/artifacts.
    Disabled by default; never makes a paid/network call in tests."""
    provider_type = "generic_rest"
    display_name = "Generic REST GPU"

    def __init__(self) -> None:
        self.cfg = get_compute_config()

    def _live_allowed(self) -> tuple[bool, str]:
        if not self.cfg.remote_gpu_enabled:
            return False, "remote GPU disabled (HELIXFORGE_REMOTE_GPU_ENABLED=false)."
        if not self.cfg.remote_configured():
            return False, "provider endpoint/token not configured."
        if not self.cfg.enable_live_gpu_test:
            return False, "live GPU calls gated (HELIXFORGE_ENABLE_LIVE_GPU_TEST=false)."
        return True, "live allowed"

    def health_check(self, live: bool = False) -> dict[str, Any]:
        configured = self.cfg.remote_configured()
        base = {"backend": ExecutionBackend.REMOTE_GPU, "configured": configured,
                "enabled": self.cfg.remote_gpu_enabled, "network_used": False, "checked_at": utcnow()}
        if not live:
            base.update({"healthy": None, "detail": "Local readiness only; live probe not requested."})
            return base
        allowed, reason = self._live_allowed()
        if not allowed:
            base.update({"healthy": None, "detail": reason})
            return base
        # A real live probe would GET {endpoint}/v1/health with a timeout here.
        # We do NOT make network calls in this implementation session.
        base.update({"healthy": None, "network_used": False,
                     "detail": "Live probe path present but not executed in this session."})
        return base

    def submit(self, job_spec: dict[str, Any]) -> dict[str, Any]:
        allowed, reason = self._live_allowed()
        if not allowed:
            return {"accepted": False, "reason": reason, "backend": ExecutionBackend.CONFIG_ONLY}
        # Live submission path intentionally not executed in this session.
        return {"accepted": False, "reason": "Live submission disabled in this build session.",
                "backend": ExecutionBackend.CONFIG_ONLY}

    def get_status(self, remote_job_id: str) -> dict[str, Any]:
        return {"remote_job_id": remote_job_id, "status": "UNKNOWN",
                "detail": "Live status polling not executed in this session."}

    def cancel(self, remote_job_id: str) -> dict[str, Any]:
        return {"remote_job_id": remote_job_id, "cancelled": False,
                "detail": "Live cancel not executed in this session."}

    def list_artifacts(self, remote_job_id: str) -> list[dict[str, Any]]:
        return []

    def validate_webhook(self, payload: bytes, signature: str) -> bool:
        secret = self.cfg.remote_gpu_webhook_secret
        if not secret or not signature:
            return False
        expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)


class FakeRemoteGPUProvider(RemoteComputeProvider):
    """Deterministic fake for tests. Scenario chosen via constructor; no network."""
    provider_type = "fake"
    display_name = "Fake Remote GPU (test)"
    SCENARIOS = {"success", "delayed_success", "timeout", "budget_block", "safety_block",
                 "malformed_artifact", "checksum_mismatch", "provider_500", "cancellation",
                 "partial_artifacts"}

    def __init__(self, scenario: str = "success", webhook_secret: str = "test-secret") -> None:
        self.scenario = scenario if scenario in self.SCENARIOS else "success"
        self.webhook_secret = webhook_secret

    def health_check(self, live: bool = False) -> dict[str, Any]:
        healthy = self.scenario != "provider_500"
        return {"healthy": healthy, "backend": ExecutionBackend.REMOTE_GPU, "network_used": False,
                "detail": f"fake scenario={self.scenario}", "checked_at": utcnow()}

    def estimate_cost(self, job_spec: dict[str, Any]) -> dict[str, Any]:
        from app.compute.cost_guard import estimate_gpu_job_cost
        return estimate_gpu_job_cost(job_spec)

    def submit(self, job_spec: dict[str, Any]) -> dict[str, Any]:
        if self.scenario == "budget_block":
            return {"accepted": False, "reason": "budget", "status": "BUDGET_BLOCKED"}
        if self.scenario == "safety_block":
            return {"accepted": False, "reason": "safety", "status": "SAFETY_BLOCKED"}
        if self.scenario == "provider_500":
            return {"accepted": False, "reason": "provider 500", "status": "TOOL_ERROR"}
        return {"accepted": True, "remote_job_id": f"fake-{self.scenario}-001", "status": "QUEUED"}

    def get_status(self, remote_job_id: str) -> dict[str, Any]:
        mapping = {"success": "SUCCEEDED", "delayed_success": "RUNNING", "timeout": "TIMED_OUT",
                   "cancellation": "CANCELLED", "partial_artifacts": "SUCCEEDED_WITH_WARNINGS",
                   "malformed_artifact": "SUCCEEDED", "checksum_mismatch": "SUCCEEDED",
                   "provider_500": "TOOL_ERROR"}
        return {"remote_job_id": remote_job_id, "status": mapping.get(self.scenario, "SUCCEEDED")}

    def cancel(self, remote_job_id: str) -> dict[str, Any]:
        return {"remote_job_id": remote_job_id, "cancelled": True, "status": "CANCELLED"}

    def list_artifacts(self, remote_job_id: str) -> list[dict[str, Any]]:
        good = {"artifact_id": "a1", "artifact_type": "metrics", "filename": "metrics.json",
                "media_type": "application/json", "size_bytes": 128,
                "checksum_sha256": "a" * 64, "content": {"rmse": 0.5}}
        if self.scenario == "malformed_artifact":
            return [{"artifact_id": "a1", "artifact_type": "metrics", "filename": "../evil.json",
                     "media_type": "application/json", "size_bytes": 128, "checksum_sha256": "a" * 64}]
        if self.scenario == "checksum_mismatch":
            return [{**good, "checksum_sha256": "b" * 64, "declared_checksum": "a" * 64}]
        if self.scenario == "partial_artifacts":
            return [good]  # missing some required outputs
        if self.scenario in ("timeout", "budget_block", "safety_block", "provider_500", "cancellation"):
            return []
        return [good, {"artifact_id": "a2", "artifact_type": "logs", "filename": "run.log",
                       "media_type": "text/plain", "size_bytes": 64, "checksum_sha256": "c" * 64}]

    def download_artifact(self, remote_job_id: str, artifact_id: str) -> dict[str, Any]:
        for a in self.list_artifacts(remote_job_id):
            if a["artifact_id"] == artifact_id:
                return a
        return {"error": "not found"}

    def validate_webhook(self, payload: bytes, signature: str) -> bool:
        expected = hmac.new(self.webhook_secret.encode(), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature or "")
