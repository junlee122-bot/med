"""Compute-layer configuration from environment. Everything is optional; defaults
keep the app CPU-only, provider-disabled, and safe. Read via get_compute_config()."""
from __future__ import annotations

import os
from typing import Any


def _b(name: str, default: bool) -> bool:
    v = os.getenv(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def _f(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _i(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _mask(secret: str) -> str:
    if not secret:
        return "(not set)"
    return "•" * max(0, len(secret) - 4) + secret[-4:] if len(secret) > 4 else "•" * len(secret)


class ComputeConfig:
    """Snapshot of compute-related env at read time (not cached — tests vary it)."""

    def __init__(self) -> None:
        self.remote_gpu_enabled = _b("HELIXFORGE_REMOTE_GPU_ENABLED", False)
        self.remote_gpu_provider = os.getenv("HELIXFORGE_REMOTE_GPU_PROVIDER", "generic_rest").strip()
        self.remote_gpu_endpoint = os.getenv("HELIXFORGE_REMOTE_GPU_ENDPOINT", "").strip()
        self.remote_gpu_api_token = os.getenv("HELIXFORGE_REMOTE_GPU_API_TOKEN", "").strip()
        self.remote_gpu_webhook_secret = os.getenv("HELIXFORGE_REMOTE_GPU_WEBHOOK_SECRET", "").strip()
        self.max_job_cost_usd = _f("HELIXFORGE_REMOTE_GPU_MAX_JOB_COST_USD", 10.00)
        self.max_daily_cost_usd = _f("HELIXFORGE_REMOTE_GPU_MAX_DAILY_COST_USD", 30.00)
        self.max_runtime_minutes = _i("HELIXFORGE_REMOTE_GPU_MAX_RUNTIME_MINUTES", 240)
        self.poll_seconds = _i("HELIXFORGE_REMOTE_GPU_POLL_SECONDS", 10)
        self.enable_live_gpu_test = _b("HELIXFORGE_ENABLE_LIVE_GPU_TEST", False)
        # Capability-probe timeouts (seconds). Short so checks never hang.
        self.probe_timeout_seconds = _i("HELIXFORGE_COMPUTE_PROBE_TIMEOUT_SECONDS", 3)

    def remote_configured(self) -> bool:
        return bool(self.remote_gpu_endpoint) and bool(self.remote_gpu_api_token)

    def public_dict(self) -> dict[str, Any]:
        return {
            "remote_gpu_enabled": self.remote_gpu_enabled,
            "remote_gpu_provider": self.remote_gpu_provider,
            "remote_gpu_endpoint_set": bool(self.remote_gpu_endpoint),
            "remote_gpu_configured": self.remote_configured(),
            "api_token_display": _mask(self.remote_gpu_api_token),
            "webhook_secret_set": bool(self.remote_gpu_webhook_secret),
            "budget": {
                "max_job_cost_usd": self.max_job_cost_usd,
                "max_daily_cost_usd": self.max_daily_cost_usd,
                "max_runtime_minutes": self.max_runtime_minutes,
            },
            "poll_seconds": self.poll_seconds,
            "enable_live_gpu_test": self.enable_live_gpu_test,
            "probe_timeout_seconds": self.probe_timeout_seconds,
        }


def get_compute_config() -> ComputeConfig:
    return ComputeConfig()
