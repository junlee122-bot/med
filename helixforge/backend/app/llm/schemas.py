"""LLM layer contract — enums + the LLMResult returned by every reasoning call.

Scientific `source_type` (REAL_TOOL_OUTPUT, etc.) and LLM `reasoning_source_type`
are DELIBERATELY separate namespaces. An LLM never produces scientific ground
truth; it produces reasoning that deterministic tools then validate.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Optional


class LLMMode:
    DETERMINISTIC_ONLY = "DETERMINISTIC_ONLY"
    HYBRID_LLM_DEV = "HYBRID_LLM_DEV"
    HYBRID_FABLE_FINAL = "HYBRID_FABLE_FINAL"
    RECORDED_HYBRID_REPLAY = "RECORDED_HYBRID_REPLAY"
    ALL = {DETERMINISTIC_ONLY, HYBRID_LLM_DEV, HYBRID_FABLE_FINAL, RECORDED_HYBRID_REPLAY}


class LLMCallPurpose:
    DYNAMIC_PLANNING = "DYNAMIC_PLANNING"
    REPLANNING = "REPLANNING"
    HYPOTHESIS_REASONING = "HYPOTHESIS_REASONING"
    SEMANTIC_CRITIQUE = "SEMANTIC_CRITIQUE"
    SAFE_REWRITE = "SAFE_REWRITE"
    REPORT_SUMMARY = "REPORT_SUMMARY"
    PROPOSAL_SUMMARY = "PROPOSAL_SUMMARY"
    COST_ESTIMATION_TEST = "COST_ESTIMATION_TEST"
    ALL = {DYNAMIC_PLANNING, REPLANNING, HYPOTHESIS_REASONING, SEMANTIC_CRITIQUE,
           SAFE_REWRITE, REPORT_SUMMARY, PROPOSAL_SUMMARY, COST_ESTIMATION_TEST}


class ReasoningSourceType:
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    REAL_LLM_OUTPUT = "REAL_LLM_OUTPUT"
    RECORDED_LLM_OUTPUT = "RECORDED_LLM_OUTPUT"
    LLM_TOOL_ERROR = "LLM_TOOL_ERROR"
    LLM_BUDGET_BLOCKED = "LLM_BUDGET_BLOCKED"
    LLM_SAFETY_BLOCKED = "LLM_SAFETY_BLOCKED"
    LLM_OUTPUT_INVALID = "LLM_OUTPUT_INVALID"
    ALL = {DETERMINISTIC_FALLBACK, REAL_LLM_OUTPUT, RECORDED_LLM_OUTPUT, LLM_TOOL_ERROR,
           LLM_BUDGET_BLOCKED, LLM_SAFETY_BLOCKED, LLM_OUTPUT_INVALID}


# Budget status
BUDGET_OK = "OK"
BUDGET_BLOCKED_RUN = "BLOCKED_RUN"
BUDGET_BLOCKED_DAY = "BLOCKED_DAY"

# Schema validation status
SCHEMA_NOT_REQUIRED = "NOT_REQUIRED"
SCHEMA_VALID = "VALID"
SCHEMA_REPAIRED = "REPAIRED"
SCHEMA_INVALID = "INVALID"

# Safety status
SAFETY_OK = "OK"
SAFETY_BLOCKED = "SAFETY_BLOCKED"


@dataclass
class LLMResult:
    """The single return type of every reasoning call. `ok` means `data` is usable
    (from a real or recorded LLM output). When `ok` is False, callers must use their
    deterministic fallback; `reasoning_source_type` and `fallback_reason` say why."""
    llm_call_id: str
    ok: bool
    reasoning_source_type: str
    data: Optional[dict]
    text: str
    provider: str
    model: str
    purpose: str
    prompt_template_id: str
    prompt_template_hash: str
    temperature: Optional[float]
    effort: str
    max_output_tokens: Optional[int]
    input_summary: str
    output_summary: str
    input_hash: str
    output_hash: str
    tokens_in: Optional[int]
    tokens_out: Optional[int]
    estimated_cost_usd: float
    actual_cost_usd: Optional[float]
    cache_hit: bool
    budget_status: str
    fallback_used: bool
    fallback_reason: str
    schema_validation_status: str
    safety_status: str
    created_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LLMClientError(Exception):
    """Raised by a client adapter on a transport/API error (→ LLM_TOOL_ERROR)."""


class LLMSafetyRefusal(Exception):
    """Raised by a client adapter when the model refuses on safety grounds
    (→ LLM_SAFETY_BLOCKED; the caller must NOT retry-around it)."""
