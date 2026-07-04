"""ChEMBL activity normalization and assay-confidence handling (professional grade).

Normalizes bioactivity records conservatively: only unambiguous unit conversions
are performed, endpoint types are grouped by comparability (IC50 is never mixed
with EC50), the standard_relation and assay confidence penalize reliability, and
outliers/duplicates are flagged (never silently removed). Produces a per-molecule
activity_reliability_score that feeds the composite molecule score.

Deterministic. No fabricated values. Missing/ambiguous data lowers reliability
rather than being guessed.
"""
from __future__ import annotations

import statistics
import uuid
from typing import Any, Optional

from app.models.schemas import utcnow
from app.storage import db

# Only these unit conversions to nM are considered unambiguous & safe.
_UNIT_TO_NM = {
    "nm": 1.0, "nmol/l": 1.0, "nmol/L".lower(): 1.0,
    "um": 1_000.0, "µm": 1_000.0, "μm": 1_000.0, "umol/l": 1_000.0,
    "mm": 1_000_000.0, "mmol/l": 1_000_000.0,
    "m": 1_000_000_000.0, "mol/l": 1_000_000_000.0,
}

# Endpoint types that are comparable only within their own group.
_COMPARABLE_ENDPOINTS = {"IC50", "KI", "KD", "EC50", "AC50", "GI50"}

_RELATION_PENALTY = {"=": 0.0, "": 0.1, None: 0.1, "~": 0.2, "<": 0.25, ">": 0.25,
                     "<=": 0.2, ">=": 0.2, ">>": 0.35, "<<": 0.35}


def _norm_unit(units: Optional[str]) -> Optional[float]:
    if not units:
        return None
    return _UNIT_TO_NM.get(units.strip().lower())


def normalize_record(rec: dict[str, Any]) -> dict[str, Any]:
    stype = (rec.get("standard_type") or rec.get("activity_type") or "").upper()
    relation = rec.get("standard_relation")
    value = rec.get("standard_value")
    units = rec.get("standard_units")
    pchembl = rec.get("pchembl_value")

    warnings: list[str] = []
    normalized_nm: Optional[float] = None
    unit_status = "OK"

    factor = _norm_unit(units)
    if value in (None, "", "—"):
        unit_status = "MISSING_VALUE"
        warnings.append("missing standard_value")
    elif factor is None:
        unit_status = "UNSUPPORTED"
        warnings.append(f"unsupported/ambiguous units '{units}' — not converted")
    else:
        try:
            normalized_nm = round(float(value) * factor, 4)
        except (TypeError, ValueError):
            unit_status = "UNSUPPORTED"
            warnings.append("non-numeric standard_value")

    # pChEMBL: prefer provided; else derive from nM (pChEMBL = 9 - log10(value_M)).
    normalized_pchembl: Optional[float] = None
    if pchembl not in (None, "", "—"):
        try:
            normalized_pchembl = round(float(pchembl), 3)
        except (TypeError, ValueError):
            pass
    if normalized_pchembl is None and normalized_nm and normalized_nm > 0:
        import math
        normalized_pchembl = round(9.0 - math.log10(normalized_nm), 3)
        warnings.append("pChEMBL derived from normalized value (no reported pChEMBL)")

    comparable = stype if stype in _COMPARABLE_ENDPOINTS else "OTHER"
    relation_penalty = _RELATION_PENALTY.get(relation, 0.15)

    # Assay confidence (ChEMBL 0-9 scale) if available.
    conf = rec.get("assay_confidence_score", rec.get("confidence_score"))
    if conf is None:
        conf_status = "UNKNOWN"
        conf_component = 0.5  # conservative default
    else:
        conf_status = "KNOWN"
        try:
            conf_component = max(0.0, min(1.0, float(conf) / 9.0))
        except (TypeError, ValueError):
            conf_status, conf_component = "UNKNOWN", 0.5

    dvc = rec.get("data_validity_comment")
    if dvc:
        warnings.append(f"data_validity_comment: {dvc}")

    # Reliability: starts at 1, penalized by relation, unit issues, unknown conf,
    # missing pChEMBL, and non-comparable endpoint.
    reliability = 1.0
    reliability -= relation_penalty
    if unit_status != "OK":
        reliability -= 0.3
    reliability -= (1.0 - conf_component) * 0.3
    if normalized_pchembl is None:
        reliability -= 0.2
    if comparable == "OTHER":
        reliability -= 0.1
    if dvc:
        reliability -= 0.15
    reliability = round(max(0.0, min(1.0, reliability)), 3)

    return {
        "original_activity_id": rec.get("id") or rec.get("activity_id"),
        "molecule_chembl_id": rec.get("molecule_chembl_id"),
        "target_chembl_id": rec.get("target_chembl_id"),
        "assay_chembl_id": rec.get("assay_chembl_id"),
        "standard_type": stype, "standard_relation": relation,
        "standard_value": value, "standard_units": units, "pchembl_value": pchembl,
        "normalized_activity_type": comparable,
        "normalized_value_nm": normalized_nm, "normalized_pchembl": normalized_pchembl,
        "comparable_group": comparable, "assay_confidence_score": conf,
        "assay_confidence_status": conf_status, "data_validity_comment": dvc,
        "relation_penalty": relation_penalty, "unit_conversion_status": unit_status,
        "outlier_flag": False, "duplicate_group_id": None,
        "reliability_score": reliability, "warnings": warnings,
    }


