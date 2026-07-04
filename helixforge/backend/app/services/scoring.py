"""Deterministic, transparent scoring (Phase 2).

Two scorers, both normalized to 0-100 with the formula and per-input breakdown
returned so the UI and reports can show exactly how a score was produced. Missing
inputs use conservative defaults and emit a warning — never a silent guess. These
are *candidate prioritization* scores, not claims of real efficacy.
"""
from __future__ import annotations

from typing import Any, Optional


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _round(x: float, dp: int = 1) -> float:
    f = 10 ** dp
    return round(x * f) / f


# ---------------------------------------------------------------------------
# Target Opportunity Score
# ---------------------------------------------------------------------------
TARGET_WEIGHTS = {
    "target_name_match": 0.20,
    "target_type_score": 0.15,
    "organism_score": 0.10,
    "chembl_confidence_score": 0.15,
    "pubmed_evidence_score": 0.15,
    "clinical_precedent_score": 0.10,
    "molecule_activity_availability": 0.10,
    "safety_penalty": -0.10,
    "uncertainty_penalty": -0.10,
}


def score_target(inputs: dict[str, Any]) -> dict[str, Any]:
    """Return {score, breakdown, warnings, formula}. Inputs are 0-1 floats."""
    warnings: list[str] = []

    def geti(key: str, default: float) -> float:
        v = inputs.get(key)
        if v is None:
            warnings.append(f"missing '{key}' → conservative default {default}")
            return default
        return _clamp01(float(v))

    vals = {
        "target_name_match": geti("target_name_match", 0.3),
        "target_type_score": geti("target_type_score", 0.4),
        "organism_score": geti("organism_score", 0.4),
        "chembl_confidence_score": geti("chembl_confidence_score", 0.3),
        "pubmed_evidence_score": geti("pubmed_evidence_score", 0.2),
        "clinical_precedent_score": geti("clinical_precedent_score", 0.2),
        "molecule_activity_availability": geti("molecule_activity_availability", 0.2),
        "safety_penalty": geti("safety_penalty", 0.0),
        "uncertainty_penalty": geti("uncertainty_penalty", 0.3),
    }
    raw = sum(TARGET_WEIGHTS[k] * v for k, v in vals.items())
    pos_max = sum(w for w in TARGET_WEIGHTS.values() if w > 0)
    score = _round(_clamp01(raw / pos_max) * 100)
    breakdown = [
        {"input": k, "value": vals[k], "weight": TARGET_WEIGHTS[k],
         "contribution": _round(TARGET_WEIGHTS[k] * vals[k] / pos_max * 100, 2)}
        for k in vals
    ]
    return {
        "score": score,
        "breakdown": breakdown,
        "warnings": warnings,
        "formula": "0.20*name +0.15*type +0.10*organism +0.15*chembl_conf +0.15*pubmed +0.10*clinical +0.10*activity -0.10*safety -0.10*uncertainty (normalized 0-100)",
    }


# ---------------------------------------------------------------------------
# Molecule Composite Score
# ---------------------------------------------------------------------------
MOLECULE_WEIGHTS = {
    "qed_score": 0.20,
    "lipinski_score": 0.15,
    "activity_proxy_score": 0.20,
    "descriptor_druglikeness_score": 0.15,
    "tdc_readiness_score": 0.10,
    "provenance_confidence": 0.10,
    "novelty_or_diversity_proxy": 0.10,
}


