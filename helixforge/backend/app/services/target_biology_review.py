"""Target biology plausibility review — deterministic, conservative, honest.

Reads the existing ``target_candidates`` + ``evidence_items`` for a workflow run
and scores each target across 10 biology dimensions using AVAILABLE signals only
(evidence volume/direction, clinical-precedent count, bioactivity availability,
target type). It never fabricates pathway biology: where a mechanistic/pathway
signal is not independently retrieved, the summary says so and defers to expert
curation, and absent signals yield conservative low/mid scores with an explicit
uncertainty note.

Safety: this module emits only HIGH-LEVEL research-need statements as next steps
(e.g. "selectivity profiling required"). It never emits wet-lab protocols,
reagents, reaction conditions, dosages, or medical/treatment advice, and it
describes clinical precedent as precedent only — never as efficacy or benefit.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import SourceType, utcnow
from app.storage import db

# The only next-step statements this module is permitted to emit. Each is a
# high-level research-need statement — never an actionable protocol.
_ALLOWED_NEXT_STEPS = [
    "orthogonal target validation required",
    "selectivity profiling required",
    "disease-relevant model validation required",
    "biomarker strategy review required",
    "human safety liability review required",
]

# Map each scored dimension to the high-level next step it motivates when weak.
_NEXT_STEP_FOR_DIM = {
    "Disease relevance": "disease-relevant model validation required",
    "Mechanistic plausibility": "orthogonal target validation required",
    "Tractability/druggability": "orthogonal target validation required",
    "Selectivity concern": "selectivity profiling required",
    "Safety liability": "human safety liability review required",
    "Biomarker availability": "biomarker strategy review required",
    "Clinical precedent": "disease-relevant model validation required",
    "Patient stratification": "biomarker strategy review required",
    "Data sufficiency": "orthogonal target validation required",
    "Development risk": "human safety liability review required",
}

_HONEST_MECHANISM = "Mechanistic detail not independently retrieved; requires expert curation."
_HONEST_PATHWAY = "Pathway context not independently retrieved; requires expert curation."


def _c5(x: float) -> int:
    """Clamp to an integer 0..5 score band."""
    return max(0, min(5, int(round(x))))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _vol_band(n: int) -> int:
    """Map an evidence/precedent count to a 1..5 band (deterministic)."""
    if n <= 0:
        return 1
    if n == 1:
        return 2
    if n <= 3:
        return 3
    if n <= 5:
        return 4
    return 5


def review_target(target: dict, evidence: list[dict]) -> dict:
    """Score one target across 10 biology dimensions from available signals only.

    Returns a plain ``TargetBiologyReview`` dict. Never fabricates biology: absent
    signals produce conservative scores with an explicit uncertainty note.
    """
    target = target or {}
    evidence = evidence or []

    # --- Extract available signals (nothing invented) ---
    ev_count = int(target.get("evidence_count") or 0)
    n_evidence = len(evidence)
    effective_ev = max(ev_count, n_evidence)
    support = sum(1 for e in evidence if str(e.get("evidence_direction", "")).lower() == "support")
    contradict = sum(1 for e in evidence if str(e.get("evidence_direction", "")).lower() == "contradict")
    all_ids = [e.get("id") for e in evidence if e.get("id")]
    support_ids = [e.get("id") for e in evidence
                   if str(e.get("evidence_direction", "")).lower() == "support" and e.get("id")]
    precedent = int(target.get("clinical_precedent_count") or 0)
    activity = bool(target.get("activity_availability"))
    ttype = str(target.get("target_type") or "").upper()
    is_single_protein = ttype == "SINGLE PROTEIN"

    dims: list[dict[str, Any]] = []

    # 1. Disease relevance — from retrieved evidence volume/direction only.
    if effective_ev == 0:
        ds = 1
        ds_unc = "no disease-association evidence retrieved"
    else:
        ds = _c5(_vol_band(effective_ev) + min(support, 2) - contradict * 2)
        ds_unc = (f"{contradict} contradicting evidence item(s) present" if contradict
                  else ("evidence direction not annotated" if support == 0 else ""))
    dims.append({"name": "Disease relevance", "score": ds,
                 "rationale": "Assessed from retrieved evidence volume/direction only; not independently curated.",
                 "evidence_ids": support_ids or all_ids, "uncertainty": ds_unc})

    # 2. Mechanistic plausibility — target type is a weak proxy; no pathway invented.
    mp = 3 if is_single_protein else (2 if ttype else 1)
    if support:
        mp = _c5(mp + 1)
    if contradict:
        mp = _c5(mp - contradict)
    dims.append({"name": "Mechanistic plausibility", "score": mp,
                 "rationale": "Proxy from target type and evidence direction; " + _HONEST_MECHANISM,
                 "evidence_ids": support_ids,
                 "uncertainty": "mechanistic detail not independently retrieved; requires expert curation"})

    # 3. Tractability / druggability — target type + whether bioactivity exists.
    tr = 3 if is_single_protein else (2 if ttype in ("PROTEIN COMPLEX", "PROTEIN FAMILY") else 1)
    if activity:
        tr = _c5(tr + 2)
    dims.append({"name": "Tractability/druggability", "score": tr,
                 "rationale": "From target type and availability of ChEMBL bioactivity; potency not assessed here.",
                 "evidence_ids": [],
                 "uncertainty": "" if activity else "no bioactivity availability signal — druggability not demonstrated"})

    # 4. Selectivity concern — no selectivity profiling data available anywhere.
    sc = 3 if activity else 2
    dims.append({"name": "Selectivity concern", "score": sc,
                 "rationale": "No selectivity/off-target panel retrieved; conservative pending profiling.",
                 "evidence_ids": [],
                 "uncertainty": "selectivity not profiled — off-target risk unassessed"})

    # 5. Safety liability — no target-specific safety data retrieved.
    sl = 3 if precedent > 0 else 2
    dims.append({"name": "Safety liability", "score": sl,
                 "rationale": "No target-specific safety liability data retrieved; conservative estimate.",
                 "evidence_ids": [],
                 "uncertainty": "no target-specific safety liability data retrieved — liability UNKNOWN"})

    # 6. Biomarker availability — no biomarker signal available.
    dims.append({"name": "Biomarker availability", "score": 1,
                 "rationale": "No biomarker evidence available in retrieved data.",
                 "evidence_ids": [],
                 "uncertainty": "no biomarker evidence available"})

    # 7. Clinical precedent — count of prior programs; precedent only, not benefit.
    if precedent <= 0:
        cp = 1
        cp_unc = "no clinical precedent referenced"
    else:
        cp = _c5(2 + min(precedent, 3))
        cp_unc = ""
    dims.append({"name": "Clinical precedent", "score": cp,
                 "rationale": (f"Reflects clinical precedent count ({precedent}); precedent indicates prior "
                               "programs only, not a benefit determination."),
                 "evidence_ids": [], "uncertainty": cp_unc})

    # 8. Patient stratification — no stratification / biomarker basis established.
    ps = 2 if (precedent > 0 and effective_ev > 0) else 1
    dims.append({"name": "Patient stratification", "score": ps,
                 "rationale": "No stratification hypothesis established from available data.",
                 "evidence_ids": [],
                 "uncertainty": "no patient-stratification / biomarker basis established"})

    # 9. Data sufficiency — breadth of independent signals retrieved.
    signals = sum([effective_ev > 0, activity, precedent > 0, support > 0])
    dsuf = _c5(1 + signals)
    dims.append({"name": "Data sufficiency", "score": dsuf,
                 "rationale": f"Independent signals present: {signals}/4 (evidence, activity, precedent, support).",
                 "evidence_ids": all_ids,
                 "uncertainty": "" if signals >= 3 else "limited independent data across evidence/activity/precedent"})

    # 10. Development risk — higher score = lower inferred risk (proxy only).
    dr = _c5(1 + (2 if precedent > 0 else 0) + (1 if activity else 0) + (1 if effective_ev > 2 else 0))
    dims.append({"name": "Development risk", "score": dr,
                 "rationale": "Lower-risk proxy from precedent/activity/evidence breadth; not a development plan.",
                 "evidence_ids": [],
                 "uncertainty": "development risk inferred from precedent/data proxies only"})

    # --- Aggregate ---
    scores = [d["score"] for d in dims]
    mean = sum(scores) / len(scores)
    if mean >= 3.5:
        review_status = "PASS"
    elif mean >= 2.5:
        review_status = "REVIEW_REQUIRED"
    elif mean >= 1.5:
        review_status = "WEAK_SUPPORT"
    else:
        review_status = "NOT_RECOMMENDED"

    # Confidence: data-driven, conservative, low when signals are absent.
    confidence = _clamp01(
        0.10
        + 0.12 * signals
        + 0.04 * min(support, 5)
        + 0.03 * min(precedent, 5)
        - 0.05 * contradict
        - (0.10 if effective_ev == 0 else 0.0)
    )
    confidence = round(max(0.05, confidence), 3)

    # Uncertainty reasons: dedup non-empty dimension uncertainties.
    uncertainty_reasons: list[str] = []
    for d in dims:
        u = d.get("uncertainty")
        if u and u not in uncertainty_reasons:
            uncertainty_reasons.append(u)

    # Expert next steps: high-level statements motivated by the weakest dimensions.
    ordered = sorted(dims, key=lambda d: d["score"])
    weak = [d for d in ordered if d["score"] <= 3]
    pool = weak if weak else ordered
    next_steps: list[str] = []
    for d in pool:
        step = _NEXT_STEP_FOR_DIM.get(d["name"])
        if step and step not in next_steps:
            next_steps.append(step)
        if len(next_steps) >= 4:
            break
    for step in _ALLOWED_NEXT_STEPS:  # guarantee at least 2
        if len(next_steps) >= 2:
            break
        if step not in next_steps:
            next_steps.append(step)
    expert_next_steps = next_steps[:4]

    # --- Honest narrative fields (never fabricate biology) ---
    if effective_ev == 0:
        disease_relevance_summary = ("No disease-association evidence retrieved; relevance not verified — "
                                     "requires expert curation.")
    else:
        disease_relevance_summary = (f"{support} supporting and {contradict} contradicting evidence item(s) "
                                     "retrieved; direction/volume only, not independently curated.")

    pharmacological_evidence_status = (
        "Bioactivity data available (pharmacological tractability signal); potency/selectivity not independently verified."
        if activity else
        "No bioactivity data available — pharmacological tractability UNKNOWN."
    )

    if precedent > 0:
        clinical_precedent_status = (f"Clinical precedent present: {precedent} prior clinical program(s)/trial(s) "
                                     "referenced; indicates precedent only, not a claim of clinical benefit.")
    else:
        clinical_precedent_status = "No clinical precedent referenced — UNKNOWN."

    if is_single_protein:
        modality_fit = "Single-protein target — small-molecule tractability plausible; not independently confirmed."
    elif ttype:
        modality_fit = (f"Target type '{target.get('target_type')}' — modality fit UNKNOWN; "
                        "requires expert assessment.")
    else:
        modality_fit = "Target type unavailable — modality fit UNKNOWN."

    return {
        "target_id": target.get("id") or target.get("target_chembl_id"),
        "target_symbol": target.get("pref_name"),
        "target_name": target.get("pref_name"),
        "organism": target.get("organism"),
        "target_type": target.get("target_type"),
        "disease_relevance_summary": disease_relevance_summary,
        "mechanism_summary": _HONEST_MECHANISM,
        "pathway_context": _HONEST_PATHWAY,
        "genetic_evidence_status": "UNKNOWN — no human genetic association evidence retrieved.",
        "pharmacological_evidence_status": pharmacological_evidence_status,
        "clinical_precedent_status": clinical_precedent_status,
        "safety_liability_summary": ("No target-specific safety liability data retrieved; liability UNKNOWN — "
                                     "human safety liability review required before prioritization."),
        "biomarker_readiness": "No biomarker evidence available — biomarker readiness UNKNOWN.",
        "patient_stratification_relevance": ("No stratification hypothesis established from available data — "
                                             "UNKNOWN."),
        "tissue_expression_note": "Tissue expression not independently retrieved — UNKNOWN.",
        "modality_fit": modality_fit,
        "confidence": confidence,
        "review_status": review_status,
        "uncertainty_reasons": uncertainty_reasons,
        "expert_next_steps": expert_next_steps,
        "dimensions": dims,
        "overall_score": round(mean, 3),
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
        "created_at": utcnow(),
    }


def review_run(run_id: str | None = None) -> dict:
    """Load a run's targets + evidence, review each target, persist, and return.

    Falls back to the latest run when ``run_id`` is None; returns an empty-but-valid
    payload when no data exists so callers can always read ``reviews`` /
    ``status_distribution``.
    """
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    if run_id and not run:
        raise ValueError("workflow run not found")
    run = run or {}
    pid = run.get("project_id")
    rid = run.get("id")

    targets = (db.list_records("target_candidates", project_id=pid, workflow_run_id=rid, limit=200)
               if pid and rid else [])
    evidence = (db.list_records("evidence_items", project_id=pid, workflow_run_id=rid, limit=500)
                if pid and rid else [])

    reviews: list[dict[str, Any]] = []
    for t in targets:
        tchembl = t.get("target_chembl_id")
        target_evidence = [e for e in evidence if e.get("target_chembl_id") == tchembl] or evidence
        reviews.append(review_target(t, target_evidence))

    status_distribution: dict[str, int] = {}
    for r in reviews:
        status_distribution[r["review_status"]] = status_distribution.get(r["review_status"], 0) + 1

    payload = {
        "id": f"tbr-{uuid.uuid4().hex[:8]}",
        "project_id": pid,
        "run_id": rid,
        "workflow_run_id": rid,
        "reviews": reviews,
        "count": len(reviews),
        "status_distribution": status_distribution,
        "disclaimer": ("Deterministic heuristic target-biology plausibility review — not a validation of disease "
                       "mechanism, safety, or clinical benefit; requires expert curation. No wet-lab, clinical, "
                       "or regulatory validation implied."),
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
        "checked_at": utcnow(),
        "created_at": utcnow(),
    }
    try:
        db.insert("target_biology_reviews", payload)
    except Exception:
        pass
    return payload
