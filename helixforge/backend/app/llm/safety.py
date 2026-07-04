"""LLM safety envelope + refusal/safety-block detection + output safety screening.

Reuses the existing deterministic safety linters so there is a single source of
truth for forbidden content. Detects model refusals so the caller can fall back
deterministically WITHOUT prompting around the safety boundary.
"""
from __future__ import annotations

import re
from typing import Any

# The biomedical safety-safe envelope injected into every system prompt.
SAFE_ENVELOPE = (
    "You are a research decision-support reasoning assistant for an in-silico drug-"
    "discovery workbench. Absolute rules:\n"
    "- Research decision support only. No medical advice, no clinical or dosing recommendation.\n"
    "- Never output wet-lab protocols, synthesis routes, reaction conditions, reagent lists, "
    "purification procedures, or dosage.\n"
    "- Never optimize for toxicity, lethality, harmful delivery, evasion, or misuse.\n"
    "- Never invent citations. Reference ONLY evidence IDs that are explicitly provided.\n"
    "- Mark assumptions as assumptions; never state an assumption as fact.\n"
    "- Do not claim clinical efficacy, wet-lab validation, or regulatory approval.\n"
    "- Use cautious language: 'in-silico hypothesis', 'candidate for expert review', "
    "'public-data-backed rationale', 'requires experimental validation'.\n"
    "- Avoid 'proven', 'validated', 'cure', 'safe and effective' (and Korean equivalents: "
    "신약을 발견했다, 치료 효과 입증, 안전성이 보장된다).\n"
    "- Do NOT reveal hidden chain-of-thought. Provide only observable summaries "
    "(decision, rationale summary, evidence IDs, assumptions, uncertainty, next action).\n"
    "- When a JSON schema is provided, output ONLY valid JSON matching it — no prose.\n"
)

# Phrases that indicate the model declined / refused on safety grounds.
_REFUSAL_MARKERS = [
    re.compile(r"\bI (can'?t|cannot|won'?t|am unable to) (help|assist|comply|provide|create)\b", re.I),
    re.compile(r"\bI'?m (not able|unable) to\b", re.I),
    re.compile(r"\bagainst (my|the) (guidelines|policy|policies)\b", re.I),
    re.compile(r"\bI (must|have to) decline\b", re.I),
    re.compile(r"\bcannot (safely )?provide (that|this|the requested)\b", re.I),
]


def is_refusal(text: str, stop_reason: str | None = None) -> bool:
    if (stop_reason or "").lower() in ("refusal", "safety", "content_filter", "blocked"):
        return True
    t = (text or "").strip()
    if not t:
        return False
    # Only treat short-ish declines as refusals (avoid flagging long analytical text
    # that merely quotes a rule).
    if len(t) > 1500:
        return False
    return any(rx.search(t) for rx in _REFUSAL_MARKERS)


def screen_output_hard(text: str) -> dict[str, Any]:
    """Coarse safety net for raw LLM output: block ONLY genuinely hazardous content
    (synthesis routes, reagents, reaction conditions, dosage, toxicity enhancement,
    etc.). Overclaim/language handling is done per-field by the reasoner services
    (with a safe-rewrite path), so structured JSON that merely *names* forbidden
    terms in an avoid-list is not falsely blocked here."""
    from app.services.safety_lint import _forbidden_hits
    hits = _forbidden_hits(text or "")
    return {"safe": not hits, "findings": hits,
            "reason": (hits[0]["detail"] if hits else "")}


def screen_output_text(text: str) -> dict[str, Any]:
    """Full screen (hazards + overclaims). Used where overclaim language must also
    be blocked (not the coarse LLM net)."""
    from app.services.safety_lint import lint_report
    from app.services.scientific_language_linter import check as lang_check
    safety = lint_report(text or "", require_disclaimer=False)
    lang = lang_check(text or "")
    blocked = safety["status"] == "BLOCKED" or lang["status"] == "BLOCKED"
    return {"safe": not blocked,
            "safety_lint_status": safety["status"], "language_lint_status": lang["status"],
            "findings": safety.get("findings", []) + lang.get("findings", [])}


# Chain-of-thought markers that must never appear in stored/observable output.
_COT_MARKERS = [
    re.compile(r"<thinking>", re.I), re.compile(r"</thinking>", re.I),
    re.compile(r"\bchain[- ]of[- ]thought\b", re.I), re.compile(r"\bthinking step by step\b", re.I),
    re.compile(r"\blet me think\b", re.I), re.compile(r"\bmy (internal|hidden) (reasoning|thoughts)\b", re.I),
]


def strip_chain_of_thought(text: str) -> str:
    """Remove any <thinking>...</thinking> blocks and CoT preambles defensively."""
    if not text:
        return text
    out = re.sub(r"<thinking>.*?</thinking>", " ", text, flags=re.I | re.S)
    return out.strip()


def contains_chain_of_thought(text: str) -> bool:
    return any(rx.search(text or "") for rx in _COT_MARKERS)