def score_molecule(inputs: dict[str, Any]) -> dict[str, Any]:
    """Return {score, recommendation, breakdown, warnings, formula}."""
    warnings: list[str] = []
    valid = bool(inputs.get("rdkit_validity", inputs.get("valid", False)))
    safety_status = str(inputs.get("safety_status", "PASS")).upper()

    if not valid:
        return {
            "score": 0.0,
            "recommendation": "Reject — invalid structure",
            "breakdown": [],
            "warnings": ["invalid SMILES → score forced to 0"],
            "formula": "invalid SMILES ⇒ 0",
        }

    def geti(key: str, default: float) -> float:
        v = inputs.get(key)
        if v is None:
            warnings.append(f"missing '{key}' → conservative default {default}")
            return default
        return _clamp01(float(v))

    # Derive some sub-scores from raw descriptors when provided.
    qed = geti("qed_score", _clamp01(float(inputs.get("qed", 0.4))))
    lip = inputs.get("lipinski_score")
    if lip is None:
        lp = inputs.get("lipinski_pass")
        viol = inputs.get("lipinski_violations")
        if lp is not None:
            lip = 1.0 if lp else max(0.0, 1.0 - 0.25 * (viol or 1))
        else:
            lip = 0.5
            warnings.append("missing 'lipinski_score' → conservative default 0.5")
    lip = _clamp01(float(lip))

    vals = {
        "qed_score": qed,
        "lipinski_score": lip,
        "activity_proxy_score": geti("activity_proxy_score", 0.4),
        "descriptor_druglikeness_score": geti("descriptor_druglikeness_score", 0.5),
        "tdc_readiness_score": geti("tdc_readiness_score", 0.5),
        "provenance_confidence": geti("provenance_confidence", 0.6),
        "novelty_or_diversity_proxy": geti("novelty_or_diversity_proxy", 0.5),
    }
    pos = sum(MOLECULE_WEIGHTS[k] * v for k, v in vals.items())
    pos_max = sum(MOLECULE_WEIGHTS.values())
    base = pos / pos_max * 100

    safety_penalty = {"PASS": 0.0, "REVIEW_REQUIRED": 15.0, "BLOCKED": 100.0}.get(safety_status, 0.0)
    uncertainty_penalty = _clamp01(float(inputs.get("uncertainty", 0.2))) * 12.0
    score = _round(max(0.0, base - safety_penalty - uncertainty_penalty))

    if safety_status == "BLOCKED":
        rec = "Do not advance"
    elif safety_status == "REVIEW_REQUIRED":
        rec = "Review required"
    elif score >= 75:
        rec = "Advance to expert review"
    elif score >= 55:
        rec = "Needs optimization"
    elif score >= 35:
        rec = "Hold pending evidence"
    else:
        rec = "Hold pending evidence"

    breakdown = [
        {"input": k, "value": vals[k], "weight": MOLECULE_WEIGHTS[k],
         "contribution": _round(MOLECULE_WEIGHTS[k] * vals[k] / pos_max * 100, 2)}
        for k in vals
    ]
    breakdown.append({"input": "safety_penalty", "value": safety_status, "weight": None, "contribution": -safety_penalty})
    breakdown.append({"input": "uncertainty_penalty", "value": inputs.get("uncertainty", 0.2), "weight": None, "contribution": -_round(uncertainty_penalty, 2)})

    return {
        "score": score,
        "recommendation": rec,
        "breakdown": breakdown,
        "warnings": warnings,
        "formula": "0.20*qed +0.15*lipinski +0.20*activity +0.15*druglikeness +0.10*tdc +0.10*provenance +0.10*novelty - safety_penalty - uncertainty_penalty",
    }


# ---------------------------------------------------------------------------
# Helpers to derive scorer inputs from real tool outputs
# ---------------------------------------------------------------------------
def target_inputs_from_chembl(
    target: dict[str, Any], query: str, pubmed_count: int, trial_count: int, activity_count: int
) -> dict[str, Any]:
    name = (target.get("pref_name") or "").upper()
    q = query.upper()
    name_match = 1.0 if q == name else (0.75 if q in name else (0.4 if name else 0.2))
    ttype = target.get("target_type", "")
    # Prefer druggable single proteins; penalize protein-protein interactions
    # (which rarely carry small-molecule bioactivity/SMILES).
    type_score = (
        1.0 if ttype == "SINGLE PROTEIN"
        else 0.6 if ttype in ("PROTEIN COMPLEX", "PROTEIN FAMILY")
        else 0.3 if "INTERACTION" in ttype
        else 0.4
    )
    organism = 1.0 if (target.get("organism") == "Homo sapiens") else 0.4
    conf = target.get("target_components") and 0.7 or 0.5
    conf = float(target.get("confidence_score", conf) or conf)
    conf = _clamp01(conf / 9.0) if conf > 1 else _clamp01(conf)
    return {
        "target_name_match": name_match,
        "target_type_score": type_score,
        "organism_score": organism,
        "chembl_confidence_score": conf,
        "pubmed_evidence_score": _clamp01(pubmed_count / 8.0),
        "clinical_precedent_score": _clamp01(trial_count / 5.0),
        "molecule_activity_availability": _clamp01(activity_count / 10.0),
        "safety_penalty": 0.0,
        "uncertainty_penalty": 0.5 if pubmed_count == 0 else 0.2,
    }


def molecule_inputs_from_rdkit(
    rd: dict[str, Any], activity: Optional[dict[str, Any]], safety_status: str, tdc_ready: bool, provenance: float
) -> dict[str, Any]:
    d = (rd or {}).get("descriptors") or {}
    pchembl = None
    if activity:
        pchembl = activity.get("pchembl_value")
    activity_proxy = _clamp01((float(pchembl) - 4.0) / 5.0) if pchembl else 0.4
    # Druglikeness from descriptor sanity.
    mw = d.get("mol_weight", 400) or 400
    logp = d.get("logp", 3) or 3
    tpsa = d.get("tpsa", 80) or 80
    dl = 1.0
    if mw > 500:
        dl -= 0.25
    if logp > 5 or logp < -1:
        dl -= 0.25
    if tpsa > 140:
        dl -= 0.25
    return {
        "rdkit_validity": rd.get("valid", False),
        "valid": rd.get("valid", False),
        "qed": d.get("qed", 0.4),
        "lipinski_pass": d.get("lipinski_pass"),
        "lipinski_violations": d.get("lipinski_violations"),
        "activity_proxy_score": activity_proxy,
        "descriptor_druglikeness_score": _clamp01(dl),
        "tdc_readiness_score": 0.7 if tdc_ready else 0.4,
        "provenance_confidence": provenance,
        "novelty_or_diversity_proxy": 0.5,
        "safety_status": safety_status,
        "uncertainty": 0.2 if rd.get("valid") else 0.5,
    }