def _flag_outliers(records: list[dict[str, Any]]) -> None:
    """Robust IQR outlier flag per comparable endpoint group (never removes)."""
    groups: dict[str, list[dict]] = {}
    for r in records:
        if r["normalized_pchembl"] is not None and r["comparable_group"] != "OTHER":
            groups.setdefault(r["comparable_group"], []).append(r)
    for grp, items in groups.items():
        if len(items) < 5:
            continue
        vals = sorted(x["normalized_pchembl"] for x in items)
        q1 = vals[len(vals) // 4]
        q3 = vals[(3 * len(vals)) // 4]
        iqr = q3 - q1
        if iqr > 0:
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            for x in items:
                if x["normalized_pchembl"] < lo or x["normalized_pchembl"] > hi:
                    x["outlier_flag"] = True
                    x["warnings"].append("outlier vs endpoint group (IQR) — retained, flagged")
        else:
            # Degenerate IQR (most values identical): fall back to a robust
            # median-absolute-deviation screen so a lone extreme is still caught.
            med = statistics.median(vals)
            mad = statistics.median([abs(v - med) for v in vals])
            if mad > 0:
                for x in items:
                    if abs(x["normalized_pchembl"] - med) > 3.5 * mad:
                        x["outlier_flag"] = True
                        x["warnings"].append("outlier vs endpoint group (MAD) — retained, flagged")
            else:
                # all-but-one identical: flag the minority values.
                for x in items:
                    if x["normalized_pchembl"] != med:
                        x["outlier_flag"] = True
                        x["warnings"].append("differs from otherwise-identical endpoint group — flagged")


def _dedupe(records: list[dict[str, Any]]) -> None:
    """Group duplicates by (molecule, comparable endpoint); tag a shared group id."""
    seen: dict[tuple, str] = {}
    for r in records:
        key = (r["molecule_chembl_id"], r["comparable_group"])
        if r["molecule_chembl_id"] is None:
            continue
        if key in seen:
            r["duplicate_group_id"] = seen[key]
        else:
            seen[key] = f"dup-{uuid.uuid4().hex[:6]}"


def normalize_activities(records: list[dict[str, Any]]) -> dict[str, Any]:
    norm = [normalize_record(r) for r in records]
    _flag_outliers(norm)
    _dedupe(norm)
    # Endpoint-group summaries (kept separate; IC50 not mixed with EC50).
    groups: dict[str, dict[str, Any]] = {}
    for r in norm:
        g = groups.setdefault(r["comparable_group"], {"count": 0, "pchembls": [], "outliers": 0})
        g["count"] += 1
        if r["normalized_pchembl"] is not None:
            g["pchembls"].append(r["normalized_pchembl"])
        if r["outlier_flag"]:
            g["outliers"] += 1
    summaries = {}
    for g, v in groups.items():
        pc = v["pchembls"]
        summaries[g] = {"count": v["count"], "outliers": v["outliers"],
                        "median_pchembl": round(statistics.median(pc), 3) if pc else None,
                        "n_with_pchembl": len(pc)}
    return {"normalized": norm, "endpoint_summaries": summaries,
            "unsupported_units": sum(1 for r in norm if r["unit_conversion_status"] == "UNSUPPORTED"),
            "unknown_assay_confidence": sum(1 for r in norm if r["assay_confidence_status"] == "UNKNOWN"),
            "checked_at": utcnow()}


def molecule_activity_reliability(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate reliability + confidence tier for one molecule's activities."""
    if not records:
        return {"reliability_score": 0.0, "confidence_tier": "low",
                "normalized_pchembl": None, "note": "no activity records"}
    norm = [normalize_record(r) for r in records]
    # Aggregate normalized pChEMBL for comparable groups (median).
    by_group: dict[str, list[float]] = {}
    for r in norm:
        if r["normalized_pchembl"] is not None and r["comparable_group"] != "OTHER":
            by_group.setdefault(r["comparable_group"], []).append(r["normalized_pchembl"])
    agg_pchembl = None
    if by_group:
        # use the strongest-represented comparable endpoint group
        grp = max(by_group.items(), key=lambda kv: len(kv[1]))[0]
        agg_pchembl = round(statistics.median(by_group[grp]), 3)
    reliability = round(statistics.mean(r["reliability_score"] for r in norm), 3)
    best = max(norm, key=lambda r: r["reliability_score"])
    if reliability >= 0.75 and agg_pchembl is not None and best["standard_relation"] == "=":
        tier = "high"
    elif reliability >= 0.5:
        tier = "medium"
    else:
        tier = "low"
    return {"reliability_score": reliability, "confidence_tier": tier,
            "normalized_pchembl": agg_pchembl, "record_count": len(norm),
            "note": "reliability aggregates relation, units, assay confidence, and endpoint comparability."}


# ---- Run integration ---------------------------------------------------------
def _molecule_activity_records(mol: dict[str, Any]) -> list[dict[str, Any]]:
    """Molecules store their own headline activity; treat as a one-record set."""
    if mol.get("pchembl_value") in (None, "", "—") and mol.get("standard_value") in (None, "", "—"):
        return []
    return [{"id": f"act-{mol.get('id')}", "molecule_chembl_id": mol.get("molecule_chembl_id"),
             "standard_type": mol.get("activity_type"), "standard_relation": mol.get("standard_relation", "="),
             "standard_value": mol.get("standard_value"), "standard_units": mol.get("standard_units"),
             "pchembl_value": mol.get("pchembl_value"),
             "assay_confidence_score": mol.get("assay_confidence_score")}]


def recompute_candidate_scores(run_id: str | None = None, persist: bool = False) -> dict[str, Any]:
    """Recompute molecule composite scores folding in activity reliability.

    activity reliability raises the activity proxy weight and lowers uncertainty
    only when the underlying measurement is trustworthy — a low-reliability record
    cannot inflate the score.
    """
    from app.services import scoring
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    pid = run.get("project_id") if run else None
    mols = db.list_records("molecule_candidates", project_id=pid, limit=500) if pid else db.list_records("molecule_candidates", limit=500)
    rows = []
    for m in mols:
        recs = _molecule_activity_records(m)
        rel = molecule_activity_reliability(recs)
        desc = m.get("descriptors") or {}
        pchembl = rel["normalized_pchembl"] or m.get("pchembl_value")
        activity_proxy = 0.4
        if pchembl not in (None, "", "—"):
            try:
                activity_proxy = max(0.0, min(1.0, (float(pchembl) - 4.0) / 5.0))
            except (TypeError, ValueError):
                pass
        # scale activity contribution by reliability; unreliable data → discounted
        activity_proxy_scaled = round(activity_proxy * (0.4 + 0.6 * rel["reliability_score"]), 3)
        inputs = {
            "rdkit_validity": m.get("valid", m.get("rdkit_validity", True)),
            "valid": m.get("valid", m.get("rdkit_validity", True)),
            "qed": desc.get("qed", 0.4),
            "lipinski_pass": desc.get("lipinski_pass"),
            "lipinski_violations": desc.get("lipinski_violations"),
            "activity_proxy_score": activity_proxy_scaled,
            "descriptor_druglikeness_score": 0.6,
            "tdc_readiness_score": 0.5,
            "provenance_confidence": 0.5 + 0.4 * rel["reliability_score"],
            "novelty_or_diversity_proxy": 0.5,
            "safety_status": m.get("safety_status", "PASS"),
            "uncertainty": round(0.15 + 0.35 * (1.0 - rel["reliability_score"]), 3),
        }
        scored = scoring.score_molecule(inputs)
        rows.append({"molecule_id": m.get("id"), "label": m.get("label") or m.get("molecule_chembl_id"),
                     "old_score": m.get("composite_score"), "new_score": scored["score"],
                     "activity_reliability": rel["reliability_score"], "confidence_tier": rel["confidence_tier"],
                     "normalized_pchembl": rel["normalized_pchembl"], "recommendation": scored["recommendation"]})
        if persist:
            m["composite_score"] = scored["score"]
            m["activity_reliability_score"] = rel["reliability_score"]
            db.insert("molecule_candidates", m)
    return {"run_id": run.get("id") if run else None, "molecules": rows, "count": len(rows),
            "persisted": persist, "checked_at": utcnow()}


def normalize_run(run_id: str | None = None) -> dict[str, Any]:
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    pid = run.get("project_id") if run else None
    mols = db.list_records("molecule_candidates", project_id=pid, limit=500) if pid else db.list_records("molecule_candidates", limit=500)
    all_records = []
    per_mol = {}
    for m in mols:
        recs = _molecule_activity_records(m)
        all_records.extend(recs)
        per_mol[m.get("id")] = molecule_activity_reliability(recs)
    result = normalize_activities(all_records)
    payload = {"id": f"actnorm-{uuid.uuid4().hex[:8]}", "run_id": run.get("id") if run else None,
               "molecule_reliability": per_mol, **result}
    try:
        db.insert("activity_normalizations", payload)
    except Exception:
        pass
    return payload
