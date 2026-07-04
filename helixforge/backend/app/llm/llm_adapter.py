"""The single entry point for every reasoning call: `call_llm()`.

Ties together config, model routing, cost guard, prompt cache, replay lookup,
safety detection, schema validation (with one repair), the AI-interaction ledger,
and the LLM-calls store. ALWAYS returns an LLMResult — never raises. When the
result is not usable (`ok=False`), the caller uses its deterministic fallback.

Tests inject a fake client via the `client` argument; production resolves the real
AnthropicClient only when a key is present and USE_LLM is on.
"""
from __future__ import annotations

import hashlib
import uuid
from typing import Any, Callable, Optional

from app.llm import cost_estimator, model_router, prompt_cache, prompt_templates, replay_store, safety
from app.llm.config import get_llm_config
from app.llm.output_validators import validate_and_extract
from app.llm.schemas import (BUDGET_OK, SAFETY_BLOCKED, SAFETY_OK, SCHEMA_INVALID,
                             SCHEMA_NOT_REQUIRED, SCHEMA_REPAIRED, SCHEMA_VALID, LLMClientError,
                             LLMMode, LLMResult, LLMSafetyRefusal, ReasoningSourceType)
from app.models.schemas import utcnow


def _hash(s: str) -> str:
    return "sha256:" + hashlib.sha256((s or "").encode()).hexdigest()[:16]


def _summ(s: str, n: int = 240) -> str:
    s = (s or "").strip().replace("\n", " ")
    return s[:n] + ("…" if len(s) > n else "")


def _blank_result(**kw) -> LLMResult:
    base = dict(
        llm_call_id=f"llm-{uuid.uuid4().hex[:12]}", ok=False,
        reasoning_source_type=ReasoningSourceType.DETERMINISTIC_FALLBACK, data=None, text="",
        provider="none", model="deterministic", purpose="", prompt_template_id="",
        prompt_template_hash="", temperature=None, effort=get_llm_config().effort,
        max_output_tokens=None, input_summary="", output_summary="", input_hash="", output_hash="",
        tokens_in=None, tokens_out=None, estimated_cost_usd=0.0, actual_cost_usd=0.0,
        cache_hit=False, budget_status=BUDGET_OK, fallback_used=True, fallback_reason="",
        schema_validation_status=SCHEMA_NOT_REQUIRED, safety_status=SAFETY_OK, created_at=utcnow(),
    )
    base.update(kw)
    return LLMResult(**base)


def _resolve_client(explicit):
    if explicit is not None:
        return explicit, "injected"
    from app.llm import anthropic_adapter
    if anthropic_adapter.available():
        try:
            return anthropic_adapter.AnthropicClient(), "anthropic"
        except LLMClientError:
            return None, "client_init_failed"
    return None, "unavailable"


