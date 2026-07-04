"""Evidence hierarchy and claim grading.

Grades a claim by the *strength* of the evidence that supports it, so a reviewer
can see at a glance whether a statement rests on clinical evidence, an in-vitro
assay, a database association, or an unverified assumption. Deterministic and
conservative: computational or database-only support can never be graded as
clinical truth, and contradictions or failed citations force a downgrade.

Reads the existing `evidence_items` / `hypotheses` / `target_candidates` /
`molecule_candidates` records — it does not create a parallel evidence store.
"""
from __future__ import annotations

import re
import uuid
from typing import Any

from app.models.schemas import utcnow
from app.services.safety_lint import detect_overclaims
from app.storage import db


# ---- Evidence hierarchy ------------------------------------------------------
class EvidenceLevel:
    L1_CLINICAL_GUIDELINE_OR_APPROVAL = "LEVEL_1_CLINICAL_GUIDELINE_OR_APPROVAL_CONTEXT"
    L2_RCT_OR_INTERVENTIONAL = "LEVEL_2_RANDOMIZED_OR_INTERVENTIONAL_CLINICAL_TRIAL"
    L3_OBSERVATIONAL_CLINICAL = "LEVEL_3_OBSERVATIONAL_CLINICAL_OR_REAL_WORLD"
    L4_PRECLINICAL_IN_VIVO = "LEVEL_4_PRECLINICAL_IN_VIVO"
    L5_IN_VITRO_OR_BIOCHEMICAL = "LEVEL_5_IN_VITRO_OR_BIOCHEMICAL_ASSAY"
    L6_COMPUTATIONAL = "LEVEL_6_COMPUTATIONAL_OR_IN_SILICO"
    L7_REVIEW_OR_BACKGROUND = "LEVEL_7_REVIEW_OR_BACKGROUND"
    L8_DATABASE_ASSOCIATION = "LEVEL_8_DATABASE_ASSOCIATION"
    L9_ASSUMPTION = "LEVEL_9_ASSUMPTION_OR_UNVERIFIED"


# lower ordinal = stronger evidence
_LEVEL_RANK = {
    EvidenceLevel.L1_CLINICAL_GUIDELINE_OR_APPROVAL: 1,
    EvidenceLevel.L2_RCT_OR_INTERVENTIONAL: 2,
    EvidenceLevel.L3_OBSERVATIONAL_CLINICAL: 3,
    EvidenceLevel.L4_PRECLINICAL_IN_VIVO: 4,
    EvidenceLevel.L5_IN_VITRO_OR_BIOCHEMICAL: 5,
    EvidenceLevel.L6_COMPUTATIONAL: 6,
    EvidenceLevel.L7_REVIEW_OR_BACKGROUND: 7,
    EvidenceLevel.L8_DATABASE_ASSOCIATION: 8,
    EvidenceLevel.L9_ASSUMPTION: 9,
}


class EvidenceGrade:
    A_STRONG = "A_STRONG"
    B_MODERATE = "B_MODERATE"
    C_PRELIMINARY = "C_PRELIMINARY"
    D_WEAK = "D_WEAK"
    E_UNVERIFIED = "E_UNVERIFIED"
    F_CONTRADICTED = "F_CONTRADICTED"


class ClaimType:
    DISEASE_TARGET_ASSOCIATION = "DISEASE_TARGET_ASSOCIATION"
    TARGET_DRUGGABILITY = "TARGET_DRUGGABILITY"
    TARGET_SAFETY = "TARGET_SAFETY"
    MOLECULE_ACTIVITY = "MOLECULE_ACTIVITY"
    MOLECULE_DRUGLIKENESS = "MOLECULE_DRUGLIKENESS"
    ADMET_RISK = "ADMET_RISK"
    CLINICAL_PRECEDENT = "CLINICAL_PRECEDENT"
    REGULATORY_RISK = "REGULATORY_RISK"
    BUSINESS_IMPACT = "BUSINESS_IMPACT"
    SYSTEM_PERFORMANCE = "SYSTEM_PERFORMANCE"


