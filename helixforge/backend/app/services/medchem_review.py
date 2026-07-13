"""Medicinal chemistry review — deterministic, non-actionable, honest.

Runs drug-likeness (Lipinski/Veber/lead-likeness) and structural-alert screens
(PAINS + a small set of non-actionable reactive-group SMARTS) on candidate
molecules using real RDKit. Degrades gracefully when RDKit or the PAINS catalog
is unavailable (labeled, not faked). Emits an expert recommendation, never a
synthesis route, dosage, or medical claim.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import SourceType, utcnow
from app.storage import db

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem import Descriptors, Lipinski
    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover
    RDKIT = False

try:
    from rdkit.Chem import FilterCatalog
    from rdkit.Chem.FilterCatalog import FilterCatalogParams
    _PAINS_PARAMS = FilterCatalogParams()
    _PAINS_PARAMS.AddCatalog(FilterCatalogParams.FilterCatalogs.PAINS)
    _PAINS_CATALOG = FilterCatalog.FilterCatalog(_PAINS_PARAMS)
    PAINS = True
except Exception:  # pragma: no cover
    PAINS = False

# Small set of non-actionable reactive/undesirable group SMARTS (structural
# alerts only — these are recognition patterns, never synthesis guidance).
_ALERT_SMARTS = [
    ("acyl_halide", "[CX3](=O)[F,Cl,Br,I]"),
    ("michael_acceptor", "[CX3]=[CX3][CX3]=O"),
    ("aldehyde", "[CX3H1](=O)[#6]"),
    ("nitro", "[NX3](=O)=O"),
    ("epoxide", "C1OC1"),
    ("isocyanate", "N=C=O"),
    ("thiol", "[#16X2H]"),
]


def _compiled_alerts():
    if not RDKIT:
        return []
    out = []
    for name, smarts in _ALERT_SMARTS:
        patt = Chem.MolFromSmarts(smarts)
        if patt is not None:
            out.append((name, patt))
    return out


_ALERTS = _compiled_alerts()


def review_molecule(smiles: str, label: str | None = None) -> dict[str, Any]:
    if not RDKIT:
        return {"smiles": smiles, "label": label, "rdkit_valid": None,
                "medchem_status": "LOW_CONFIDENCE", "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
                "warnings": ["RDKit unavailable — medchem review not run"],
                "expert_recommendation": "Install RDKit to run medicinal-chemistry review.", "confidence": 0.2}
    mol = Chem.MolFromSmiles(smiles) if smiles else None
    if mol is None:
        return {"smiles": smiles, "label": label, "rdkit_valid": False,
                "medchem_status": "REJECT_INVALID", "source_type": SourceType.REAL_TOOL_OUTPUT.value,
                "warnings": ["invalid SMILES"], "expert_recommendation": "Reject — structure could not be parsed.",
                "confidence": 0.9}

    mw = round(Descriptors.MolWt(mol), 2)
    logp = round(Descriptors.MolLogP(mol), 2)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)
    tpsa = round(Descriptors.TPSA(mol), 2)
    rot = Descriptors.NumRotatableBonds(mol)
    rings = Descriptors.RingCount(mol)
    try:
        qed = round(Descriptors.qed(mol), 3)
    except Exception:
        qed = None

    # Lipinski Ro5 (≤1 violation acceptable).
    lip_v = sum([mw > 500, logp > 5, hbd > 5, hba > 10])
    lipinski = {"violations": lip_v, "pass": lip_v <= 1,
                "detail": f"MW={mw}, cLogP={logp}, HBD={hbd}, HBA={hba}"}
    # Veber: rotatable bonds ≤10 and TPSA ≤140.
    veber = {"pass": rot <= 10 and tpsa <= 140, "rotatable_bonds": rot, "tpsa": tpsa}
    # Lead-likeness (stricter ranges).
    lead = {"pass": (250 <= mw <= 350) and (logp <= 3.5) and (hbd <= 3) and (hba <= 7),
            "detail": "MW 250-350, cLogP ≤3.5, HBD ≤3, HBA ≤7"}

    # Structural alerts.
    pains_alerts: list[str] = []
    if PAINS:
        entry = _PAINS_CATALOG.GetFirstMatch(mol)
        if entry is not None:
            pains_alerts.append(entry.GetDescription())
        pains_status = SourceType.REAL_TOOL_OUTPUT.value
    else:
        pains_status = SourceType.CONFIGURED_BUT_NOT_RUN.value
    reactive_alerts = [name for name, patt in _ALERTS if mol.HasSubstructMatch(patt)]

    warnings: list[str] = []
    if not lipinski["pass"]:
        warnings.append(f"Lipinski Ro5: {lip_v} violations")
    if not veber["pass"]:
        warnings.append("Veber flags (rotatable bonds / TPSA)")
    if pains_alerts:
        warnings.append(f"PAINS alert: {pains_alerts[0]}")
    if reactive_alerts:
        warnings.append(f"reactive/undesirable group(s): {', '.join(reactive_alerts)}")
    if not PAINS:
        warnings.append("PAINS catalog unavailable — structural-alert screen incomplete")

    if pains_alerts or reactive_alerts:
        status = "STRUCTURAL_ALERT_REVIEW"
        rec = "Flag for medicinal-chemistry review — structural alert present."
        conf = 0.7
    elif lipinski["pass"] and veber["pass"]:
        status = "FAVORABLE_FOR_REVIEW" if lead["pass"] else "NEEDS_OPTIMIZATION"
        rec = ("Favorable drug-like profile — advance to expert review."
               if lead["pass"] else "Drug-like but not lead-like — optimization candidate.")
        conf = 0.75
    else:
        status = "NEEDS_OPTIMIZATION"
        rec = "Property flags present — optimization needed before prioritization."
        conf = 0.65

    return {
        "smiles": smiles, "label": label, "canonical_smiles": Chem.MolToSmiles(mol),
        "rdkit_valid": True,
        "descriptor_summary": {"mol_weight": mw, "logp": logp, "hbd": hbd, "hba": hba,
                               "tpsa": tpsa, "rotatable_bonds": rot, "rings": rings, "qed": qed},
        "druglikeness_review": {"qed": qed, "note": "QED 0..1 (higher = more drug-like)"},
        "lipinski_review": lipinski, "veber_review": veber, "lead_likeness_review": lead,
        "structural_alerts": {"pains": pains_alerts, "reactive_groups": reactive_alerts,
                              "pains_screen_status": pains_status},
        "pains_alerts": pains_alerts, "reactive_group_alerts": reactive_alerts,
        "aggregation_risk_note": "Aggregation risk not experimentally assessed (in-silico only).",
        "promiscuity_risk_note": "Promiscuity inferred only from PAINS/alerts, not assay panels.",
        "synthetic_feasibility_note": "Synthetic feasibility not computed here; no synthesis guidance provided.",
        "novelty_diversity_note": "See molecule diversity/applicability-domain analysis.",
        "activity_reliability_note": "See activity normalization for assay reliability.",
        "admet_readiness_note": "ADMET is a baseline/eval substrate — not a safety determination.",
        "medchem_status": status, "expert_recommendation": rec, "confidence": conf,
        "warnings": warnings, "source_type": SourceType.REAL_TOOL_OUTPUT.value,
    }


def review_run(run_id: str | None = None) -> dict[str, Any]:
    runs = db.list_records("workflow_runs", limit=200)
    run = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    if run_id and not run:
        raise ValueError("workflow run not found")
    pid = run.get("project_id") if run else None
    rid = run.get("id") if run else None
    mols = (db.list_records("molecule_candidates", project_id=pid, workflow_run_id=rid, limit=500)
            if pid and rid else [])
    reviews = []
    for m in mols:
        r = review_molecule(m.get("canonical_smiles") or m.get("smiles"),
                            m.get("label") or m.get("molecule_chembl_id"))
        r["molecule_id"] = m.get("id")
        reviews.append(r)
    dist: dict[str, int] = {}
    for r in reviews:
        dist[r["medchem_status"]] = dist.get(r["medchem_status"], 0) + 1
    payload = {"id": f"medchem-{uuid.uuid4().hex[:8]}", "project_id": pid,
               "run_id": rid, "workflow_run_id": rid,
               "reviews": reviews, "count": len(reviews), "status_distribution": dist,
               "rdkit_available": RDKIT, "pains_available": PAINS,
               "disclaimer": "Structural/property review only — no synthesis, dosage, or safety determination.",
               "checked_at": utcnow(), "created_at": utcnow()}
    try:
        db.insert("medchem_reviews", payload)
    except Exception:
        pass
    return payload
