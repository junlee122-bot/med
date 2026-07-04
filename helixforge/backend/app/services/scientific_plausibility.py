"""Scientific plausibility checker.

Sanity-checks the latest run's candidate molecules and target selection against
well-established drug-likeness ranges (Lipinski Ro5, Veber). This is a plausibility
screen, NOT a claim of activity, safety, or efficacy — it flags values that fall
outside typical small-molecule drug space so a human reviewer can look closer.
Deterministic, provenance-labeled, no fabricated results.
"""
from __future__ import annotations

from typing import Any

from app.models.schemas import utcnow
from app.storage import db

# Established descriptor ranges for oral small-molecule drug-likeness.
RULES: list[dict[str, Any]] = [
    {"key": "mol_weight", "label": "Molecular weight", "min": 150, "max": 500,
     "hard_max": 900, "rule": "Lipinski Ro5 (≤500)"},
    {"key": "logp", "label": "cLogP", "min": -0.4, "max": 5.0,
     "hard_max": 8.0, "rule": "Lipinski Ro5 (≤5)"},
    {"key": "hbd", "label": "H-bond donors", "min": 0, "max": 5,
     "hard_max": 10, "rule": "Lipinski Ro5 (≤5)"},
    {"key": "hba", "label": "H-bond acceptors", "min": 0, "max": 10,
     "hard_max": 18, "rule": "Lipinski Ro5 (≤10)"},
    {"key": "tpsa", "label": "TPSA", "min": 0, "max": 140,
     "hard_max": 200, "rule": "Veber (≤140 Å²)"},
]


def _latest_run() -> dict[str, Any]:
    runs = [r for r in db.list_records("workflow_runs", limit=100)
            if r.get("kind") in ("agentic", "agentic_replay", "real_pipeline")]
    return runs[0] if runs else {}


def _check_molecule(mol: dict[str, Any]) -> dict[str, Any]:
    desc = mol.get("descriptors") or {}
    checks: list[dict[str, Any]] = []
    ro5_violations = 0
    implausible = False
    for r in RULES:
        val = desc.get(r["key"])
        if val is None:
            checks.append({"key": r["key"], "value": None, "status": "unknown",
                           "note": "descriptor not available"})
            continue
        try:
            v = float(val)
        except (TypeError, ValueError):
            checks.append({"key": r["key"], "value": val, "status": "unknown", "note": "non-numeric"})
            continue
        if v > r["hard_max"] or v < (r["min"] - abs(r["min"]) - 5):
            status = "implausible"
            implausible = True
        elif v > r["max"] or v < r["min"]:
            status = "outside_typical"
            if v > r["max"]:
                ro5_violations += 1
        else:
            status = "ok"
        checks.append({"key": r["key"], "value": round(v, 2), "status": status, "rule": r["rule"]})
    # Ro5 allows one violation; two or more is a real flag.
    if implausible:
        verdict = "IMPLAUSIBLE"
    elif ro5_violations >= 2:
        verdict = "OUTSIDE_DRUGLIKE"
    elif not mol.get("valid", True):
        verdict = "INVALID_STRUCTURE"
    else:
        verdict = "PLAUSIBLE"
    return {"molecule_id": mol.get("id"), "label": mol.get("label") or mol.get("molecule_chembl_id"),
            "valid": mol.get("valid"), "verdict": verdict, "ro5_violations": ro5_violations,
            "checks": checks, "source_type": mol.get("source_type")}


def check_run(run_id: str | None = None) -> dict[str, Any]:
    run = db.get("workflow_runs", run_id) if run_id else _latest_run()
    if not run:
        return {"status": "NO_RUN", "note": "No run found — run the pipeline first.",
                "checked_at": utcnow(), "source_type": "HEURISTIC_ANALYSIS"}
    pid = run.get("project_id")
    mols = [m for m in db.list_records("molecule_candidates", project_id=pid, limit=500)]
    results = [_check_molecule(m) for m in mols]
    counts: dict[str, int] = {}
    for r in results:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    n = len(results)
    plausible = counts.get("PLAUSIBLE", 0)
    # Target-side plausibility: does the selected target carry real evidence?
    ev = db.list_records("evidence_items", project_id=pid, limit=500)
    targets = db.list_records("target_candidates", project_id=pid, limit=200)
    target_flags: list[str] = []
    if not targets:
        target_flags.append("선정 타깃 레코드 없음 (target candidate missing).")
    if not ev:
        target_flags.append("연결된 근거(evidence) 레코드 없음 — 타깃 주장 근거 약함.")
    warnings: list[str] = []
    if n and plausible / n < 0.5:
        warnings.append("후보 분자의 절반 미만이 drug-like 범위 — assay 필터/원본 검토 필요.")
    if counts.get("IMPLAUSIBLE"):
        warnings.append(f"{counts['IMPLAUSIBLE']}개 분자가 물리적으로 비현실적 디스크립터 — RDKit 재검증 권장.")
    status = "REVIEW_REQUIRED" if (warnings or target_flags) else "PASS"
    return {
        "status": status, "run_id": run.get("id"), "mode": run.get("kind"),
        "molecule_count": n, "verdict_counts": counts,
        "plausible_fraction": round(plausible / n, 3) if n else None,
        "molecule_results": results[:100], "target_flags": target_flags,
        "warnings": warnings,
        "disclaimer": ("Drug-likeness plausibility screen only — not a claim of activity, safety, or efficacy. "
                       "약물성 타당성 스크리닝일 뿐이며 활성·안전성·효능을 주장하지 않습니다."),
        "source_type": "HEURISTIC_ANALYSIS", "checked_at": utcnow(),
    }
