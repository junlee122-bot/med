"""Safety lint: overclaim rewriting + report-markdown linting.

Deterministic, non-actionable. Detects forbidden content and provenance
mistakes in a report before export. Never emits actionable hazardous detail.
"""
from __future__ import annotations

import re
from typing import Any

OVERCLAIM_PATTERNS = [
    (re.compile(r"\bvalidated cure\b", re.I), '"validated cure"'),
    (re.compile(r"\bproven efficacy\b", re.I), '"proven efficacy"'),
    (re.compile(r"\bclinically (proven|confirmed)\b", re.I), '"clinically proven/confirmed"'),
    (re.compile(r"\bguaranteed\b", re.I), '"guaranteed"'),
    (re.compile(r"\b100% (safe|effective)\b", re.I), '"100% safe/effective"'),
    (re.compile(r"\bcure[sd]?\b (cancer|disease)", re.I), '"cures disease"'),
]

# Korean overclaim patterns (Phase 4). Rewritten to conservative phrasing.
OVERCLAIM_PATTERNS_KO = [
    (re.compile(r"신약을?\s*발견했다"), '"신약을 발견했다"'),
    (re.compile(r"치료제를?\s*개발했다"), '"치료제를 개발했다"'),
    (re.compile(r"신약\s*개발\s*완료"), '"신약 개발 완료"'),
    (re.compile(r"완전\s*자동\s*신약개발"), '"완전 자동 신약개발"'),
    (re.compile(r"임상\s*효과가?\s*입증(됐|되었|됨)"), '"임상 효과 입증"'),
    (re.compile(r"안전성이?\s*보장(된다|됨)"), '"안전성이 보장된다"'),
    (re.compile(r"100%\s*(안전|효과)"), '"100% 안전/효과"'),
    (re.compile(r"승인\s*가능성이?\s*확실"), '"승인 가능성이 확실하다"'),
    (re.compile(r"습식\s*실험\s*없이\s*검증\s*완료"), '"습식 실험 없이 검증 완료"'),
    (re.compile(r"치료\s*효과\s*입증"), '"치료 효과 입증"'),
]

# English forbidden actionable content (safety policy). Detection only — we never
# generate these; this guards against accidental leakage into a report.
FORBIDDEN_PATTERNS = [
    (re.compile(r"step[- ]by[- ]step synthesis", re.I), "step-by-step synthesis"),
    (re.compile(r"\breaction conditions?\b", re.I), "reaction conditions"),
    (re.compile(r"\breagent list\b", re.I), "reagent list"),
    (re.compile(r"\bpurification (procedure|protocol)\b", re.I), "purification procedure"),
    (re.compile(r"\bdosage\b", re.I), "dosage"),
    (re.compile(r"\bincrease toxicity\b", re.I), "toxicity enhancement"),
    (re.compile(r"\blethality\b", re.I), "lethality"),
    (re.compile(r"\bharmful delivery\b", re.I), "harmful delivery"),
    (re.compile(r"\bregulatory approval granted\b", re.I), "false regulatory approval claim"),
]

# Korean forbidden actionable content (Phase 4).
FORBIDDEN_PATTERNS_KO = [
    (re.compile(r"합성\s*경로"), "합성 경로 (synthesis route)"),
    (re.compile(r"합성법"), "합성법 (synthesis method)"),
    (re.compile(r"제조\s*(법|방법)"), "제조법 (preparation method)"),
    (re.compile(r"단계별\s*합성"), "단계별 합성 (step-by-step synthesis)"),
    (re.compile(r"반응\s*조건"), "반응 조건 (reaction conditions)"),
    (re.compile(r"시약\s*목록"), "시약 목록 (reagent list)"),
    (re.compile(r"정제\s*(절차|방법)"), "정제 절차 (purification procedure)"),
    (re.compile(r"(투여량|복용량|용량\s*지침)"), "투여량/복용량 (dosage)"),
    (re.compile(r"독성\s*증가"), "독성 증가 (toxicity enhancement)"),
    (re.compile(r"치사율\s*증가"), "치사율 증가 (lethality increase)"),
    (re.compile(r"(화학무기|폭발물)"), "무기/폭발물 (weapon/explosive)"),
    (re.compile(r"병원성\s*증가"), "병원성 증가 (pathogenicity increase)"),
    (re.compile(r"전달력\s*향상"), "전달력 향상 (delivery enhancement)"),
]