# Claim types whose evidence is intrinsically NOT clinical efficacy — capped so a
# strong-sounding grade can never imply proven therapeutic effect.
_MAX_GRADE_BY_CLAIM = {
    ClaimType.MOLECULE_ACTIVITY: EvidenceGrade.B_MODERATE,       # assay ≠ efficacy
    ClaimType.MOLECULE_DRUGLIKENESS: EvidenceGrade.C_PRELIMINARY,  # computational
    ClaimType.ADMET_RISK: EvidenceGrade.C_PRELIMINARY,          # model output
    ClaimType.CLINICAL_PRECEDENT: EvidenceGrade.B_MODERATE,     # precedent ≠ proof
    ClaimType.REGULATORY_RISK: EvidenceGrade.C_PRELIMINARY,     # heuristic
    ClaimType.BUSINESS_IMPACT: EvidenceGrade.D_WEAK,            # assumption-heavy
}

_GRADE_ORDER = [EvidenceGrade.A_STRONG, EvidenceGrade.B_MODERATE, EvidenceGrade.C_PRELIMINARY,
                EvidenceGrade.D_WEAK, EvidenceGrade.E_UNVERIFIED, EvidenceGrade.F_CONTRADICTED]


def _cap_grade(grade: str, cap: str | None) -> str:
    if cap is None:
        return grade
    return grade if _GRADE_ORDER.index(grade) >= _GRADE_ORDER.index(cap) else cap


def classify_evidence_level(item: dict[str, Any]) -> str:
    """Map a stored evidence item to an evidence level, conservatively."""
    src = (item.get("source_name") or "").lower()
    stype = (item.get("source_type") or "").upper()
    if stype in ("ASSUMPTION",):
        return EvidenceLevel.L9_ASSUMPTION
    if stype in ("HEURISTIC_ANALYSIS", "BASELINE_MODEL_OUTPUT"):
        return EvidenceLevel.L6_COMPUTATIONAL
    if "clinicaltrials" in src or "clinical trial" in src or item.get("identifier_type") == "NCT":
        # A registered interventional trial is precedent-level clinical evidence.
        return EvidenceLevel.L2_RCT_OR_INTERVENTIONAL
    if "chembl" in src:
        return EvidenceLevel.L5_IN_VITRO_OR_BIOCHEMICAL
    if "tdc" in src or "therapeutics data commons" in src:
        return EvidenceLevel.L6_COMPUTATIONAL
    if "pubmed" in src or "ncbi" in src:
        # Without full-text classification we treat a bare PubMed record as
        # background/review — never as direct experimental proof.
        return EvidenceLevel.L7_REVIEW_OR_BACKGROUND
    if "rdkit" in src:
        return EvidenceLevel.L6_COMPUTATIONAL
    return EvidenceLevel.L8_DATABASE_ASSOCIATION


def _is_failed(item: dict[str, Any]) -> bool:
    vs = (item.get("verification_status") or "").upper()
    return vs in ("FAILED", "UNRESOLVED", "UNVERIFIED", "NOT_FOUND")


def _is_contradiction(item: dict[str, Any]) -> bool:
    return (item.get("evidence_direction") or "").lower() in ("contradict", "contradicts", "against", "refute")


