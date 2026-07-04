"""ChEMBL assay / activity quality analysis.

Turns a list of ChEMBL activity records into an honest quality summary: which
standard types/units are present, how much pChEMBL is available, relation
distribution, suspicious values, and conservative unit handling. Records every
reason data was down-weighted rather than silently discarding it.
"""
from __future__ import annotations

import statistics
from typing import Any, Optional

from app.models.schemas import SourceType

PREFERRED_TYPES = {"IC50", "Ki", "Kd", "EC50"}
# nM is the reference unit; only these simple concentration units are converted.
_UNIT_TO_NM = {"nM": 1.0, "uM": 1000.0, "µM": 1000.0, "mM": 1_000_000.0}


def _num(x: Any) -> Optional[float]:
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def assay_quality_summary(target_chembl_id: str, activities: list[dict]) -> dict[str, Any]:
    warnings: list[str] = []
    type_counts: dict[str, int] = {}
    unit_counts: dict[str, int] = {}
    relation_counts: dict[str, int] = {}
    values_by_type: dict[str, list[float]] = {}
    molecules = set()
    pchembl_available = 0
    suspicious = 0

    for a in activities:
        st = a.get("activity_type") or a.get("standard_type") or "unknown"
        type_counts[st] = type_counts.get(st, 0) + 1
        unit = a.get("standard_units") or "none"
        unit_counts[unit] = unit_counts.get(unit, 0) + 1
        rel = a.get("standard_relation") or a.get("relation") or "="
        relation_counts[rel] = relation_counts.get(rel, 0) + 1
        if a.get("molecule_chembl_id"):
            molecules.add(a["molecule_chembl_id"])
        if a.get("pchembl_value") not in (None, ""):
            pchembl_available += 1
        v = _num(a.get("standard_value"))
        if v is not None:
            if v <= 0 or v > 1e9:
                suspicious += 1
            else:
                values_by_type.setdefault(st, []).append(v)

    median_by_type = {t: round(statistics.median(vs), 3) for t, vs in values_by_type.items() if vs}

    if pchembl_available == 0:
        warnings.append("No pChEMBL values available; activity confidence is lower.")
    non_std_units = [u for u in unit_counts if u not in _UNIT_TO_NM and u != "none"]
    if non_std_units:
        warnings.append(f"Non-standard/unconverted units present: {', '.join(sorted(set(non_std_units)))}.")
    if suspicious:
        warnings.append(f"{suspicious} suspicious activity value(s) (<=0 or absurdly large) excluded from medians.")

    return {
        "source_type": SourceType.REAL_TOOL_OUTPUT.value if activities else SourceType.TOOL_ERROR.value,
        "target_chembl_id": target_chembl_id,
        "activity_count": len(activities), "unique_molecule_count": len(molecules),
        "standard_type_counts": type_counts, "standard_unit_counts": unit_counts,
        "pchembl_available_count": pchembl_available, "relation_counts": relation_counts,
        "suspicious_value_count": suspicious, "median_activity_by_type": median_by_type,
        "preferred_type_fraction": round(
            sum(type_counts.get(t, 0) for t in PREFERRED_TYPES) / max(1, len(activities)), 3),
        "limitations": ["Assay heterogeneity is common in ChEMBL; medians are indicative only.",
                        "Only nM/uM/mM units are safely comparable; others are flagged, not converted."],
        "warnings": warnings,
    }


def activity_proxy(activity: dict) -> dict[str, Any]:
    """Conservative activity proxy in [0,1] with an honest provenance note."""
    pchembl = _num(activity.get("pchembl_value"))
    if pchembl is not None:
        # pChEMBL 5 (10 uM) → ~0.2, pChEMBL 9 (1 nM) → ~1.0.
        return {"score": max(0.0, min(1.0, (pchembl - 4.0) / 5.0)), "basis": "pChEMBL",
                "source_type": SourceType.REAL_TOOL_OUTPUT.value, "warning": ""}
    val = _num(activity.get("standard_value"))
    unit = activity.get("standard_units")
    if val is not None and unit in _UNIT_TO_NM and val > 0:
        nM = val * _UNIT_TO_NM[unit]
        # lower concentration = stronger; map 1nM→~1, 10uM→~0.2 via pseudo-pIC50.
        import math
        p = 9.0 - math.log10(nM)
        return {"score": max(0.0, min(1.0, (p - 4.0) / 5.0)), "basis": f"{unit}→nM",
                "source_type": SourceType.HEURISTIC_ANALYSIS.value, "warning": ""}
    return {"score": 0.4, "basis": "conservative default",
            "source_type": SourceType.ASSUMPTION.value, "warning": "No comparable activity value"}
