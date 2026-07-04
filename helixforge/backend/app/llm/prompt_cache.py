"""In-session prompt cache. Keyed by (model, input_hash). Avoids paying twice for
identical calls within a session and feeds the record/replay savings estimate."""
from __future__ import annotations

from typing import Any, Optional

from app.llm.config import get_llm_config

_CACHE: dict[str, dict[str, Any]] = {}
_STATS = {"hits": 0, "misses": 0, "stores": 0}


def _key(model: str, input_hash: str) -> str:
    return f"{model}::{input_hash}"


def get(model: str, input_hash: str) -> Optional[dict[str, Any]]:
    if not get_llm_config().enable_prompt_cache:
        return None
    v = _CACHE.get(_key(model, input_hash))
    if v is not None:
        _STATS["hits"] += 1
    else:
        _STATS["misses"] += 1
    return v


def put(model: str, input_hash: str, value: dict[str, Any]) -> None:
    if not get_llm_config().enable_prompt_cache:
        return
    _CACHE[_key(model, input_hash)] = value
    _STATS["stores"] += 1


def stats() -> dict[str, Any]:
    total = _STATS["hits"] + _STATS["misses"]
    return {"enabled": get_llm_config().enable_prompt_cache, "entries": len(_CACHE),
            "hits": _STATS["hits"], "misses": _STATS["misses"], "stores": _STATS["stores"],
            "hit_rate": round(_STATS["hits"] / total, 3) if total else 0.0}


def clear() -> None:
    _CACHE.clear()
    _STATS.update({"hits": 0, "misses": 0, "stores": 0})