def call_llm(
    *, purpose: str, prompt_template_id: str, user_prompt: str,
    required_keys: Optional[list[str]] = None, list_keys: Optional[list[str]] = None,
    run_id: Optional[str] = None, project_id: Optional[str] = None, agent_run_id: Optional[str] = None,
    mode: Optional[str] = None, temperature: float = 0.2, client: Any = None,
    record_ledger: bool = True,
) -> LLMResult:
    cfg = get_llm_config()
    mode = mode or cfg.mode
    routing = model_router.route(purpose, mode)
    model = routing["model"]
    max_tokens = routing["max_output_tokens"]
    sys_prompt = prompt_templates.system_prompt_for(prompt_template_id)
    tmpl_hash = prompt_templates.combined_hash(prompt_template_id)
    in_hash = _hash(model + "|" + sys_prompt + "|" + user_prompt)
    in_summary = _summ(user_prompt)
    schema_status = SCHEMA_NOT_REQUIRED if not required_keys else SCHEMA_VALID

    def finalize(res: LLMResult) -> LLMResult:
        if record_ledger:
            _record(res, run_id, project_id, agent_run_id, sys_prompt, user_prompt)
        return res

    # --- Replay mode: serve recorded output only. ---
    if mode == LLMMode.RECORDED_HYBRID_REPLAY:
        rec = replay_store.find_recorded(purpose, in_hash, run_id)
        if rec and rec.get("data") is not None:
            res = _blank_result(
                ok=True, reasoning_source_type=ReasoningSourceType.RECORDED_LLM_OUTPUT,
                data=rec["data"], text=rec.get("text", ""), provider=rec.get("provider", "recorded"),
                model=rec.get("model", model), purpose=purpose, prompt_template_id=prompt_template_id,
                prompt_template_hash=tmpl_hash, temperature=temperature, max_output_tokens=max_tokens,
                input_summary=in_summary, output_summary=rec.get("output_summary", ""),
                input_hash=in_hash, output_hash=rec.get("output_hash", ""),
                estimated_cost_usd=0.0, actual_cost_usd=0.0, fallback_used=False,
                fallback_reason="", schema_validation_status=schema_status)
            return finalize(res)
        return finalize(_fallback(purpose, prompt_template_id, tmpl_hash, in_hash, in_summary,
                                  "replay mode: no recorded output for this input"))

    # --- Availability gate. ---
    available, reason = cfg.llm_available()
    resolved_client, client_kind = _resolve_client(client)
    if not available and client is None:
        return finalize(_fallback(purpose, prompt_template_id, tmpl_hash, in_hash, in_summary, reason))
    if resolved_client is None:
        return finalize(_fallback(purpose, prompt_template_id, tmpl_hash, in_hash, in_summary,
                                  "no LLM client available (SDK/key missing)"))

    # --- Cost guard (pre-call estimate). ---
    est = cost_estimator.estimate_call_cost(model, len(sys_prompt) + len(user_prompt), max_tokens)
    budget = model_router.check_budget(est["estimated_cost_usd"], run_id)
    if not budget["allowed"]:
        res = _fallback(purpose, prompt_template_id, tmpl_hash, in_hash, in_summary, budget["reason"])
        res.reasoning_source_type = ReasoningSourceType.LLM_BUDGET_BLOCKED
        res.budget_status = budget["status"]
        res.estimated_cost_usd = est["estimated_cost_usd"]
        res.model = model
        return finalize(res)

    # --- Prompt cache. ---
    cached = prompt_cache.get(model, in_hash)
    if cached is not None:
        model_router.record_spend(0.0, run_id, model, purpose, cache_hit=True)
        res = _blank_result(
            ok=True, reasoning_source_type=ReasoningSourceType.REAL_LLM_OUTPUT, data=cached.get("data"),
            text=cached.get("text", ""), provider=client_kind, model=model, purpose=purpose,
            prompt_template_id=prompt_template_id, prompt_template_hash=tmpl_hash, temperature=temperature,
            max_output_tokens=max_tokens, input_summary=in_summary,
            output_summary=cached.get("output_summary", ""), input_hash=in_hash,
            output_hash=cached.get("output_hash", ""), tokens_in=0, tokens_out=0,
            estimated_cost_usd=0.0, actual_cost_usd=0.0, cache_hit=True, fallback_used=False,
            schema_validation_status=(SCHEMA_VALID if required_keys else SCHEMA_NOT_REQUIRED))
        return finalize(res)

    # --- Real call. ---
    try:
        raw = resolved_client.complete(model=model, system=sys_prompt, prompt=user_prompt,
                                       max_tokens=max_tokens, temperature=temperature)
    except LLMSafetyRefusal as e:
        res = _fallback(purpose, prompt_template_id, tmpl_hash, in_hash, in_summary,
                        f"safety refusal: {e}")
        res.reasoning_source_type = ReasoningSourceType.LLM_SAFETY_BLOCKED
        res.safety_status = SAFETY_BLOCKED
        res.model = model
        return finalize(res)
    except (LLMClientError, Exception) as e:  # noqa: BLE001 - never let an LLM error kill a run
        res = _fallback(purpose, prompt_template_id, tmpl_hash, in_hash, in_summary,
                        f"LLM tool error: {str(e)[:160]}")
        res.reasoning_source_type = ReasoningSourceType.LLM_TOOL_ERROR
        res.model = model
        return finalize(res)

    text = safety.strip_chain_of_thought(raw.get("text", ""))
    tokens_in = raw.get("tokens_in")
    tokens_out = raw.get("tokens_out")
    actual_cost = cost_estimator.estimate_cost(model, tokens_in or 0, tokens_out or 0) if (
        tokens_in is not None) else est["estimated_cost_usd"]

    # Output safety screen.
    screen = safety.screen_output_text(text)
    if not screen["safe"]:
        model_router.record_spend(actual_cost, run_id, model, purpose)
        res = _fallback(purpose, prompt_template_id, tmpl_hash, in_hash, in_summary,
                        "LLM output failed safety/language lint")
        res.reasoning_source_type = ReasoningSourceType.LLM_SAFETY_BLOCKED
        res.safety_status = SAFETY_BLOCKED
        res.model = model
        res.actual_cost_usd = actual_cost
        return finalize(res)

    # Schema validation (+ one repair).
    data = None
    if required_keys:
        ok, data, why = validate_and_extract(text, required_keys, list_keys)
        if not ok and cfg.max_retries >= 1:
            repair_budget = model_router.check_budget(est["estimated_cost_usd"], run_id)
            if repair_budget["allowed"]:
                try:
                    repair_prompt = (f"Your previous output was invalid ({why}). "
                                     f"Return ONLY valid minified JSON with keys {required_keys}. "
                                     f"Previous output:\n{text[:2000]}")
                    raw2 = resolved_client.complete(model=model, system=sys_prompt, prompt=repair_prompt,
                                                    max_tokens=max_tokens, temperature=0.0)
                    text2 = safety.strip_chain_of_thought(raw2.get("text", ""))
                    ti2, to2 = raw2.get("tokens_in"), raw2.get("tokens_out")
                    actual_cost += cost_estimator.estimate_cost(model, ti2 or 0, to2 or 0) if ti2 is not None else est["estimated_cost_usd"]
                    ok2, data2, _ = validate_and_extract(text2, required_keys, list_keys)
                    if ok2:
                        data, text, ok, schema_status = data2, text2, True, SCHEMA_REPAIRED
                    else:
                        schema_status = SCHEMA_INVALID
                except Exception:
                    schema_status = SCHEMA_INVALID
            else:
                schema_status = SCHEMA_INVALID
        elif ok:
            schema_status = SCHEMA_VALID
        else:
            schema_status = SCHEMA_INVALID

        if not ok:
            model_router.record_spend(actual_cost, run_id, model, purpose)
            res = _fallback(purpose, prompt_template_id, tmpl_hash, in_hash, in_summary,
                            "LLM output did not satisfy schema after repair")
            res.reasoning_source_type = ReasoningSourceType.LLM_OUTPUT_INVALID
            res.model = model
            res.actual_cost_usd = actual_cost
            res.schema_validation_status = SCHEMA_INVALID
            return finalize(res)

    model_router.record_spend(actual_cost, run_id, model, purpose)
    out_summary = _summ(text)
    result = LLMResult(
        llm_call_id=f"llm-{uuid.uuid4().hex[:12]}", ok=True,
        reasoning_source_type=ReasoningSourceType.REAL_LLM_OUTPUT, data=data, text=text,
        provider=client_kind, model=model, purpose=purpose, prompt_template_id=prompt_template_id,
        prompt_template_hash=tmpl_hash, temperature=temperature, effort=cfg.effort,
        max_output_tokens=max_tokens, input_summary=in_summary, output_summary=out_summary,
        input_hash=in_hash, output_hash=_hash(text), tokens_in=tokens_in, tokens_out=tokens_out,
        estimated_cost_usd=est["estimated_cost_usd"], actual_cost_usd=round(actual_cost, 6),
        cache_hit=False, budget_status=BUDGET_OK, fallback_used=False, fallback_reason="",
        schema_validation_status=schema_status, safety_status=SAFETY_OK, created_at=utcnow())
    prompt_cache.put(model, in_hash, {"data": data, "text": text, "output_summary": out_summary,
                                      "output_hash": result.output_hash})
    return finalize(result)


