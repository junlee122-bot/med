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


def redact_secrets(text: str) -> str:
    if not text:
        return text
    s = get_settings()
    out = text
    if s.ncbi_api_key:
        out = out.replace(s.ncbi_api_key, "***REDACTED***")
    # Strip common key-bearing query params regardless of value.
    out = re.sub(r"(api_key|apikey|key|token)=[^&\s\"']+", r"\1=***REDACTED***", out, flags=re.I)
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
        (d / f"ref-{abs(hash(query)) % 10_000_000}.json").write_text(str(ref))
    except Exception:
        pass
    return ref
