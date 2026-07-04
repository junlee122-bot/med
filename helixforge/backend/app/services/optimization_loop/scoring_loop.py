"""Per-candidate scoring and a lightweight Pareto front for the loop.

``score_candidate`` computes RDKit descriptors (when needed), assesses the
applicability domain against a reference set, and calls the shared, transparent
molecule scorer. ``pareto_front`` selects the non-dominated set over
``(score, applicability confidence, -uncertainty)`` so the loop can report a
trade-off front rather than a single collapsed number.
"""
from __future__ import annotations

from typing import Any

from app.services import applicability_domain
from app.services.scoring import molecule_inputs_from_rdkit, score_molecule

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import Descriptors, QED

    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover - environment without RDKit
    RDKIT = False


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_descriptors(smiles: str) -> dict[str, Any]:
    """Compute the standard descriptor block from a SMILES (RDKit)."""
    if not RDKIT or not smiles:
        return {}
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {}
    return {
        "mol_weight": round(Descriptors.MolWt(mol), 3),
        "logp": round(Descriptors.MolLogP(mol), 3),
        "hbd": int(Descriptors.NumHDonors(mol)),
        "hba": int(Descriptors.NumHAcceptors(mol)),
        "tpsa": round(Descriptors.TPSA(mol), 3),
        "qed": round(QED.qed(mol), 3),
    }


def score_candidate(cand: dict, reference_smiles: list[str]) -> dict[str, Any]:
    """Score one candidate: descriptors + applicability domain + composite score.

    Returns
    -------
    dict
        ``{smiles, score, recommendation, applicability_status, warnings, ...}``.
        Also carries ``applicability_confidence`` and ``uncertainty`` so the
        Pareto front can reason over the trade-off axes.
    """
    smiles = cand.get("canonical_smiles") or cand.get("smiles") or ""
    warnings: list[str] = []

    descriptors = cand.get("descriptors") or {}
    if not descriptors and smiles:
        descriptors = compute_descriptors(smiles)

    # Applicability domain against the run's reference set.
    assessment = applicability_domain.assess_molecule(smiles, reference_smiles or [])
    applicability_status = assessment.get("domain_status", "UNKNOWN")
    conf_adjust = float(assessment.get("confidence_adjustment", -0.15) or 0.0)
    applicability_confidence = round(_clamp01(1.0 + conf_adjust), 3)
    warnings.extend(assessment.get("warnings", []) or [])

    # Derive scorer inputs from descriptors; out-of-domain lowers confidence by
    # raising uncertainty.
    rd = {"valid": bool(smiles) and RDKIT, "descriptors": descriptors}
    if not RDKIT:
        rd["valid"] = bool(descriptors)
    activity = (
        {"pchembl_value": cand.get("pchembl_value")}
        if cand.get("pchembl_value") is not None
        else None
    )
    provenance = _clamp01(float(cand.get("composite_score") or 0.0) / 100.0) or 0.5
    inputs = molecule_inputs_from_rdkit(
        rd, activity, safety_status="PASS", tdc_ready=False, provenance=provenance
    )
    uncertainty = round(_clamp01(0.2 - conf_adjust), 3)
    inputs["uncertainty"] = uncertainty

    result = score_molecule(inputs)
    warnings.extend(result.get("warnings", []) or [])

    return {
        "id": cand.get("id"),
        "label": cand.get("label"),
        "smiles": smiles,
        "score": result.get("score", 0.0),
        "recommendation": result.get("recommendation", ""),
        "applicability_status": applicability_status,
        "applicability_confidence": applicability_confidence,
        "uncertainty": uncertainty,
        "source_type": cand.get("source_type"),
        "parent": cand.get("parent"),
        "warnings": warnings,
    }


def _dominates(a: dict, b: dict) -> bool:
    """True if ``a`` Pareto-dominates ``b`` over (score, app confidence, -uncertainty)."""
    a_axes = (
        float(a.get("score", 0.0)),
        float(a.get("applicability_confidence", 0.0)),
        -float(a.get("uncertainty", 1.0)),
    )
    b_axes = (
        float(b.get("score", 0.0)),
        float(b.get("applicability_confidence", 0.0)),
        -float(b.get("uncertainty", 1.0)),
    )
    at_least_as_good = all(x >= y for x, y in zip(a_axes, b_axes))
    strictly_better = any(x > y for x, y in zip(a_axes, b_axes))
    return at_least_as_good and strictly_better


def pareto_front(scored: list[dict]) -> list[dict]:
    """Return the non-dominated set over (score, app confidence, -uncertainty)."""
    front: list[dict] = []
    for i, cand in enumerate(scored):
        dominated = any(
            j != i and _dominates(other, cand) for j, other in enumerate(scored)
        )
        if not dominated:
            front.append(cand)
    # Deterministic ordering: best score first, then id.
    front.sort(key=lambda c: (-float(c.get("score", 0.0)), str(c.get("id") or "")))
    return front
