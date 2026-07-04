"""Optional Fable 5 / LLM reasoning layer for HelixForge.

The app runs fully without an API key: every reasoning call degrades to a
deterministic fallback. Scientific facts always come from the tool layer; the LLM
only reasons, and its outputs are validated by deterministic gates.
"""
from app.llm.llm_adapter import call_llm, health  # noqa: F401
from app.llm.schemas import (LLMCallPurpose, LLMMode, LLMResult,  # noqa: F401
                             ReasoningSourceType)
