"""Token cost estimation. Pricing is a configurable SNAPSHOT — not immutable truth.
Verify current rates in the provider console before quoting costs externally."""
from __future__ import annotations

from typing import Any

from app.llm.config import get_llm_config

# USD per million tokens (input, output). Snapshot — see note above.
PRICING_SNAPSHOT: dict[str, dict[str, float]] = {
    "claude-fable-5": {"input": 10.00, "output": 50.00},
    "claude-mythos-5": {"input": 10.00, "output": 50.00},
    "claude-opus-4-8": {"input": 5.00, "output": 25.00},
    "claude-sonnet-5": {"input": 3.00, "output": 15.00},
    "claude-haiku-4-5": {"input": 1.00, "output": 5.00},
}

PRICING_NOTE = ("Pricing snapshot in USD per million tokens; verify current rates in "
                "the provider console. Sonnet 5 rates honor promotional env overrides.")


def _rates(model: str) -> dict[str, float]:
    cfg = get_llm_config()
    if model == "claude-sonnet-5":
        return {"input": cfg.sonnet5_input, "output": cfg.sonnet5_output}
    return PRICING_SNAPSHOT.get(model, {"input": 3.00, "output": 15.00})


def estimate_tokens_from_chars(char_count: int) -> int:
    """Rough heuristic: ~4 chars/token. Used only for pre-call estimation."""
    return max(1, round(char_count / 4))


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    r = _rates(model)
    cost = (tokens_in / 1_000_000) * r["input"] + (tokens_out / 1_000_000) * r["output"]
    return round(cost, 6)


def estimate_call_cost(model: str, prompt_chars: int, max_output_tokens: int) -> dict[str, Any]:
    tin = estimate_tokens_from_chars(prompt_chars)
    tout = max_output_tokens  # worst case
    return {"model": model, "estimated_tokens_in": tin, "estimated_tokens_out": tout,
            "estimated_cost_usd": estimate_cost(model, tin, tout),
            "rates": _rates(model), "pricing_note": PRICING_NOTE}


def pricing_table() -> dict[str, Any]:
    cfg = get_llm_config()
    table = {}
    for m in PRICING_SNAPSHOT:
        table[m] = _rates(m)
    return {"pricing": table, "note": PRICING_NOTE,
            "sonnet5_override_active": (cfg.sonnet5_input != 3.00 or cfg.sonnet5_output != 15.00)}
