"""Application configuration.

Settings come from environment variables / .env (via pydantic-settings). A small
runtime-override layer lets the Settings UI adjust non-secret operational values
without editing the process environment. Secret values are never echoed back in
full and never written to logs.
"""
from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent  # helixforge/backend
DATA_DIR = Path(os.getenv("HELIXFORGE_DATA_DIR", BASE_DIR / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
RUNTIME_OVERRIDE_PATH = DATA_DIR / "runtime_settings.json"

# Keys that may be edited at runtime through the Settings UI.
RUNTIME_EDITABLE = {
    "ncbi_api_key",
    "ncbi_email",
    "reinvent4_bin",
    "reinvent4_python",
    "vina_bin",
    "chunk_size",
    "timeout_seconds",
}
SECRET_KEYS = {"ncbi_api_key"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"),
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Service ---
    app_name: str = "HelixForge AI Backend"
    app_version: str = "1.0.0"
    environment: str = Field(default="development")
    cors_origins: str = Field(default="http://localhost:5173,http://localhost:3000,http://127.0.0.1:5173")
    http_user_agent: str = Field(default="HelixForgeAI/1.0 (research decision support; contact via NCBI_EMAIL)")

    # --- External API config ---
    ncbi_api_key: str = Field(default="")
    ncbi_email: str = Field(default="")

    # --- Local scientific tools ---
    reinvent4_bin: str = Field(default="")
    reinvent4_python: str = Field(default="")
    vina_bin: str = Field(default="vina")

    # --- Operational ---
    chunk_size: int = Field(default=50)
    timeout_seconds: int = Field(default=30)
    db_path: str = Field(default=str(DATA_DIR / "helixforge.db"))
    cache_dir: str = Field(default=str(DATA_DIR / "cache"))

    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


def _load_runtime_overrides() -> dict[str, Any]:
    if RUNTIME_OVERRIDE_PATH.exists():
        try:
            return json.loads(RUNTIME_OVERRIDE_PATH.read_text())
        except Exception:
            return {}
    return {}


@lru_cache
def _base_settings() -> Settings:
    return Settings()


def get_settings() -> Settings:
    """Return settings with runtime overrides applied over env-derived defaults."""
    base = _base_settings()
    overrides = _load_runtime_overrides()
    if not overrides:
        return base
    merged = base.model_copy(update={k: v for k, v in overrides.items() if k in RUNTIME_EDITABLE})
    return merged


def set_runtime_overrides(values: dict[str, Any]) -> dict[str, Any]:
    """Persist runtime-editable overrides. Returns the sanitized applied set."""
    current = _load_runtime_overrides()
    applied: dict[str, Any] = {}
    for k, v in values.items():
        if k not in RUNTIME_EDITABLE:
            continue
        if v is None or v == "":
            current.pop(k, None)
        else:
            current[k] = v
        applied[k] = v
    RUNTIME_OVERRIDE_PATH.write_text(json.dumps(current, indent=2))
    return applied


def mask_secret(value: str) -> str:
    """Mask a secret for display: keep last 4 chars, never the whole value."""
    if not value:
        return ""
    if len(value) <= 4:
        return "•" * len(value)
    return "•" * (len(value) - 4) + value[-4:]


def settings_status() -> dict[str, Any]:
    """Non-secret view of current settings for the Settings UI."""
    s = get_settings()
    return {
        "ncbi_api_key": {"set": bool(s.ncbi_api_key), "preview": mask_secret(s.ncbi_api_key)},
        "ncbi_email": {"set": bool(s.ncbi_email), "value": s.ncbi_email},
        "reinvent4_bin": {"set": bool(s.reinvent4_bin), "value": s.reinvent4_bin},
        "reinvent4_python": {"set": bool(s.reinvent4_python), "value": s.reinvent4_python},
        "vina_bin": {"set": bool(s.vina_bin), "value": s.vina_bin},
        "chunk_size": {"value": s.chunk_size},
        "timeout_seconds": {"value": s.timeout_seconds},
    }
