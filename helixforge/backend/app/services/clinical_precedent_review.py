"""Clinical precedent review — conservative interpretation of ClinicalTrials.gov hits.

Upgrades raw clinical-trial evidence items for the latest workflow run into a
high-level, non-actionable precedent summary: how many registered trials exist,
their inferred phases/statuses/endpoints, and any termination/withdrawal signals.

SAFETY: Clinical precedent is PRECEDENT ONLY. This module never infers efficacy,
never recommends a treatment, and never provides dosing or medical advice. Phase,
status, and intervention class are inferred from free text and marked UNKNOWN when
they cannot be determined. All output is rule-based (HEURISTIC_ANALYSIS) and
requires qualified human expert review. No wet-lab or synthesis content.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from app.models.schemas import SourceType, utcnow
from app.storage import db

# --- Valid precedent-strength labels (exactly these five) -------------------
PRECEDENT_STRENGTHS = (
    "HIGH_PRECEDENT",
    "MODERATE_PRECEDENT",
    "LIMITED_PRECEDENT",
    "NO_PRECEDENT_FOUND",
    "UNKNOWN_DUE_TO_TOOL_ERROR",
)

_FAILURE_TERMS = ("terminated", "withdrawn", "suspended", "failed")

# Phase inference: most-specific first. \b guards keep "phase iii" from also
# matching the phase-2/phase-1 patterns.
_PHASE_PATTERNS: list[tuple[str, str]] = [
    ("EARLY_PHASE_1", r"early\s*phase\s*(?:i|1)\b"),
    ("PHASE_4", r"phase\s*(?:iv|4)\b"),
    ("PHASE_3", r"phase\s*(?:iii|3)\b"),
    ("PHASE_2", r"phase\s*(?:ii|2)\b"),
    ("PHASE_1", r"phase\s*(?:i|1)\b"),
]

_STATUS_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("TERMINATED", ("terminated",)),
    ("WITHDRAWN", ("withdrawn",)),
    ("SUSPENDED", ("suspended",)),
    ("COMPLETED", ("completed",)),
    ("ACTIVE_NOT_RECRUITING", ("active, not recruiting", "active not recruiting")),
    ("NOT_YET_RECRUITING", ("not yet recruiting",)),
    ("RECRUITING", ("recruiting", "enrolling")),
]

_INTERVENTION_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("monoclonal_antibody", ("monoclonal antibody", "antibody")),
    ("kinase_inhibitor", ("kinase inhibitor", "tyrosine kinase")),
    ("checkpoint_immunotherapy", ("checkpoint", "immunotherapy")),
    ("cell_therapy", ("car-t", "car t", "cell therapy")),
    ("vaccine", ("vaccine",)),
    ("chemotherapy", ("chemotherapy", "cytotoxic")),
    ("small_molecule_inhibitor", ("small molecule", "inhibitor")),
]

_POPULATION_KEYWORDS = (
    "advanced", "locally advanced", "metastatic", "refractory", "relapsed",
    "newly diagnosed", "treatment-naive", "first-line", "first line",
    "second-line", "second line", "unresectable", "pediatric", "elderly",
)

_COMPARATOR_KEYWORDS = (
    "placebo", "standard of care", "standard-of-care", "best supportive care",
    "monotherapy", "combination", "active comparator", "open-label",
    "double-blind", "randomized",
)


def classify_endpoint_category(text: str) -> str:
    """Map a trial title/endpoint string to one high-level endpoint category.

    Returns one of: survival, response_rate, biomarker, safety_tolerability,
    pharmacokinetic, quality_of_life, other_unknown. Short abbreviations are
    matched on word boundaries so "os" does not fire inside "dose"/"most".
    """
    t = (text or "").lower()

    def has_word(*words: str) -> bool:
        return any(re.search(rf"\b{re.escape(w)}\b", t) for w in words)

    if "survival" in t or has_word("os", "pfs", "dfs", "efs"):
        return "survival"
    if "response" in t or has_word("orr", "rr", "dcr"):
        return "response_rate"
    if "biomarker" in t or "expression" in t or "mutation" in t:
        return "biomarker"
    if "safety" in t or "tolerab" in t or "adverse" in t or "toxicity" in t:
        return "safety_tolerability"
    if "pharmacokinet" in t or has_word("pk"):
        return "pharmacokinetic"
    if "quality of life" in t or has_word("qol"):
        return "quality_of_life"
    return "other_unknown"


def _trial_text(trial: dict[str, Any]) -> str:
    """Concatenate the readable text fields of a trial-like evidence item."""
    parts: list[str] = []
    for key in ("title", "brief_title", "claim", "text", "summary", "abstract",
                "phase", "status"):
        v = trial.get(key)
        if isinstance(v, str):
            parts.append(v)
    for key in ("primary_outcomes", "interventions", "conditions", "endpoints"):
        v = trial.get(key)
        if isinstance(v, list):
            parts.extend(str(x) for x in v)
    return " ".join(parts)


def _infer_phase(low_text: str) -> str:
    for label, pattern in _PHASE_PATTERNS:
        if re.search(pattern, low_text):
            return label
    return "UNKNOWN"


def _infer_status(low_text: str) -> str:
    for label, needles in _STATUS_KEYWORDS:
        if any(n in low_text for n in needles):
            return label
    return "UNKNOWN"


def _infer_interventions(low_text: str) -> list[str]:
    out: list[str] = []
    for label, needles in _INTERVENTION_KEYWORDS:
        if any(n in low_text for n in needles):
            out.append(label)
    return out


def _precedent_strength(trial_count: int, tool_error: bool = False) -> str:
    """Bucket trial count into a conservative precedent-strength label."""
    if trial_count == 0:
        return "UNKNOWN_DUE_TO_TOOL_ERROR" if tool_error else "NO_PRECEDENT_FOUND"
    if trial_count <= 2:
        return "LIMITED_PRECEDENT"
    if trial_count <= 6:
        return "MODERATE_PRECEDENT"
    return "HIGH_PRECEDENT"


def _detect_tool_error(metrics: dict[str, Any], run: dict[str, Any]) -> bool:
    """Best-effort detection of a ClinicalTrials tool error on the run."""
    if isinstance(metrics, dict):
        for k, v in metrics.items():
            kl = str(k).lower()
            if "error" in kl and v:
                return True
            if kl.endswith("status") and str(v).lower() in ("error", "tool_error", "failed"):
                return True
    if str(run.get("source_type") or "").upper() == SourceType.TOOL_ERROR.value:
        return True
    return False


def _review_trials(
    condition: str,
    target_query: str,
    trials: list[dict[str, Any]],
    run_id: str | None = None,
    project_id: str | None = None,
    tool_error: bool = False,
) -> dict[str, Any]:
    """Core, DB-free precedent interpretation over an explicit list of trials."""
    trial_count = len(trials)
    phases: dict[str, int] = {}
    statuses: dict[str, int] = {}
    endpoint_categories: dict[str, int] = {}
    intervention_set: set[str] = set()
    population_set: set[str] = set()
    comparator_set: set[str] = set()
    failure_signals: list[str] = []

    for t in trials:
        text = _trial_text(t)
        low = text.lower()

        phase = _infer_phase(low)
        phases[phase] = phases.get(phase, 0) + 1

        status = _infer_status(low)
        statuses[status] = statuses.get(status, 0) + 1

        category = classify_endpoint_category(text)
        endpoint_categories[category] = endpoint_categories.get(category, 0) + 1

        intervention_set.update(_infer_interventions(low))
        population_set.update(p for p in _POPULATION_KEYWORDS if p in low)
        comparator_set.update(c for c in _COMPARATOR_KEYWORDS if c in low)

        for term in _FAILURE_TERMS:
            if term in low:
                label = (t.get("title") or t.get("claim")
                         or t.get("identifier") or "trial")
                failure_signals.append(f"{term}: {label}")

    strength = _precedent_strength(trial_count, tool_error)

    limitations = [
        "Clinical precedent reflects prior or ongoing investigation only; it is "
        "not proof of efficacy or safety.",
        "Phase, status, and intervention class are inferred from free text and "
        "may be incomplete; fields shown as UNKNOWN could not be determined.",
        "Trial registration does not imply a positive result; terminated, "
        "withdrawn, or suspended trials may signal difficulties.",
        "No endpoint outcomes, effect sizes, or statistical results are "
        "interpreted here.",
        "This is a rule-based summary, not a substitute for expert clinical or "
        "regulatory review.",
    ]
    if tool_error:
        limitations.append(
            "Trial retrieval reported a tool error; the trial set may be incomplete.")

    disclaimer = (
        "This review summarizes the existence and high-level design of "
        "registered clinical trials as prior investigational context. Clinical "
        "precedent is PRECEDENT only, not proof of efficacy or safety. It does "
        "not assert that any intervention works, is safe, or should be used, and "
        "it provides no treatment recommendation, no dosing guidance, and no "
        "medical advice. All interpretation requires qualified human expert review."
    )

    # Conservative: clinical precedent always warrants expert human review.
    expert_review_needed = True

    return {
        "id": f"cpr-{uuid.uuid4().hex[:8]}",
        "run_id": run_id,
        "workflow_run_id": run_id,
        "project_id": project_id,
        "condition": condition or "",
        "target_query": target_query or "",
        "trial_count": trial_count,
        "phases": phases,
        "statuses": statuses,
        "intervention_classes": sorted(intervention_set),
        "endpoint_categories": endpoint_categories,
        "population_patterns": sorted(population_set),
        "comparator_patterns": sorted(comparator_set),
        "precedent_strength": strength,
        "failure_or_termination_signals": failure_signals,
        "limitations": limitations,
        "expert_review_needed": expert_review_needed,
        "disclaimer": disclaimer,
        "source_type": (SourceType.TOOL_ERROR.value if tool_error
                        else SourceType.HEURISTIC_ANALYSIS.value),
        "created_at": utcnow(),
    }


def review_run(run_id: str | None = None) -> dict[str, Any]:
    """Build a clinical-precedent review for a run's ClinicalTrials.gov evidence.

    Uses the given run, else the most recent workflow run. Trial-like evidence
    items are those whose source_name mentions ClinicalTrials or whose
    identifier_type is NCT. Persists to `clinical_precedent_reviews`.
    """
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    if run_id and not run:
        raise ValueError("workflow run not found")
    run = run or {}
    pid = run.get("project_id")
    rid = run.get("id")

    trials: list[dict[str, Any]] = []
    if pid:
        trials = [
            e for e in db.list_records("evidence_items", project_id=pid, workflow_run_id=rid, limit=1000)
            if "clinicaltrials" in (e.get("source_name") or "").lower()
            or e.get("identifier_type") == "NCT"
        ]

    tool_error = _detect_tool_error(run.get("metrics") or {}, run)
    review = _review_trials(
        condition=run.get("condition") or "",
        target_query=run.get("target_query") or "",
        trials=trials,
        run_id=rid,
        project_id=pid,
        tool_error=tool_error,
    )
    try:
        db.insert("clinical_precedent_reviews", review)
    except Exception:
        pass
    return review
