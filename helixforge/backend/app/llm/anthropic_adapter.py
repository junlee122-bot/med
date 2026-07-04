"""Real Anthropic client adapter. Optional — the `anthropic` SDK may be absent, in
which case `available()` is False and the layer falls back deterministically. This
module makes the ONLY real network call in the LLM layer."""
from __future__ import annotations

from typing import Any

from app.llm.config import get_llm_config
from app.llm.safety import is_refusal
from app.llm.schemas import LLMClientError, LLMSafetyRefusal

try:  # optional dependency
    import anthropic  # type: ignore
    _SDK = True
except Exception:  # pragma: no cover - depends on environment
    _SDK = False


def sdk_available() -> bool:
    return _SDK


def available() -> bool:
    cfg = get_llm_config()
    return _SDK and bool(cfg.api_key)


class AnthropicClient:
    """Thin wrapper. `complete()` returns a normalized dict and raises the layer's
    typed errors on failure/refusal so the adapter can label the result."""

    def __init__(self) -> None:
        if not _SDK:
            raise LLMClientError("anthropic SDK not installed")
        cfg = get_llm_config()
        if not cfg.api_key:
            raise LLMClientError("ANTHROPIC_API_KEY not set")
        self._client = anthropic.Anthropic(api_key=cfg.api_key, timeout=cfg.timeout_seconds)

    def complete(self, *, model: str, system: str, prompt: str, max_tokens: int,
                 temperature: float = 0.2) -> dict[str, Any]:
        try:
            resp = self._client.messages.create(
                model=model, max_tokens=max_tokens, temperature=temperature,
                system=system, messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:  # transport/API error
            raise LLMClientError(str(e)[:300])

        stop_reason = getattr(resp, "stop_reason", None)
        text = ""
        for block in getattr(resp, "content", []) or []:
            if getattr(block, "type", None) == "text":
                text += getattr(block, "text", "")
        usage = getattr(resp, "usage", None)
        tokens_in = getattr(usage, "input_tokens", None) if usage else None
        tokens_out = getattr(usage, "output_tokens", None) if usage else None

        if is_refusal(text, stop_reason):
            raise LLMSafetyRefusal("model declined on safety grounds")

        return {"text": text, "tokens_in": tokens_in, "tokens_out": tokens_out,
                "stop_reason": stop_reason, "model": model}