def grade_claim(claim: dict[str, Any], evidence_items: list[dict[str, Any]],
                tool_runs: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Grade a single claim. `claim` needs claim_text, claim_type, linked_evidence_ids."""
    claim_type = claim.get("claim_type", ClaimType.DISEASE_TARGET_ASSOCIATION)
    linked_ids = set(claim.get("linked_evidence_ids") or [])
    linked = [e for e in evidence_items if e.get("id") in linked_ids] if linked_ids else list(evidence_items)

    supports = [e for e in linked if not _is_contradiction(e) and not _is_failed(e)]
    contradictions = [e for e in linked if _is_contradiction(e)]
    failed = [e for e in linked if _is_failed(e)]
    assumptions = [e for e in linked if (e.get("source_type") or "").upper() == "ASSUMPTION"]
    assumption_count = claim.get("assumption_count", len(assumptions))

    levels = [classify_evidence_level(e) for e in supports]
    best_rank = min((_LEVEL_RANK[l] for l in levels), default=99)
    support_count = len(supports)

    # Base grade from strongest supporting evidence level.
    if support_count == 0:
        grade = EvidenceGrade.E_UNVERIFIED
    elif best_rank <= 2:
        grade = EvidenceGrade.A_STRONG
    elif best_rank <= 4:
        grade = EvidenceGrade.B_MODERATE
    elif best_rank <= 6:
        grade = EvidenceGrade.C_PRELIMINARY
    elif best_rank <= 8:
        grade = EvidenceGrade.D_WEAK
    else:
        grade = EvidenceGrade.E_UNVERIFIED

    uncertainty_reasons: list[str] = []
    # Rule: single weak source is preliminary at best.
    if support_count == 1 and grade == EvidenceGrade.A_STRONG:
        grade = EvidenceGrade.B_MODERATE
        uncertainty_reasons.append("single supporting source — not treated as strong.")
    # Rule: contradictions force a downgrade / contradicted grade.
    if contradictions:
        if len(contradictions) >= support_count:
            grade = EvidenceGrade.F_CONTRADICTED
        else:
            grade = _weaken(grade)
        uncertainty_reasons.append(f"{len(contradictions)} contradicting evidence item(s).")
    # Rule: failed / unverified citations cap the grade.
    if failed:
        grade = _cap_grade(grade, EvidenceGrade.E_UNVERIFIED)
        uncertainty_reasons.append(f"{len(failed)} failed/unverified citation(s).")
    # Rule: assumption-only support cannot exceed E.
    if support_count and assumptions and len(assumptions) == support_count:
        grade = _cap_grade(grade, EvidenceGrade.E_UNVERIFIED)
        uncertainty_reasons.append("supported only by assumptions.")
    # Rule: review/background-only support cannot be treated as direct experimental.
    if support_count and all(l in (EvidenceLevel.L7_REVIEW_OR_BACKGROUND, EvidenceLevel.L8_DATABASE_ASSOCIATION)
                             for l in levels):
        grade = _cap_grade(grade, EvidenceGrade.C_PRELIMINARY)
        uncertainty_reasons.append("only review/database-association support — preliminary.")

    # Claim-type ceilings (assay ≠ efficacy, precedent ≠ proof, etc.).
    grade = _cap_grade(grade, _MAX_GRADE_BY_CLAIM.get(claim_type))

    confidence = _grade_confidence(grade, support_count, len(contradictions))
    return {
        "id": claim.get("id") or f"clm-{uuid.uuid4().hex[:8]}",
        "run_id": claim.get("run_id"),
        "claim_text": claim.get("claim_text", ""),
        "claim_type": claim_type,
        "linked_evidence_ids": sorted(linked_ids),
        "linked_tool_run_ids": claim.get("linked_tool_run_ids", []),
        "evidence_levels": sorted(set(levels), key=lambda l: _LEVEL_RANK[l]),
        "evidence_grade": grade,
        "support_count": support_count,
        "contradiction_count": len(contradictions),
        "assumption_count": assumption_count,
        "confidence": confidence,
        "uncertainty_reasons": uncertainty_reasons,
        "reviewer_note": _reviewer_note(grade, claim_type),
        "created_at": utcnow(),
    }


def _weaken(grade: str) -> str:
    i = _GRADE_ORDER.index(grade)
    return _GRADE_ORDER[min(i + 1, len(_GRADE_ORDER) - 1)]


def _grade_confidence(grade: str, support: int, contra: int) -> float:
    base = {EvidenceGrade.A_STRONG: 0.85, EvidenceGrade.B_MODERATE: 0.7,
            EvidenceGrade.C_PRELIMINARY: 0.5, EvidenceGrade.D_WEAK: 0.35,
            EvidenceGrade.E_UNVERIFIED: 0.2, EvidenceGrade.F_CONTRADICTED: 0.1}[grade]
    base += min(0.1, 0.02 * max(0, support - 1))
    base -= min(0.15, 0.05 * contra)
    return round(max(0.05, min(0.95, base)), 2)


def _reviewer_note(grade: str, claim_type: str) -> str:
    if claim_type == ClaimType.MOLECULE_ACTIVITY:
        return "Assay evidence — supports prioritization, not therapeutic efficacy."
    if claim_type == ClaimType.CLINICAL_PRECEDENT:
        return "Clinical precedent — indicates prior interest, not proof of efficacy."
    if claim_type == ClaimType.ADMET_RISK:
        return "Model/heuristic output — not a safety determination."
    if grade in (EvidenceGrade.E_UNVERIFIED, EvidenceGrade.F_CONTRADICTED, EvidenceGrade.D_WEAK):
        return "Weak/unverified — requires expert review before use."
    return "Supports expert review; not a clinical or regulatory conclusion."


# ---- Run-level grading -------------------------------------------------------
def _run_records(run_id: str | None):
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    pid = run.get("project_id") if run else None
    ev = db.list_records("evidence_items", project_id=pid, limit=1000) if pid else db.list_records("evidence_items", limit=1000)
    return run, pid, ev


def grade_hypotheses(run_id: str | None = None) -> dict[str, Any]:
    run, pid, ev = _run_records(run_id)
    hyps = db.list_records("hypotheses", project_id=pid, limit=500) if pid else db.list_records("hypotheses", limit=500)
    graded = []
    for h in hyps:
        claim = {"id": f"clm-hyp-{h.get('id')}", "run_id": run.get("id") if run else None,
                 "claim_text": h.get("statement", ""), "claim_type": ClaimType.DISEASE_TARGET_ASSOCIATION,
                 "linked_evidence_ids": h.get("evidence_ids") or [],
                 "assumption_count": len(h.get("assumptions") or [])}
        graded.append(grade_claim(claim, ev))
    return {"run_id": run.get("id") if run else None, "graded_claims": graded,
            "count": len(graded), "grade_distribution": _dist(graded), "checked_at": utcnow()}


def grade_target_candidates(run_id: str | None = None) -> dict[str, Any]:
    run, pid, ev = _run_records(run_id)
    tgts = db.list_records("target_candidates", project_id=pid, limit=200) if pid else db.list_records("target_candidates", limit=200)
    graded = []
    for t in tgts:
        has_precedent = (t.get("clinical_precedent_count") or 0) > 0
        ctype = ClaimType.CLINICAL_PRECEDENT if has_precedent else ClaimType.DISEASE_TARGET_ASSOCIATION
        claim = {"id": f"clm-tgt-{t.get('id')}", "run_id": run.get("id") if run else None,
                 "claim_text": f"{t.get('pref_name') or t.get('target_chembl_id')} is a candidate target"
                               + (" with clinical precedent" if has_precedent else ""),
                 "claim_type": ctype, "linked_evidence_ids": []}
        # Targets carry counts rather than explicit evidence ids; grade from availability.
        g = _grade_from_counts(claim, t.get("evidence_count") or 0, t.get("clinical_precedent_count") or 0,
                               t.get("activity_availability"))
        graded.append(g)
    return {"run_id": run.get("id") if run else None, "graded_claims": graded,
            "count": len(graded), "grade_distribution": _dist(graded), "checked_at": utcnow()}


def grade_molecule_candidates(run_id: str | None = None) -> dict[str, Any]:
    run, pid, ev = _run_records(run_id)
    mols = db.list_records("molecule_candidates", project_id=pid, limit=500) if pid else db.list_records("molecule_candidates", limit=500)
    graded = []
    for m in mols:
        has_pchembl = m.get("pchembl_value") not in (None, "", "—")
        claim = {"id": f"clm-mol-{m.get('id')}", "run_id": run.get("id") if run else None,
                 "claim_text": f"{m.get('label') or m.get('molecule_chembl_id')} shows measured activity"
                               if has_pchembl else f"{m.get('label') or m.get('molecule_chembl_id')} is a candidate",
                 "claim_type": ClaimType.MOLECULE_ACTIVITY if has_pchembl else ClaimType.MOLECULE_DRUGLIKENESS,
                 "linked_evidence_ids": []}
        # A molecule with a real pChEMBL from ChEMBL is L5 assay evidence.
        level = EvidenceLevel.L5_IN_VITRO_OR_BIOCHEMICAL if has_pchembl else EvidenceLevel.L6_COMPUTATIONAL
        g = _grade_from_level(claim, level, supported=bool(m.get("valid", True)))
        graded.append(g)
    return {"run_id": run.get("id") if run else None, "graded_claims": graded,
            "count": len(graded), "grade_distribution": _dist(graded), "checked_at": utcnow()}


def _grade_from_counts(claim, evidence_count, precedent_count, activity_availability):
    synthetic = []
    for _ in range(min(evidence_count, 5)):
        synthetic.append({"id": f"syn-pub-{uuid.uuid4().hex[:4]}", "source_name": "PubMed", "evidence_direction": "support"})
    for _ in range(min(precedent_count, 5)):
        synthetic.append({"id": f"syn-nct-{uuid.uuid4().hex[:4]}", "source_name": "ClinicalTrials.gov",
                          "identifier_type": "NCT", "evidence_direction": "support"})
    if activity_availability:
        synthetic.append({"id": f"syn-chembl-{uuid.uuid4().hex[:4]}", "source_name": "ChEMBL", "evidence_direction": "support"})
    claim = dict(claim, linked_evidence_ids=[s["id"] for s in synthetic])
    return grade_claim(claim, synthetic)


def _grade_from_level(claim, level: str, supported: bool):
    if not supported:
        item = []
    else:
        item = [{"id": f"syn-{uuid.uuid4().hex[:4]}", "source_name":
                 "ChEMBL" if level == EvidenceLevel.L5_IN_VITRO_OR_BIOCHEMICAL else "RDKit",
                 "evidence_direction": "support"}]
    claim = dict(claim, linked_evidence_ids=[i["id"] for i in item])
    return grade_claim(claim, item)


def _dist(graded: list[dict]) -> dict[str, int]:
    d: dict[str, int] = {}
    for g in graded:
        d[g["evidence_grade"]] = d.get(g["evidence_grade"], 0) + 1
    return d


def grade_run(run_id: str | None = None) -> dict[str, Any]:
    h = grade_hypotheses(run_id)
    t = grade_target_candidates(run_id)
    m = grade_molecule_candidates(run_id)
    all_claims = h["graded_claims"] + t["graded_claims"] + m["graded_claims"]
    payload = {
        "id": f"grades-{uuid.uuid4().hex[:8]}", "run_id": h["run_id"],
        "hypotheses": h, "targets": t, "molecules": m,
        "total_claims": len(all_claims), "grade_distribution": _dist(all_claims),
        "disclaimer": ("Grades reflect evidence STRENGTH only. In-silico and assay evidence are "
                       "not clinical efficacy; final judgement belongs to the human research team."),
        "created_at": utcnow(),
    }
    try:
        db.insert("evidence_claims", payload)
    except Exception:
        pass
    return payload


# ---- Report linting ----------------------------------------------------------
# Strong-claim language that requires strong evidence to be acceptable.
_STRONG_CLAIM_PATTERNS = [
    (re.compile(r"\bprove[sd]?\b|\bproven\b", re.I), "proven"),
    (re.compile(r"\bconfirm(s|ed)?\b", re.I), "confirmed"),
    (re.compile(r"\bvalidated\b", re.I), "validated"),
    (re.compile(r"\bdemonstrat(e|es|ed)\b efficacy", re.I), "demonstrated efficacy"),
    (re.compile(r"\bclinically\b", re.I), "clinically"),
    (re.compile(r"\bcures?\b|\bcured\b", re.I), "cure"),
    (re.compile(r"\bguarantee", re.I), "guarantee"),
    (re.compile(r"신약을?\s*발견"), "신약 발견"),
    (re.compile(r"입증(됨|됐|되었)"), "입증"),
    (re.compile(r"확실(하다|히)"), "확실"),
]


def detect_unsupported_strong_claims(report_markdown: str) -> dict[str, Any]:
    """Flag strong-claim language and delegate forbidden-overclaim detection to safety_lint."""
    findings: list[dict[str, Any]] = []
    for rx, label in _STRONG_CLAIM_PATTERNS:
        for m in rx.finditer(report_markdown or ""):
            ctx = report_markdown[max(0, m.start() - 40): m.end() + 40].replace("\n", " ")
            findings.append({"severity": "REVIEW_REQUIRED", "phrase": label,
                             "context": ctx.strip(),
                             "reason": "Strong-claim language requires Grade A/B evidence — verify support."})
    overclaims = detect_overclaims(report_markdown or "")
    for oc in overclaims:
        findings.append({"severity": "BLOCKED", "phrase": oc, "context": "",
                         "reason": "Overclaim detected by safety lint."})
    status = "BLOCKED" if any(f["severity"] == "BLOCKED" for f in findings) else (
        "REVIEW_REQUIRED" if findings else "PASS")
    return {"status": status, "findings": findings, "count": len(findings), "checked_at": utcnow()}


# Conservative language for weak grades.
_DOWNGRADE_MAP = {
    EvidenceGrade.C_PRELIMINARY: "preliminary, in-silico/public-data-backed signal (expert review required)",
    EvidenceGrade.D_WEAK: "weak, hypothesis-level signal (requires experimental validation)",
    EvidenceGrade.E_UNVERIFIED: "unverified hypothesis (not evidence-backed; requires validation)",
    EvidenceGrade.F_CONTRADICTED: "contradicted signal (do not rely on; conflicting evidence)",
}


def downgrade_claim_language(claim_text: str, evidence_grade: str) -> dict[str, Any]:
    """Soften a claim's phrasing to match its evidence grade."""
    suffix = _DOWNGRADE_MAP.get(evidence_grade)
    if not suffix:
        return {"changed": False, "text": claim_text}
    softened = re.sub(r"\bproven\b|\bconfirmed\b|\bvalidated\b", "supported", claim_text, flags=re.I)
    softened = f"{softened} — {suffix}"
    return {"changed": True, "text": softened, "grade": evidence_grade}
