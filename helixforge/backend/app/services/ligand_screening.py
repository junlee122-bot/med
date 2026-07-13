"""CPU ligand-based virtual screening (Phase 8, Section 10).

Without GPU docking, provide a useful, honest ligand-based screen: Morgan/Tanimoto
similarity to known reference ligands, scaffold overlap, property-window filtering,
duplicate filtering, and applicability domain. This is a SCREENING SIGNAL, never
binding proof. No fabricated docking score.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import SourceType, utcnow
from app.services import chem_utils as cu
from app.storage import db

# Property window (drug-like) for a light filter — reused from Lipinski/Veber ranges.
PROP_WINDOW = {"mol_weight": (150, 550), "logp": (-0.5, 5.5), "hbd": (0, 5), "hba": (0, 10), "tpsa": (0, 140)}

SIM_KNOWN_LIKE = 0.7   # >= => known-like
SIM_OUT_OF_DOMAIN = 0.2  # nearest ref below this => out of domain


def _property_ok(desc: dict[str, float] | None) -> bool:
    if not desc:
        return False
    for k, (lo, hi) in PROP_WINDOW.items():
        v = desc.get(k)
        if v is None or v < lo or v > hi:
            return False
    return True


def _recommendation(nearest: float, valid: bool, duplicate: bool, prop_ok: bool,
                    safety_ok: bool) -> str:
    if not valid:
        return "REJECT_INVALID"
    if not safety_ok:
        return "SAFETY_BLOCKED"
    if duplicate:
        return "DUPLICATE"
    if nearest >= SIM_KNOWN_LIKE:
        return "KNOWN_LIKE_PRIORITY"
    if nearest < SIM_OUT_OF_DOMAIN:
        return "OUT_OF_DOMAIN"
    if prop_ok:
        return "DIVERSE_EXPLORATION"
    return "BORDERLINE"


def screen(candidates: list[str], reference_ligands: list[str], top_k: int = 10,
           run_id: str | None = None, target: str | None = None,
           project_id: str | None = None) -> dict[str, Any]:
    """Screen candidate SMILES against known reference ligand SMILES."""
    if not cu.rdkit_available():
        return {"status": "UNAVAILABLE", "reason": "RDKit not available", "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
                "checked_at": utcnow()}
    ref_fps = [fp for fp in (cu.morgan_fp(s) for s in reference_ligands) if fp is not None]
    ref_scaffolds = {cu.murcko_scaffold(s) for s in reference_ligands if cu.murcko_scaffold(s)}
    seen_canon: set[str] = set()

    results: list[dict[str, Any]] = []
    valid_count = 0
    dup_count = 0
    for smi in candidates:
        canon = cu.canonical_smiles(smi)
        valid = canon is not None
        if valid:
            valid_count += 1
        duplicate = bool(canon and canon in seen_canon)
        if canon:
            if duplicate:
                dup_count += 1
            seen_canon.add(canon)
        fp = cu.morgan_fp(smi)
        sims = cu.bulk_tanimoto(fp, ref_fps) if fp is not None else []
        nearest = max(sims) if sims else 0.0
        top = sorted(sims, reverse=True)[:5]
        scaf = cu.murcko_scaffold(smi)
        scaffold_match = bool(scaf and scaf in ref_scaffolds)
        desc = cu.descriptors(smi)
        prop_ok = _property_ok(desc)
        # Deterministic safety proxy: valid structure + within property window is OK;
        # the real safety gate runs downstream. Here we only reject clearly invalid.
        safety_ok = valid
        rec = _recommendation(nearest, valid, duplicate, prop_ok, safety_ok)
        results.append({
            "smiles": smi, "canonical_smiles": canon, "valid": valid,
            "nearest_reference_similarity": round(nearest, 4),
            "top_similarities": [round(x, 4) for x in top],
            "scaffold": scaf, "scaffold_match_known": scaffold_match,
            "property_window_ok": prop_ok, "descriptors": desc,
            "applicability": ("IN_DOMAIN" if nearest >= SIM_KNOWN_LIKE else
                              "BORDERLINE" if nearest >= SIM_OUT_OF_DOMAIN else "OUT_OF_DOMAIN"),
            "duplicate": duplicate, "recommendation": rec,
        })
    results.sort(key=lambda r: r["nearest_reference_similarity"], reverse=True)
    top_candidates = results[:top_k]
    role_counts: dict[str, int] = {}
    for r in results:
        role_counts[r["recommendation"]] = role_counts.get(r["recommendation"], 0) + 1

    out = {
        "id": f"lscreen-{uuid.uuid4().hex[:8]}", "project_id": project_id,
        "run_id": run_id, "workflow_run_id": run_id, "target": target,
        "candidate_count": len(candidates), "valid_count": valid_count, "duplicate_count": dup_count,
        "reference_count": len(reference_ligands), "reference_scaffold_count": len(ref_scaffolds),
        "top_candidates": top_candidates, "recommendation_counts": role_counts,
        "best_similarity": round(max((r["nearest_reference_similarity"] for r in results), default=0.0), 4),
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
        "banner": "Ligand-based screening is a prioritization signal — NOT a docking result and NOT binding proof.",
        "limitations": ["2D similarity only; no 3D pose or binding energy.",
                        "Similarity to known actives can miss novel chemotypes.",
                        "Not a substitute for experimental validation."],
        "created_at": utcnow(),
    }
    db.insert("ligand_screens", out)
    return out


def get_screen(screen_id: str) -> dict[str, Any] | None:
    return db.get("ligand_screens", screen_id)
