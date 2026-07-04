"""Safe, deterministic in-silico candidate generation for the optimization loop.

Two generation strategies, both explicitly labeled and safe:

``resample_and_reweight``
    "Optimization by selection." Deterministically perturbs the molecule scoring
    weights, re-ranks the EXISTING candidate pool under the perturbed weights,
    and returns the top re-ranked candidates as the next generation. No new
    structures are invented — children are re-prioritized existing molecules,
    labeled ``SELECTION_LOOP``.

``local_heuristic_analogs``
    Optional, conservative RDKit analog suggestions. A single small substituent
    (fluorine, chlorine, methyl, or hydroxyl) is added at an existing carbon
    attachment point via robust ``RWMol`` edits, then the structure is
    sanitized and re-validated. Anything that fails validation is discarded. If
    RDKit is unavailable, ``[]`` is returned and the mode is unavailable — no
    junk is ever emitted, and no procedural chemistry text is produced.

Neither strategy fabricates REINVENT4 output. ``reinvent_available`` reports
whether REINVENT4 is configured so the loop can honestly downgrade to a local
strategy.
"""
from __future__ import annotations

import random
from typing import Any

from app.config import get_settings

try:
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover - environment without RDKit
    RDKIT = False


# Base weights for the reweight/re-rank step. Kept local so we never mutate the
# shared scoring weights, and so the loop is self-contained.
_BASE_WEIGHTS: dict[str, float] = {
    "qed_score": 0.30,
    "descriptor_druglikeness_score": 0.25,
    "activity_proxy_score": 0.25,
    "provenance_confidence": 0.20,
}

# Conservative single-atom substituents: (label, atomic number).
_SAFE_FRAGMENTS: list[tuple[str, int]] = [
    ("fluoro", 9),
    ("chloro", 17),
    ("methyl", 6),
    ("hydroxyl", 8),
]

_MAX_ANALOGS = 12


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def reinvent_available() -> bool:
    """Return True only if BOTH REINVENT4 binary and interpreter are configured."""
    settings = get_settings()
    return bool(getattr(settings, "reinvent4_bin", "")) and bool(
        getattr(settings, "reinvent4_python", "")
    )


def _feature_vector(cand: dict[str, Any]) -> dict[str, float]:
    """Derive deterministic 0-1 feature signals from a candidate record."""
    desc = cand.get("descriptors") or {}
    qed = _clamp01(float(desc.get("qed", 0.4) or 0.4))

    mw = float(desc.get("mol_weight", 400) or 400)
    logp = float(desc.get("logp", 3) or 3)
    tpsa = float(desc.get("tpsa", 80) or 80)
    druglikeness = 1.0
    if mw > 500:
        druglikeness -= 0.25
    if logp > 5 or logp < -1:
        druglikeness -= 0.25
    if tpsa > 140:
        druglikeness -= 0.25
    druglikeness = _clamp01(druglikeness)

    pchembl = cand.get("pchembl_value")
    try:
        activity = _clamp01((float(pchembl) - 4.0) / 5.0) if pchembl is not None else 0.4
    except (TypeError, ValueError):
        activity = 0.4

    provenance = _clamp01(float(cand.get("composite_score") or 0.0) / 100.0)

    return {
        "qed_score": qed,
        "descriptor_druglikeness_score": druglikeness,
        "activity_proxy_score": activity,
        "provenance_confidence": provenance,
    }


def resample_and_reweight(candidates: list[dict], seed: int = 0) -> list[dict]:
    """Re-rank the existing pool under deterministically perturbed weights.

    This is optimization-by-selection: no new structures are produced. The
    returned children are existing molecules re-prioritized under perturbed
    weights, each labeled ``SELECTION_LOOP`` and pointing back at its parent.
    """
    if not candidates:
        return []

    rng = random.Random(seed)
    # Deterministic multiplicative perturbation in [0.8, 1.2] per weight.
    perturbed: dict[str, float] = {}
    for key, weight in _BASE_WEIGHTS.items():
        perturbed[key] = max(0.0, weight * (0.8 + 0.4 * rng.random()))
    total = sum(perturbed.values()) or 1.0

    scored: list[tuple[float, str, dict]] = []
    for cand in candidates:
        feats = _feature_vector(cand)
        value = sum(perturbed[k] * feats[k] for k in _BASE_WEIGHTS) / total
        scored.append((value, str(cand.get("id") or ""), cand))

    # Highest reweighted value first; id tiebreak for determinism.
    scored.sort(key=lambda t: (-t[0], t[1]))

    children: list[dict] = []
    for value, _cid, cand in scored:
        smiles = cand.get("canonical_smiles") or cand.get("smiles") or ""
        children.append(
            {
                "id": f"sel-{cand.get('id')}",
                "label": f"selection::{cand.get('label') or cand.get('id')}",
                "smiles": smiles,
                "descriptors": cand.get("descriptors") or {},
                "composite_score": float(cand.get("composite_score") or 0.0),
                "pchembl_value": cand.get("pchembl_value"),
                "reweighted_value": round(value, 4),
                "source_type": "SELECTION_LOOP",
                "parent": cand.get("id"),
            }
        )
    return children


def local_heuristic_analogs(seed_smiles: list[str]) -> list[dict]:
    """Conservative RDKit analog suggestions via single-atom substituent edits.

    Returns a list of ``{smiles, valid, source_type, parent}`` dicts. Every
    structure is sanitized and re-validated; invalid candidates are discarded.
    If RDKit is unavailable this returns ``[]`` (mode unavailable) rather than
    emitting junk. No procedural chemistry text is ever produced.
    """
    if not RDKIT:
        return []

    out: list[dict] = []
    seen: set[str] = set()

    for smi in seed_smiles:
        if len(out) >= _MAX_ANALOGS:
            break
        if not smi:
            continue
        parent_mol = Chem.MolFromSmiles(smi)
        if parent_mol is None:
            continue
        parent_canon = Chem.MolToSmiles(parent_mol)
        seen.add(parent_canon)

        for atom in parent_mol.GetAtoms():
            if len(out) >= _MAX_ANALOGS:
                break
            # Only substitute on carbons that carry at least one implicit H.
            if atom.GetSymbol() != "C" or atom.GetTotalNumHs() < 1:
                continue
            for _label, atomic_num in _SAFE_FRAGMENTS:
                rw = Chem.RWMol(parent_mol)
                new_idx = rw.AddAtom(Chem.Atom(atomic_num))
                rw.AddBond(atom.GetIdx(), new_idx, Chem.BondType.SINGLE)
                try:
                    candidate_mol = rw.GetMol()
                    Chem.SanitizeMol(candidate_mol)
                except Exception:
                    continue
                candidate_smiles = Chem.MolToSmiles(candidate_mol)
                if candidate_smiles in seen:
                    continue
                # Re-validate the emitted SMILES round-trips to a real molecule.
                if Chem.MolFromSmiles(candidate_smiles) is None:
                    continue
                seen.add(candidate_smiles)
                out.append(
                    {
                        "smiles": candidate_smiles,
                        "valid": True,
                        "source_type": "LOCAL_HEURISTIC_GENERATED",
                        "parent": parent_canon,
                    }
                )
                # One substituent per attachment point keeps the set small and
                # conservative.
                break

    return out[:_MAX_ANALOGS]
