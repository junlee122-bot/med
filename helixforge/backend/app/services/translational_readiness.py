"""Translational readiness assessment.

Bridges the in-silico discovery output (targets, molecules, evidence) toward a
clinical / regulatory framing WITHOUT ever claiming clinical, wet-lab, or
regulatory success. It reads a workflow run's stored records and produces a
conservative, capped Technology-Readiness-Level (TRL) assessment that a human
expert can use as a planning aid.

CRITICAL: this system contains NO wet-lab, in-vivo, or clinical data. Every
signal here is computational or database-derived, so the readiness level is
HARD-CAPPED at TRL_4 (ready for expert experimental planning) and can never
imply experimental confirmation, efficacy, dosing, or approval. The final
scientific and clinical judgement always belongs to qualified human researchers.

Deterministic and side-effect-light: reads existing records, returns a plain
dict, and best-effort persists it to ``translational_assessments``.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import SourceType, utcnow
from app.storage import db


# ---------------------------------------------------------------------------
# Readiness levels (ordered weakest -> strongest). TRL_4 is the hard ceiling.
# ---------------------------------------------------------------------------
class ReadinessLevel:
    TRL_0_CONCEPT_ONLY = "TRL_0_CONCEPT_ONLY"
    TRL_1_IN_SILICO_HYPOTHESIS = "TRL_1_IN_SILICO_HYPOTHESIS"
    TRL_2_COMPUTATIONAL_PRIORITIZATION = "TRL_2_COMPUTATIONAL_PRIORITIZATION"
    TRL_3_READY_FOR_EXPERT_REVIEW = "TRL_3_READY_FOR_EXPERT_REVIEW"
    TRL_4_READY_FOR_EXPERIMENTAL_PLANNING = "TRL_4_READY_FOR_EXPERIMENTAL_PLANNING"


# Ordered low -> high; index used to enforce the TRL_4 hard cap.
_LEVEL_ORDER = [
    ReadinessLevel.TRL_0_CONCEPT_ONLY,
    ReadinessLevel.TRL_1_IN_SILICO_HYPOTHESIS,
    ReadinessLevel.TRL_2_COMPUTATIONAL_PRIORITIZATION,
    ReadinessLevel.TRL_3_READY_FOR_EXPERT_REVIEW,
    ReadinessLevel.TRL_4_READY_FOR_EXPERIMENTAL_PLANNING,
]
# Hard ceiling: wet-lab / clinical validation absent, so we never exceed TRL_4.
_MAX_LEVEL = ReadinessLevel.TRL_4_READY_FOR_EXPERIMENTAL_PLANNING

_CAP_NOTE = "in-silico only; wet-lab/clinical validation absent; capped at TRL_4."

_REAL_SOURCES = {
    SourceType.REAL_TOOL_OUTPUT.value,
    SourceType.RECORDED_REAL_TOOL_OUTPUT.value,
}

_EMPTY = (None, "", "-", "—", "n/a", "N/A")


def _cap_level(level: str) -> str:
    """Never return a level stronger than the TRL_4 ceiling."""
    if level not in _LEVEL_ORDER:
        return ReadinessLevel.TRL_0_CONCEPT_ONLY
    return level if _LEVEL_ORDER.index(level) <= _LEVEL_ORDER.index(_MAX_LEVEL) else _MAX_LEVEL


def _has_value(v: Any) -> bool:
    return v not in _EMPTY


def _safe_list(table: str, pid: str | None, rid: str | None, limit: int) -> list[dict[str, Any]]:
    try:
        return (db.list_records(table, project_id=pid, workflow_run_id=rid, limit=limit)
                if pid and rid else [])
    except Exception:
        return []


def assess_run(run_id: str | None = None, *, persist: bool = True) -> dict[str, Any]:
    """Produce a capped translational-readiness assessment for a run.

    Args:
        run_id: workflow run id, or ``None`` to use the most recent run.

    Returns:
        A ``TranslationalReadinessAssessment`` dict. Best-effort persisted to the
        ``translational_assessments`` table.
    """
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    if run_id and not run:
        raise ValueError("workflow run not found")
    run = run or {}
    pid = run.get("project_id")
    rid = run.get("id")
    has_run = bool(run)

    targets = _safe_list("target_candidates", pid, rid, 200)
    molecules = _safe_list("molecule_candidates", pid, rid, 500)
    evidence = _safe_list("evidence_items", pid, rid, 1000)
    docking = _safe_list("docking_jobs", pid, rid, 100)

    # --- Derived signals (all computational / database-level) ----------------
    valid_molecules = [m for m in molecules if m.get("valid")]
    mols_with_activity = [m for m in molecules if _has_value(m.get("pchembl_value"))]
    real_molecules = [m for m in molecules if (m.get("source_type") or "").upper() in _REAL_SOURCES]
    tgts_with_activity = [t for t in targets if t.get("activity_availability")]
    tgts_with_precedent = [t for t in targets if (t.get("clinical_precedent_count") or 0) > 0]
    verified_evidence = [e for e in evidence
                         if (e.get("verification_status") or "").upper() == "VERIFIED"]

    has_targets = len(targets) > 0
    has_molecules = len(molecules) > 0
    has_valid_molecules = len(valid_molecules) > 0
    has_real_activity = bool(mols_with_activity or tgts_with_activity)
    has_clinical_precedent = len(tgts_with_precedent) > 0
    has_strong_evidence = len(verified_evidence) > 0 or len(evidence) >= 3

    docking_complete = any((d.get("status") or "").lower() == "complete" for d in docking)

    # --- Readiness level from available signals (then hard-capped) -----------
    if not has_run and not has_targets and not has_molecules:
        level = ReadinessLevel.TRL_0_CONCEPT_ONLY
    elif not has_run:
        level = ReadinessLevel.TRL_1_IN_SILICO_HYPOTHESIS
    elif has_targets and has_molecules:
        level = ReadinessLevel.TRL_2_COMPUTATIONAL_PRIORITIZATION
        if has_real_activity and has_valid_molecules:
            level = ReadinessLevel.TRL_3_READY_FOR_EXPERT_REVIEW
            if has_strong_evidence and has_clinical_precedent and has_valid_molecules:
                level = ReadinessLevel.TRL_4_READY_FOR_EXPERIMENTAL_PLANNING
    else:
        # A run exists but is missing targets or molecules -> still hypothesis.
        level = ReadinessLevel.TRL_1_IN_SILICO_HYPOTHESIS

    readiness_level = _cap_level(level)

    # --- Sub-readiness blocks ------------------------------------------------
    top_target = None
    if targets:
        top = max(targets, key=lambda t: t.get("score") or 0)
        top_target = top.get("pref_name") or top.get("target_chembl_id")

    target_readiness = {
        "target_count": len(targets),
        "with_clinical_precedent": len(tgts_with_precedent),
        "with_activity_data": len(tgts_with_activity),
        "top_target": top_target,
        "status": "PRIORITIZED_IN_SILICO" if has_targets else "NONE",
        "validation": "requires independent target validation by domain experts",
    }

    molecule_readiness = {
        "molecule_count": len(molecules),
        "rdkit_valid_count": len(valid_molecules),
        "with_measured_activity": len(mols_with_activity),
        "real_source_count": len(real_molecules),
        "status": "COMPUTATIONALLY_PRIORITIZED" if has_molecules else "NONE",
        "note": "computational prioritization only; no wet-lab confirmation performed",
    }

    screened = [m for m in molecules if _has_value(m.get("safety_status"))]
    flagged = [m for m in molecules
               if (m.get("safety_status") or "").upper() not in ("PASS", "OK", "CLEAR", "")]
    safety_readiness = {
        "screened_count": len(screened),
        "flagged_count": len(flagged),
        "status": "PRELIMINARY_IN_SILICO_SCREEN" if screened else "NOT_SCREENED",
        "note": ("in-silico safety-liability screen only; not a safety determination; "
                 "independent toxicology and safety review required"),
    }

    clinical_precedent = {
        "targets_with_precedent": len(tgts_with_precedent),
        "total_precedent_references": sum((t.get("clinical_precedent_count") or 0) for t in targets),
        "source": "ClinicalTrials.gov / literature records" if has_clinical_precedent else "none",
        "interpretation": ("prior clinical interest / precedent only — this indicates that the "
                           "target area has been explored before; it is NOT evidence of efficacy, "
                           "safety, or approval"),
    }

    evidence_grade_summary = {
        "total_evidence_items": len(evidence),
        "verified": len(verified_evidence),
        "unverified": len(evidence) - len(verified_evidence),
        "highest_available_tier": ("clinical-precedent / database / in-silico" if evidence
                                    else "none"),
        "note": "no clinical efficacy evidence is present in this system",
    }

    manufacturability_unknowns = [
        "chemical manufacturability not assessed (out of scope for this system)",
        "scale-up feasibility unknown",
        "process and formulation strategy undefined",
        "supply-chain and material availability not evaluated",
    ]

    # --- Blocking gaps (concrete, deterministic) -----------------------------
    blocking_gaps: list[str] = []
    if not has_run:
        blocking_gaps.append("no workflow run present")
    if not has_targets:
        blocking_gaps.append("no target candidates identified")
    if not has_molecules:
        blocking_gaps.append("no molecule candidates generated")
    if not has_valid_molecules:
        blocking_gaps.append("no RDKit-valid molecules")
    if not has_real_activity:
        blocking_gaps.append("no real ChEMBL bioactivity confirmation")
    # Structural gaps that always hold (no wet-lab in this system):
    blocking_gaps.append("no experimental assay confirmation (in-silico only)")
    if not docking_complete:
        blocking_gaps.append("Vina docking configured-but-not-run (no docking scores)")
    if not _admet_present(pid):
        blocking_gaps.append("no ADMET model trained/validated")
    blocking_gaps.append("no biomarker strategy defined")
    if not has_clinical_precedent:
        blocking_gaps.append("no clinical precedent identified")
    if not verified_evidence:
        blocking_gaps.append("no verified evidence linked")

    # --- Recommended next actions (HIGH-LEVEL only) --------------------------
    recommended_next_actions: list[str] = []
    if not has_run:
        recommended_next_actions.append(
            "Execute the discovery pipeline to generate target and molecule candidates.")
    recommended_next_actions.extend([
        "Independent target validation by domain experts.",
        "In-vitro assay planning by qualified experts.",
        "Biomarker strategy definition with translational scientists.",
        "Safety-liability review by toxicology experts.",
        "Human expert review of prioritized candidates before any downstream use.",
    ])
    if readiness_level in (ReadinessLevel.TRL_3_READY_FOR_EXPERT_REVIEW,
                           ReadinessLevel.TRL_4_READY_FOR_EXPERIMENTAL_PLANNING):
        recommended_next_actions.append(
            "Endpoint and patient-selection strategy definition by clinical experts.")

    biomarker_readiness = ("NOT_STARTED — no biomarker strategy defined; "
                           "requires expert definition and independent validation")
    patient_selection = ("NOT_APPLICABLE — no clinical stage reached; patient-selection strategy "
                         "is undefined and must be set by clinical experts")
    endpoint_strategy = ("UNDEFINED — clinical endpoints require expert and regulatory input; "
                        "none are established by this in-silico system")
    regulatory_documentation_status = ("NOT_STARTED — no regulatory documentation generated; "
                                       "pre-IND / regulatory readiness is not assessed here")

    limitations = [
        _CAP_NOTE,
        "No experimental, in-vivo, or clinical data are present in this system.",
        "Readiness reflects computational prioritization, not therapeutic validation.",
        ("Human review required: final scientific and clinical judgement belongs to qualified "
         "researchers (전문가 검토 필요; 책임은 연구자에게 있습니다)."),
    ]

    disclaimer = (
        "This translational readiness assessment is an in-silico decision-support artifact. "
        "It makes no clinical, wet-lab, or regulatory success claim and provides no dosing, "
        "treatment, or protocol guidance. Human review by qualified domain experts is required "
        "before any downstream use; responsibility for all scientific and clinical decisions "
        "remains with the human research team (전문가 검토 필요, 책임은 연구자)."
    )

    now = utcnow()
    payload: dict[str, Any] = {
        "id": f"transl-{uuid.uuid4().hex[:8]}",
        "project_id": pid,
        "run_id": rid,
        "workflow_run_id": rid,
        "target_readiness": target_readiness,
        "molecule_readiness": molecule_readiness,
        "biomarker_readiness": biomarker_readiness,
        "safety_readiness": safety_readiness,
        "manufacturability_unknowns": manufacturability_unknowns,
        "clinical_precedent": clinical_precedent,
        "patient_selection": patient_selection,
        "endpoint_strategy": endpoint_strategy,
        "regulatory_documentation_status": regulatory_documentation_status,
        "evidence_grade_summary": evidence_grade_summary,
        "readiness_level": readiness_level,
        "readiness_ceiling": _MAX_LEVEL,
        "blocking_gaps": blocking_gaps,
        "recommended_next_actions": recommended_next_actions,
        "limitations": limitations,
        "disclaimer": disclaimer,
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
        "created_at": now,
    }

    if persist:
        try:
            db.insert("translational_assessments", payload)
        except Exception:
            pass
    return payload


def _admet_present(pid: str | None) -> bool:
    try:
        return db.count("admet_validation_jobs", project_id=pid) > 0
    except Exception:
        return False
