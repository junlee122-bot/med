"""Shared CPU cheminformatics helpers (RDKit). Fingerprints, scaffolds, descriptors,
validity, and Bemis-Murcko scaffolds — used by ligand screening, CPU QSAR, dataset
curation, active learning, and multi-objective search. RDKit-optional: callers get
None / False cleanly if RDKit is unavailable (no crash, no fabrication)."""
from __future__ import annotations

from typing import Any, Optional

try:  # RDKit is a normal dependency here but we degrade rather than crash.
    from rdkit import Chem, DataStructs
    from rdkit.Chem import AllChem, Descriptors
    from rdkit.Chem.Scaffolds import MurckoScaffold
    _RDKIT = True
except Exception:  # pragma: no cover - exercised only when RDKit missing
    _RDKIT = False


def rdkit_available() -> bool:
    return _RDKIT


def mol_from_smiles(smiles: str):
    if not _RDKIT or not smiles:
        return None
    try:
        return Chem.MolFromSmiles(smiles)
    except Exception:
        return None


def canonical_smiles(smiles: str) -> Optional[str]:
    m = mol_from_smiles(smiles)
    return Chem.MolToSmiles(m) if m is not None else None


def is_valid(smiles: str) -> bool:
    return mol_from_smiles(smiles) is not None


def morgan_fp(smiles: str, radius: int = 2, n_bits: int = 1024):
    m = mol_from_smiles(smiles)
    if m is None:
        return None
    try:
        return AllChem.GetMorganFingerprintAsBitVect(m, radius, nBits=n_bits)
    except Exception:
        return None


def tanimoto(fp_a, fp_b) -> Optional[float]:
    if fp_a is None or fp_b is None:
        return None
    try:
        return float(DataStructs.TanimotoSimilarity(fp_a, fp_b))
    except Exception:
        return None


def bulk_tanimoto(query_fp, ref_fps: list) -> list[float]:
    if not _RDKIT or query_fp is None or not ref_fps:
        return []
    try:
        return [float(x) for x in DataStructs.BulkTanimotoSimilarity(query_fp, ref_fps)]
    except Exception:
        return []


def murcko_scaffold(smiles: str) -> Optional[str]:
    m = mol_from_smiles(smiles)
    if m is None:
        return None
    try:
        scaf = MurckoScaffold.GetScaffoldForMol(m)
        return Chem.MolToSmiles(scaf) if scaf is not None else None
    except Exception:
        return None


def descriptors(smiles: str) -> Optional[dict[str, float]]:
    m = mol_from_smiles(smiles)
    if m is None:
        return None
    try:
        return {
            "mol_weight": round(Descriptors.MolWt(m), 2),
            "logp": round(Descriptors.MolLogP(m), 3),
            "hbd": int(Descriptors.NumHDonors(m)),
            "hba": int(Descriptors.NumHAcceptors(m)),
            "tpsa": round(Descriptors.TPSA(m), 2),
            "rotatable_bonds": int(Descriptors.NumRotatableBonds(m)),
            "qed": round(_qed(m), 3),
            "heavy_atoms": int(m.GetNumHeavyAtoms()),
        }
    except Exception:
        return None


def _qed(m) -> float:
    try:
        from rdkit.Chem import QED
        return float(QED.qed(m))
    except Exception:
        return 0.0


def feature_vector(smiles: str, n_bits: int = 1024) -> Optional[list[int]]:
    """Morgan bit vector as a plain python list (for scikit-learn feature matrices)."""
    fp = morgan_fp(smiles, n_bits=n_bits)
    if fp is None:
        return None
    return list(fp)


def dedupe_by_canonical(smiles_list: list[str]) -> dict[str, Any]:
    """Return {unique, duplicates, invalid} counts and the unique canonical set."""
    seen: dict[str, str] = {}
    invalid, dup = 0, 0
    for s in smiles_list:
        c = canonical_smiles(s)
        if c is None:
            invalid += 1
            continue
        if c in seen:
            dup += 1
        else:
            seen[c] = s
    return {"unique_canonical": list(seen.keys()), "unique_count": len(seen),
            "duplicate_count": dup, "invalid_count": invalid}
