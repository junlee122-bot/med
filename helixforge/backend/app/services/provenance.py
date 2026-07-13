"""Provenance & secret handling.

- redact_secrets: strip API keys from any text before logging/exporting.
- cache_reference: record a compact provenance stub for a real HTTP call
  (query, sanitized URL, status, timestamp) without storing secrets or huge blobs.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.config import DATA_DIR, get_settings
from app.models.schemas import utcnow

CACHE_DIR = DATA_DIR / "cache"


def _is_sensitive_key(key: Any) -> bool:
    normalized = str(key).strip().lower()
    exact = {
        "token", "access_token", "refresh_token", "auth_token", "bearer_token",
        "secret", "client_secret", "password", "api_key", "apikey", "authorization",
    }
    suffixes = ("_secret", "_password", "_api_key", "_apikey", "_authorization")
    return normalized in exact or normalized.endswith(suffixes)


def redact_secrets(value: Any) -> Any:
    """Recursively redact secrets from strings and structured export payloads."""
    if isinstance(value, dict):
        return {
            key: (item if isinstance(item, bool) or item is None
                  else "***REDACTED***" if _is_sensitive_key(key)
                  else redact_secrets(item))
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_secrets(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secrets(item) for item in value)
    if not isinstance(value, str) or not value:
        return value
    s = get_settings()
    out = value
    if s.ncbi_api_key:
        out = out.replace(s.ncbi_api_key, "***REDACTED***")
    # Redact the live Anthropic key value if present in the environment.
    import os
    ant = os.getenv("ANTHROPIC_API_KEY", "")
    if ant:
        out = out.replace(ant, "***REDACTED***")
    # Strip common provider key patterns regardless of value (Anthropic/OpenAI style).
    out = re.sub(r"sk-ant-[A-Za-z0-9_\-]+", "***REDACTED***", out)
    out = re.sub(r"\bsk-[A-Za-z0-9]{16,}\b", "***REDACTED***", out)
    # Strip common key-bearing query params regardless of value.
    out = re.sub(r"(api_key|apikey|key|token|authorization)=[^&\s\"']+", r"\1=***REDACTED***", out, flags=re.I)
    return out


def cache_reference(source: str, query: str, url: str, status_code: int, normalized_count: int) -> dict[str, Any]:
    ref = {
        "source": source, "query": query, "url": redact_secrets(url),
        "status_code": status_code, "normalized_count": normalized_count, "retrieved_at": utcnow(),
    }
    try:
        d = CACHE_DIR / source.lower().replace("/", "_").replace(".", "_")
        d.mkdir(parents=True, exist_ok=True)
        # Store only the compact reference, never secrets or large payloads.
        (d / f"ref-{abs(hash(query)) % 10_000_000}.json").write_text(
            str(ref), encoding="utf-8"
        )
    except Exception:
        pass
    return ref
