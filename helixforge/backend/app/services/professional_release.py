"""Professional release scorecard.

Aggregates the professional-validation layer into 16 readiness categories (A–P),
each with a 0–100 score, status, blocking issues, and a linked page. Composes the
existing services defensively (a missing/empty run never crashes the scorecard —
it lowers the relevant category and records the gap). Complements, does not
replace, the existing release_readiness module.
"""
from __future__ import annotations

import uuid
from typing import Any, Callable

from app.models.schemas import utcnow
from app.storage import db


def _safe(fn: Callable, default=None):
    try:
        return fn()
    except Exception:
        return default


def _latest_run(run_id: str | None = None) -> dict[str, Any]:
    if run_id:
        run = db.get("workflow_runs", run_id)
        if not run:
            raise ValueError("workflow run not found")
        return run
    runs = db.list_records("workflow_runs", limit=200)
    return runs[0] if runs else {}


def _cat(key, label, score, status, blocking, warnings, page, action):
    return {"key": key, "label": label, "score": round(score, 1), "status": status,
            "blocking_issues": blocking, "warnings": warnings, "linked_page": page,
            "recommended_action": action}


def compute(run_id: str | None = None) -> dict[str, Any]:
    run = _latest_run(run_id)
    rid = run.get("id")
    pid = run.get("project_id")
    has_run = bool(run)
    cats: list[dict] = []

    # A. Evidence integrity
    grades = _safe(lambda: __import__("app.services.evidence_grading", fromlist=["grade_run"]).grade_run(rid), {})
    gd = (grades or {}).get("grade_distribution", {})
    contradicted = gd.get("F_CONTRADICTED", 0)
    total_claims = (grades or {}).get("total_claims", 0)
    a_score = 80 if total_claims else 30
    a_block = ["No graded claims (no run)"] if not total_claims else []
    if contradicted:
        a_score -= 15
    cats.append(_cat("A", "Evidence integrity", a_score, _st(a_score, a_block),
                     a_block, ([f"{contradicted} contradicted claims"] if contradicted else []),
                     "/evidence-grading", "Grade claims; resolve contradictions."))

    # B. Target biology readiness
    tb = _safe(lambda: __import__("app.services.target_biology_review", fromlist=["review_run"]).review_run(rid), {})
    tb_dist = (tb or {}).get("status_distribution", {})
    b_score = 70 if tb_dist else 30
    cats.append(_cat("B", "Target biology readiness", b_score, _st(b_score, [] if tb_dist else ["No target review"]),
                     [] if tb_dist else ["No target biology review"], [], "/professional-review",
                     "Run target biology review."))

    # C. Molecule quality readiness
    mols = (db.list_records("molecule_candidates", project_id=pid, workflow_run_id=rid, limit=500)
            if pid and rid else [])
    valid = [m for m in mols if m.get("valid", m.get("rdkit_validity"))]
    c_score = (len(valid) / len(mols) * 100) if mols else 20
    cats.append(_cat("C", "Molecule quality readiness", c_score, _st(c_score, [] if mols else ["No molecules"]),
                     [] if mols else ["No molecule candidates"], [], "/molecule-qa", "Generate/validate candidates."))

    # D. Activity normalization readiness
    an = _safe(lambda: __import__("app.services.activity_normalization", fromlist=["normalize_run"]).normalize_run(rid), {})
    unsupported = (an or {}).get("unsupported_units", 0)
    d_score = 75 if (an or {}).get("normalized") else 35
    cats.append(_cat("D", "Activity normalization readiness", d_score, _st(d_score, []),
                     [], ([f"{unsupported} unsupported-unit records"] if unsupported else []),
                     "/molecule-qa", "Normalize assay activities."))

    # E. MedChem readiness
    mc = _safe(lambda: __import__("app.services.medchem_review", fromlist=["review_run"]).review_run(rid), {})
    mc_dist = (mc or {}).get("status_distribution", {})
    alerts = mc_dist.get("STRUCTURAL_ALERT_REVIEW", 0)
    e_score = 70 if mc_dist else 30
    cats.append(_cat("E", "MedChem readiness", e_score, _st(e_score, []),
                     [], ([f"{alerts} molecules with structural alerts"] if alerts else []),
                     "/molecule-qa", "Review medicinal-chemistry alerts."))

    # F. Applicability domain readiness
    ad = _safe(lambda: __import__("app.services.applicability_domain", fromlist=["assess_run"]).assess_run(rid), {})
    ad_dist = (ad or {}).get("status_distribution", {})
    ood = ad_dist.get("OUT_OF_DOMAIN", 0)
    f_score = 70 if ad_dist else 30
    cats.append(_cat("F", "Applicability domain readiness", f_score, _st(f_score, []),
                     [], ([f"{ood} out-of-domain molecules"] if ood else []), "/molecule-qa",
                     "Assess applicability domain."))

    # G. ADMET validation readiness
    admet_jobs = (db.list_records("admet_validation_jobs", project_id=pid,
                                  workflow_run_id=rid, limit=10)
                  if pid and rid else [])
    completed = [j for j in admet_jobs if j.get("status") == "COMPLETED"]
    g_score = 65 if completed else 40
    cats.append(_cat("G", "ADMET validation readiness", g_score, _st(g_score, []),
                     [], ([] if completed else ["No trained ADMET baseline (optional)"]),
                     "/tdc", "Optionally train an ADMET baseline with leakage-aware split."))

    # H. Docking governance readiness
    dp = _safe(lambda: __import__("app.services.docking_protocol", fromlist=["run"]).run(rid), {})
    dock_lint = (dp or {}).get("lint", {}).get("status", "REVIEW_REQUIRED")
    h_score = 60 if dp else 40
    cats.append(_cat("H", "Docking governance readiness", h_score,
                     "REVIEW_REQUIRED" if dock_lint != "PASS" else _st(h_score, []),
                     [], ["Docking is a prioritization signal, not binding proof"], "/docking",
                     "Capture docking protocol record."))

    # I. Translational readiness
    tr = _safe(lambda: __import__("app.services.translational_readiness", fromlist=["assess_run"]).assess_run(rid), {})
    trl = (tr or {}).get("readiness_level", "TRL_0_CONCEPT_ONLY")
    i_score = {"TRL_0_CONCEPT_ONLY": 20, "TRL_1_IN_SILICO_HYPOTHESIS": 35,
               "TRL_2_COMPUTATIONAL_PRIORITIZATION": 55, "TRL_3_READY_FOR_EXPERT_REVIEW": 70,
               "TRL_4_READY_FOR_EXPERIMENTAL_PLANNING": 80}.get(trl, 30)
    cats.append(_cat("I", "Translational readiness", i_score, _st(i_score, []),
                     (tr or {}).get("blocking_gaps", [])[:3], [f"Level: {trl} (capped at TRL_4)"],
                     "/professional-review", "Advance readiness with expert review."))

    # J. Clinical precedent readiness
    cp = _safe(lambda: __import__("app.services.clinical_precedent_review", fromlist=["review_run"]).review_run(rid), {})
    strength = (cp or {}).get("precedent_strength", "UNKNOWN_DUE_TO_TOOL_ERROR")
    j_score = {"HIGH_PRECEDENT": 80, "MODERATE_PRECEDENT": 65, "LIMITED_PRECEDENT": 50,
               "NO_PRECEDENT_FOUND": 40, "UNKNOWN_DUE_TO_TOOL_ERROR": 30}.get(strength, 40)
    cats.append(_cat("J", "Clinical precedent readiness", j_score, _st(j_score, []),
                     [], [f"Precedent: {strength} (precedent ≠ efficacy)"], "/clinical",
                     "Review clinical precedent."))

    # K. Safety & ethics readiness
    safety_statuses = [str(m.get("safety_status") or "UNKNOWN").upper() for m in mols]
    unsafe_statuses = [status for status in safety_statuses if status != "PASS"]
    if not mols:
        k_score, k_block = 25, ["No run-scoped molecule safety screens"]
    elif unsafe_statuses:
        k_score, k_block = 35, [f"{len(unsafe_statuses)} molecules lack a PASS safety screen"]
    else:
        k_score, k_block = 85, []
    cats.append(_cat("K", "Safety & ethics readiness", k_score, _st(k_score, k_block),
                     k_block, [], "/safety", "Confirm safety lint + disclaimers."))

    # L. Source-type governance
    gov = _safe(
        lambda: __import__("app.services.source_type_governance", fromlist=["audit"]).audit(pid, rid),
        {},
    )
    gov_status = (gov or {}).get("status", "REVIEW_REQUIRED")
    l_block = ["Source-type governance BLOCKED"] if gov_status == "BLOCKED" else []
    l_score = 90 if gov_status == "PASS" else (55 if gov_status == "REVIEW_REQUIRED" else 20)
    cats.append(_cat("L", "Source-type governance", l_score, gov_status, l_block, [],
                     "/safety", "Resolve mislabeled source types."))

    # M. Reproducibility & replay
    snaps = (db.list_records("run_snapshots", project_id=pid, workflow_run_id=rid, limit=5)
             if pid and rid else [])
    m_score = 80 if snaps else 45
    cats.append(_cat("M", "Reproducibility & replay", m_score, _st(m_score, []),
                     [], ([] if snaps else ["No recorded snapshot"]), "/snapshots",
                     "Record a snapshot for offline replay."))

    # N. Professional documentation
    docs = (db.list_records("professional_documents", project_id=pid, workflow_run_id=rid, limit=50)
            if pid and rid else [])
    n_score = 75 if docs else 35
    cats.append(_cat("N", "Professional documentation", n_score, _st(n_score, []),
                     [], ([] if docs else ["No professional docs generated"]), "/submission",
                     "Generate model/data/risk/validation docs."))

    # O. Expert review readiness
    ers = _safe(lambda: __import__("app.services.expert_review_board", fromlist=["summary_for_run"]).summary_for_run(rid), {}) if rid else {}
    unresolved_high = (ers or {}).get("unresolved_high_risk", 1)
    signed_off = bool((ers or {}).get("all_high_risk_signed_off"))
    if not signed_off and not unresolved_high:
        unresolved_high = 1  # no high-risk queue/sign-offs is itself blocking
    o_block = [f"{unresolved_high} high-risk items require proposal sign-off"] if not signed_off else []
    o_score = 80 if signed_off else (40 if ers else 25)
    cats.append(_cat("O", "Expert review readiness", o_score, _st(o_score, o_block),
                     o_block, [], "/expert-review", "Complete expert review sign-off."))

    # P. Submission readiness (rolls up)
    p_score = min(c["score"] for c in cats) if cats else 0
    p_block = [b for c in cats for b in c["blocking_issues"]]
    cats.append(_cat("P", "Submission readiness", p_score, _st(p_score, p_block),
                     p_block[:5], [], "/submission", "Clear blocking issues across categories."))

    overall = round(sum(c["score"] for c in cats) / len(cats), 1)
    blocking_total = sum(len(c["blocking_issues"]) for c in cats)
    status = _overall_status(overall, blocking_total, has_run, unresolved_high)
    payload = {
        "status": status, "overall_score": overall, "categories": cats,
        "blocking_count": blocking_total,
        "disclaimer": ("Professional readiness self-assessment (HEURISTIC). In-silico only; "
                       "no wet-lab/clinical/regulatory validation is claimed."),
        "source_type": "HEURISTIC_ANALYSIS", "run_id": rid, "computed_at": utcnow(),
    }
    return payload


