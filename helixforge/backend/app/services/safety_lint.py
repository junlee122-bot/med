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

# Forbidden actionable content (safety policy). Detection only — we never
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

DISCLAIMER_MARKERS = ("research decision support", "연구 의사결정 보조", "final responsibility", "책임은 연구자")


def detect_overclaims(text: str) -> list[str]:
    hits = []
    for rx, label in OVERCLAIM_PATTERNS:
        if rx.search(text):
            hits.append(label)
    return hits


def rewrite_overclaims(text: str) -> dict[str, Any]:
    out = text
    hits = []
    for rx, label in OVERCLAIM_PATTERNS:
        if rx.search(out):
            hits.append(label)
            out = rx.sub("in-silico hypothesis for expert review", out)
    return {"rewritten": out, "changed": bool(hits), "hits": hits}


def lint_report(markdown: str) -> dict[str, Any]:
    """Return {status, export_safe, findings[]}."""
    findings: list[dict[str, Any]] = []

    for rx, label in FORBIDDEN_PATTERNS:
        if rx.search(markdown):
            findings.append({"severity": "BLOCKED", "category": "forbidden_content",
                             "detail": f"Report contains forbidden content: {label}."})

    for label in detect_overclaims(markdown):
        findings.append({"severity": "REVIEW_REQUIRED", "category": "overclaim",
                         "detail": f"Report contains an overclaim: {label}."})

    if not any(m.lower() in markdown.lower() for m in DISCLAIMER_MARKERS):
        findings.append({"severity": "REVIEW_REQUIRED", "category": "missing_disclaimer",
                         "detail": "Report is missing the human-responsibility disclaimer."})

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
    return {"status": status, "export_safe": export_safe, "findings": findings}
