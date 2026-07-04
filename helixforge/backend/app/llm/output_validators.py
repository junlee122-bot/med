"""Lightweight JSON extraction + structural validation for LLM outputs.

No external jsonschema dependency — we validate the small set of shapes we ask for
(required keys, list/dict types). Returns (ok, data, reason)."""
from __future__ import annotations

import json
import re
from typing import Any, Optional


def extract_json(text: str) -> Optional[Any]:
    """Pull a JSON object/array out of a model response (handles ```json fences)."""
    if not text:
        return None
    t = text.strip()
    # Fenced code block.
    m = re.search(r"```(?:json)?\s*(.*?)```", t, re.S)
    if m:
        t = m.group(1).strip()
    # Direct parse.
    try:
        return json.loads(t)
    except Exception:
        pass
    # First balanced {...} or [...].
    for opener, closer in (("{", "}"), ("[", "]")):
        start = t.find(opener)
        if start == -1:
            continue
        depth = 0
        for i in range(start, len(t)):
            if t[i] == opener:
                depth += 1
            elif t[i] == closer:
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(t[start:i + 1])
                    except Exception:
                        break
    return None


def validate_shape(data: Any, required_keys: list[str],
                   list_keys: Optional[list[str]] = None) -> tuple[bool, str]:
    """Validate a dict has the required keys, and that list_keys are lists."""
    if not isinstance(data, dict):
        return False, f"expected object, got {type(data).__name__}"
    missing = [k for k in required_keys if k not in data]
    if missing:
        return False, f"missing keys: {missing}"
    for k in (list_keys or []):
        if k in data and not isinstance(data[k], list):
            return False, f"key '{k}' must be a list"
    return True, "ok"


def validate_and_extract(text: str, required_keys: list[str],
                         list_keys: Optional[list[str]] = None) -> tuple[bool, Optional[dict], str]:
    data = extract_json(text)
    if data is None:
        return False, None, "no JSON found in output"
    ok, reason = validate_shape(data, required_keys, list_keys)
    return ok, (data if ok else None), reason