def _st(score, blocking):
    if blocking:
        return "NOT_READY"
    return "READY" if score >= 70 else ("PARTIAL" if score >= 45 else "NOT_READY")


def _overall_status(overall, blocking_total, has_run, unresolved_high):
    if not has_run:
        return "NOT_READY"
    if blocking_total > 0 or unresolved_high:
        # can still be demo/proposal ready even with expert sign-off pending
        if overall >= 60:
            return "PROPOSAL_READY"
        if overall >= 45:
            return "TECHNICAL_DEMO_READY"
        return "NOT_READY"
    if overall >= 85:
        return "SUBMISSION_READY"
    if overall >= 75:
        return "FINAL_DEMO_READY"
    if overall >= 65:
        return "EXPERT_REVIEW_READY"
    return "PROPOSAL_READY"


def persist(run_id: str | None = None) -> dict[str, Any]:
    card = dict(compute(run_id))
    rid = card.get("run_id")
    run = db.get("workflow_runs", rid) if rid else None
    card.update({
        "id": f"professional-release-{uuid.uuid4().hex[:8]}",
        "project_id": run.get("project_id") if run else None,
        "workflow_run_id": rid,
        "created_at": card.get("computed_at") or utcnow(),
    })
    db.insert("professional_evaluations", card)
    return card
