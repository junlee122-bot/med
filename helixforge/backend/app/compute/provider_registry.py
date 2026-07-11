"""Select the active compute provider from configuration. Defaults to a safe,
network-free provider. Never returns a live provider unless explicitly configured."""
from __future__ import annotations

from typing import Any

from app.compute.config import get_compute_config
from app.compute.providers import (
    GenericRESTGPUProvider, LocalCPUProvider, RecordedArtifactProvider, RemoteComputeProvider,
)
from app.models.schemas import utcnow


def get_provider(provider_type: str | None = None) -> RemoteComputeProvider:
    cfg = get_compute_config()
    ptype = provider_type or (cfg.remote_gpu_provider if cfg.remote_configured() else "local_cpu")
    if ptype == "generic_rest":
        return GenericRESTGPUProvider()
    if ptype == "recorded":
        return RecordedArtifactProvider()
    return LocalCPUProvider()


def list_providers() -> dict[str, Any]:
    cfg = get_compute_config()
    providers = [
        {"id": "local_cpu", "provider_type": "local_cpu", "display_name": "Local CPU",
         "configured": True, "enabled": True, "credential_status": "n/a",
         "allowed_job_types": "CPU_*", "network": False},
        {"id": "recorded", "provider_type": "recorded", "display_name": "Recorded Artifacts",
         "configured": True, "enabled": True, "credential_status": "n/a",
         "allowed_job_types": "replay", "network": False},
        {"id": "generic_rest", "provider_type": "generic_rest", "display_name": "Generic REST GPU",
         "configured": cfg.remote_configured(), "enabled": cfg.remote_gpu_enabled,
         "credential_status": "set" if cfg.remote_gpu_api_token else "not set",
         "allowed_job_types": "GPU_*", "network": cfg.remote_gpu_enabled,
         "endpoint_set": bool(cfg.remote_gpu_endpoint)},
    ]
    return {"providers": providers, "active": get_provider().provider_type,
            "live_gpu_calls_enabled": cfg.enable_live_gpu_test and cfg.remote_gpu_enabled,
            "note": "No arbitrary commands: GPU jobs are allowlisted specs only.",
            "checked_at": utcnow()}