def _fallback(purpose, template_id, tmpl_hash, in_hash, in_summary, reason) -> LLMResult:
    return _blank_result(
        purpose=purpose, prompt_template_id=template_id, prompt_template_hash=tmpl_hash,
        input_hash=in_hash, input_summary=in_summary, fallback_used=True, fallback_reason=reason,
        reasoning_source_type=ReasoningSourceType.DETERMINISTIC_FALLBACK)


def _record(res: LLMResult, run_id, project_id, agent_run_id, sys_prompt, user_prompt) -> None:
    # 1) LLM-calls store (for replay + snapshot).
    replay_store.persist_call(res, run_id, project_id, agent_run_id, sys_prompt, user_prompt)
    # 2) AI interaction ledger (transparency).
    try:
        from app.services import ai_interaction_ledger as ledger
        ledger.record_llm_call(res, run_id=run_id, project_id=project_id, agent_run_id=agent_run_id)
    except Exception:
        pass


def health() -> dict[str, Any]:
    cfg = get_llm_config()
    from app.llm import anthropic_adapter
    available, reason = cfg.llm_available()
    return {"mode": cfg.mode, "use_llm": cfg.use_llm, "api_key_present": bool(cfg.api_key),
            "sdk_installed": anthropic_adapter.sdk_available(), "llm_available": available,
            "availability_reason": reason, "safe": True,
            "note": "No key or USE_LLM=false → deterministic fallback. The app is fully functional either way.",
            "checked_at": utcnow()}
