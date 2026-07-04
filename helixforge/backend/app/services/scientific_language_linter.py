"""Professional scientific language linter (EN + KO).

Detects overclaiming / unscientific certainty language and proposes conservative
rewrites. Delegates hard forbidden-content detection (synthesis routes, dosage,
etc.) to the existing safety_lint so there is a single source of truth for
hazardous content; this module adds the softer "claim-language" layer that turns
marketing certainty into review-appropriate phrasing.
"""
from __future__ import annotations

import re
from typing import Any

from app.services.safety_lint import _forbidden_hits, detect_overclaims

# (pattern, severity, suggested conservative rewrite)
_EN_RULES = [
    (re.compile(r"\bdiscovered a drug\b", re.I), "REVIEW_REQUIRED", "prioritized an in-silico candidate"),
    (re.compile(r"\bproven efficacy\b|\bproven\b", re.I), "REVIEW_REQUIRED", "supports expert review"),
    (re.compile(r"\bclinically validated\b|\bclinically proven\b", re.I), "BLOCKED", "requires experimental validation"),
    (re.compile(r"\bregulatory approval (is )?likely\b", re.I), "BLOCKED", "regulatory pathway requires expert assessment"),
    (re.compile(r"\bsafe and effective\b", re.I), "BLOCKED", "not a safety/efficacy determination"),
    (re.compile(r"\bguaranteed?\b", re.I), "REVIEW_REQUIRED", "public-data-backed hypothesis"),
    (re.compile(r"\bcures?\b|\bcured\b", re.I), "BLOCKED", "supports research toward"),
    (re.compile(r"\bvalidated treatment\b", re.I), "BLOCKED", "candidate for further research"),
    (re.compile(r"\bbinding confirmed\b", re.I), "REVIEW_REQUIRED", "docking is a prioritization signal, not binding proof"),
    (re.compile(r"\btoxicity ruled out\b", re.I), "BLOCKED", "toxicity not experimentally excluded"),
]

_KO_RULES = [
    (re.compile(r"신약을?\s*발견했다"), "REVIEW_REQUIRED", "in-silico 후보 우선순위화"),
    (re.compile(r"치료\s*효과\s*입증"), "BLOCKED", "추가 실험 검증 필요"),
    (re.compile(r"임상\s*검증\s*완료"), "BLOCKED", "추가 실험 검증 필요"),
    (re.compile(r"규제\s*승인\s*가능"), "BLOCKED", "규제 경로는 전문가 평가 필요"),
    (re.compile(r"안전성이?\s*보장(된다|됨)?"), "BLOCKED", "안전성은 실험적으로 확인되지 않음"),
    (re.compile(r"효과가?\s*확실(하다|함)?"), "REVIEW_REQUIRED", "공개 데이터 기반 탐색 결과"),
    (re.compile(r"치료제\s*개발\s*완료"), "BLOCKED", "전문가 검토가 필요한 가설"),
    (re.compile(r"결합이?\s*확인(됐|되었|됨)"), "REVIEW_REQUIRED", "도킹은 결합 증명이 아닌 우선순위 신호"),
    (re.compile(r"독성이?\s*배제(됐|되었|됨)"), "BLOCKED", "독성은 실험적으로 배제되지 않음"),
]

DISCLAIMER_NOTE = "의학적·규제적 조언이 아님 / not clinical or regulatory advice"


def check(text: str) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for rx, sev, rewrite in _EN_RULES + _KO_RULES:
        for m in rx.finditer(text or ""):
            ctx = (text[max(0, m.start() - 30): m.end() + 30]).replace("\n", " ").strip()
            findings.append({"severity": sev, "phrase": m.group(0), "context": ctx,
                             "suggested_rewrite": rewrite})
    # Hard forbidden content from safety_lint (synthesis/dosage/etc.).
    for hit in _forbidden_hits(text or ""):
        findings.append({"severity": "BLOCKED", "phrase": hit.get("detail", "forbidden content"),
                         "context": "", "suggested_rewrite": "[REMOVE — forbidden content]"})
    # Overclaim patterns from safety_lint.
    for oc in detect_overclaims(text or ""):
        findings.append({"severity": "REVIEW_REQUIRED", "phrase": oc, "context": "",
                         "suggested_rewrite": "conservative in-silico phrasing"})
    status = "BLOCKED" if any(f["severity"] == "BLOCKED" for f in findings) else (
        "REVIEW_REQUIRED" if findings else "PASS")
    return {"status": status, "findings": findings, "count": len(findings),
            "export_safe": status != "BLOCKED", "note": DISCLAIMER_NOTE}


def rewrite_safe(text: str) -> dict[str, Any]:
    """Apply the conservative rewrites for the softer claim-language rules.

    Forbidden content is NOT silently rewritten — it is left for a human to remove
    (only flagged), so we never mask hazardous content by paraphrasing it.
    """
    out = text or ""
    applied: list[dict[str, str]] = []
    for rx, sev, rewrite in _EN_RULES + _KO_RULES:
        if rewrite.startswith("[REMOVE"):
            continue
        new = rx.sub(rewrite, out)
        if new != out:
            applied.append({"rewrite": rewrite, "severity": sev})
            out = new
    post = check(out)
    return {"rewritten": out, "changed": bool(applied), "applied": applied,
            "residual_status": post["status"], "residual_findings": post["findings"],
            "note": "Forbidden content is flagged for human removal, never auto-paraphrased."}
