"""LLM configuration from environment. Everything is optional; defaults keep the
app fully deterministic and key-free."""
from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

from app.llm.schemas import LLMMode


def _b(name: str, default: bool) -> bool:
    v = os.getenv(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


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


class LLMConfig:
    """Snapshot of LLM-related env at read time. Read via get_llm_config()."""

    def __init__(self) -> None:
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.use_llm = _b("HELIXFORGE_USE_LLM", False)
        raw_mode = os.getenv("HELIXFORGE_LLM_MODE", "deterministic").strip().upper()
        # Accept short aliases.
        alias = {"DETERMINISTIC": LLMMode.DETERMINISTIC_ONLY, "DEV": LLMMode.HYBRID_LLM_DEV,
                 "FINAL": LLMMode.HYBRID_FABLE_FINAL, "REPLAY": LLMMode.RECORDED_HYBRID_REPLAY}
        self.mode = alias.get(raw_mode, raw_mode if raw_mode in LLMMode.ALL else LLMMode.DETERMINISTIC_ONLY)

        self.dev_model = os.getenv("HELIXFORGE_LLM_DEV_MODEL", "claude-sonnet-5")
        self.cheap_model = os.getenv("HELIXFORGE_LLM_CHEAP_MODEL", "claude-haiku-4-5")
        self.final_model = os.getenv("HELIXFORGE_LLM_FINAL_MODEL", "claude-fable-5")
        self.planner_model = os.getenv("HELIXFORGE_LLM_PLANNER_MODEL", "claude-sonnet-5")
        self.hypothesis_model = os.getenv("HELIXFORGE_LLM_HYPOTHESIS_MODEL", "claude-fable-5")
        self.critic_model = os.getenv("HELIXFORGE_LLM_CRITIC_MODEL", "claude-fable-5")

        self.max_cost_per_run = _f("HELIXFORGE_LLM_MAX_COST_PER_RUN_USD", 2.00)
        self.max_cost_per_day = _f("HELIXFORGE_LLM_MAX_COST_PER_DAY_USD", 20.00)
        self.max_tokens_planner = _i("HELIXFORGE_LLM_MAX_OUTPUT_TOKENS_PLANNER", 2500)
        self.max_tokens_hypothesis = _i("HELIXFORGE_LLM_MAX_OUTPUT_TOKENS_HYPOTHESIS", 3500)
        self.max_tokens_critic = _i("HELIXFORGE_LLM_MAX_OUTPUT_TOKENS_CRITIC", 2500)

        self.store_full_prompts = _b("HELIXFORGE_LLM_STORE_FULL_PROMPTS", False)
        self.enable_prompt_cache = _b("HELIXFORGE_LLM_ENABLE_PROMPT_CACHE", True)
        self.timeout_seconds = _i("HELIXFORGE_LLM_TIMEOUT_SECONDS", 90)
        self.max_retries = _i("HELIXFORGE_LLM_MAX_RETRIES", 1)
        self.effort = os.getenv("HELIXFORGE_LLM_EFFORT", "medium")

        # Pricing overrides (promotional Sonnet, etc.). Not immutable truth.
        self.sonnet5_input = _f("HELIXFORGE_SONNET5_INPUT_USD_PER_MTOK", 3.00)
        self.sonnet5_output = _f("HELIXFORGE_SONNET5_OUTPUT_USD_PER_MTOK", 15.00)

        self.enable_live_smoke = _b("HELIXFORGE_ENABLE_LIVE_LLM_SMOKE", False)

    def llm_available(self) -> tuple[bool, str]:
        """Return (available, reason). Available means a real call *could* be made."""
        if not self.use_llm:
            return False, "HELIXFORGE_USE_LLM is false (deterministic mode)."
        if self.mode == LLMMode.DETERMINISTIC_ONLY:
            return False, "HELIXFORGE_LLM_MODE is deterministic."
        if self.mode == LLMMode.RECORDED_HYBRID_REPLAY:
            return False, "Replay mode: no live calls; recorded outputs are used."
        if not self.api_key:
            return False, "ANTHROPIC_API_KEY is not set."
        return True, "LLM available."

    def public_dict(self) -> dict[str, Any]:
        """Config for the /api/llm/config endpoint — NEVER includes the key."""
        avail, reason = self.llm_available()
        return {
            "use_llm": self.use_llm, "mode": self.mode,
            "api_key_present": bool(self.api_key), "api_key_display": _mask(self.api_key),
            "llm_available": avail, "availability_reason": reason,
            "models": {"dev": self.dev_model, "cheap": self.cheap_model, "final": self.final_model,
                       "planner": self.planner_model, "hypothesis": self.hypothesis_model,
                       "critic": self.critic_model},
            "budget": {"max_cost_per_run_usd": self.max_cost_per_run,
                       "max_cost_per_day_usd": self.max_cost_per_day},
            "max_output_tokens": {"planner": self.max_tokens_planner,
                                  "hypothesis": self.max_tokens_hypothesis,
                                  "critic": self.max_tokens_critic},
            "store_full_prompts": self.store_full_prompts,
            "enable_prompt_cache": self.enable_prompt_cache,
            "timeout_seconds": self.timeout_seconds, "max_retries": self.max_retries,
            "effort": self.effort, "enable_live_smoke": self.enable_live_smoke,
        }


def _mask(key: str) -> str:
    if not key:
        return "(not set)"
    if len(key) <= 8:
        return "••••"
    return f"{key[:3]}••••{key[-4:]}"


def get_llm_config() -> LLMConfig:
    # Not cached — env / tests may change it between calls.
    return LLMConfig()