DISCLAIMER_MARKERS = ("research decision support", "연구 의사결정 보조", "final responsibility", "책임은 연구자")

# Conservative Korean replacements for overclaims.
KO_SAFE_REPLACEMENT = "in-silico 후보 우선순위화(전문가 검토 필요)"


def detect_overclaims(text: str) -> list[str]:
    hits = []
    for rx, label in OVERCLAIM_PATTERNS + OVERCLAIM_PATTERNS_KO:
        if rx.search(text):
            hits.append(label)
    return hits


def rewrite_overclaims(text: str) -> dict[str, Any]:
    """English overclaim rewriter (kept for backward compatibility)."""
    out = text
    hits = []
    for rx, label in OVERCLAIM_PATTERNS:
        if rx.search(out):
            hits.append(label)
            out = rx.sub("in-silico hypothesis for expert review", out)
    return {"rewritten": out, "changed": bool(hits), "hits": hits}


def rewrite_overclaims_ko(text: str) -> dict[str, Any]:
    """Korean overclaim rewriter → conservative phrasing."""
    out = text
    hits = []
    for rx, label in OVERCLAIM_PATTERNS_KO:
        if rx.search(out):
            hits.append(label)
            out = rx.sub(KO_SAFE_REPLACEMENT, out)
    return {"rewritten": out, "changed": bool(hits), "hits": hits}


def _forbidden_hits(text: str) -> list[dict]:
    hits = []
    for rx, label in FORBIDDEN_PATTERNS + FORBIDDEN_PATTERNS_KO:
        if rx.search(text):
            hits.append({"severity": "BLOCKED", "category": "forbidden_content",
                         "detail": f"Contains forbidden content: {label}."})
    return hits


def lint_report(markdown: str, require_disclaimer: bool = True) -> dict[str, Any]:
    """Multilingual (EN + KO) report lint. Return {status, export_safe, findings, languages}."""
    findings: list[dict[str, Any]] = list(_forbidden_hits(markdown))

    for label in detect_overclaims(markdown):
        findings.append({"severity": "REVIEW_REQUIRED", "category": "overclaim",
                         "detail": f"Contains an overclaim: {label}."})

    if require_disclaimer and not any(m.lower() in markdown.lower() for m in DISCLAIMER_MARKERS):
        findings.append({"severity": "REVIEW_REQUIRED", "category": "missing_disclaimer",
                         "detail": "Missing the human-responsibility disclaimer."})

    # Provenance mistakes: CONFIGURED_BUT_NOT_RUN represented as real output.
    if re.search(r"CONFIGURED_BUT_NOT_RUN.{0,40}REAL_TOOL_OUTPUT", markdown) or \
       re.search(r"real (docking|generated) (score|molecule)", markdown, re.I):
        findings.append({"severity": "REVIEW_REQUIRED", "category": "provenance",
                         "detail": "Possible mislabeling of a not-run tool as real output."})

    if any(f["severity"] == "BLOCKED" for f in findings):
        status, export_safe = "BLOCKED", False
    elif findings:
        status, export_safe = "REVIEW_REQUIRED", True
    else:
        status, export_safe = "PASS", True
    has_ko = bool(re.search(r"[가-힣]", markdown))
    return {"status": status, "export_safe": export_safe, "findings": findings,
            "languages": (["ko", "en"] if has_ko else ["en"])}


# Aliases / focused variants -------------------------------------------------
def lint_report_multilingual(markdown: str) -> dict[str, Any]:
    return lint_report(markdown, require_disclaimer=True)


def lint_submission_artifact(markdown: str) -> dict[str, Any]:
    # Submission artifacts must be export-safe; disclaimer required.
    return lint_report(markdown, require_disclaimer=True)


def lint_ai_output_text(text: str) -> dict[str, Any]:
    # Free AI output text: check forbidden + overclaim, disclaimer not required.
    return lint_report(text, require_disclaimer=False)
