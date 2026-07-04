"""Molecule diversity / scaffold analysis with real RDKit.

Morgan fingerprints, pairwise Tanimoto, exact + near-duplicate detection, and
Bemis-Murcko scaffolds. Degrades gracefully (CONFIGURED_BUT_NOT_RUN) when RDKit
is unavailable — never fabricated.
"""
from __future__ import annotations

from typing import Any

from app.models.schemas import SourceType

try:
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import AllChem
    from rdkit.Chem.Scaffolds import MurckoScaffold
    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover - depends on environment
    RDKIT = False


def rdkit_available() -> bool:
    return RDKIT


def analyze_diversity(smiles_list: list[str], near_dup_threshold: float = 0.85) -> dict[str, Any]:
    if not RDKIT:
        return {"source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
                "available": False, "detail": "RDKit not installed; diversity analysis not run.",
                "warnings": ["RDKit unavailable"]}

    mols, canon, valid_idx, warnings = [], [], [], []
    for i, smi in enumerate(smiles_list):
        m = Chem.MolFromSmiles(smi) if smi else None
        if m is None:
            warnings.append(f"invalid SMILES at index {i}")
            continue
        mols.append(m)
        canon.append(Chem.MolToSmiles(m))
        valid_idx.append(i)

    n = len(mols)
    if n == 0:
        return {"source_type": SourceType.REAL_TOOL_OUTPUT.value, "available": True, "count": 0,
                "warnings": warnings or ["no valid molecules"], "diversity_score": None,
                "duplicates": [], "near_duplicates": [], "scaffolds": [], "nearest_neighbors": []}

    fps = [AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=1024) for m in mols]

    # Exact duplicates by canonical SMILES.
    seen: dict[str, list[int]] = {}
    for k, c in enumerate(canon):
        seen.setdefault(c, []).append(valid_idx[k])
    duplicates = [{"canonical_smiles": c, "indices": idxs} for c, idxs in seen.items() if len(idxs) > 1]

    # Pairwise Tanimoto → near-duplicates + nearest neighbours + diversity.
    near_dups, sims_all = [], []
    nearest = [{"index": valid_idx[i], "nn_index": None, "similarity": 0.0} for i in range(n)]
    for i in range(n):
        best_j, best_s = None, -1.0
        for j in range(n):
            if i == j:
                continue
            s = DataStructs.TanimotoSimilarity(fps[i], fps[j])
            if i < j:
                sims_all.append(s)
                if s >= near_dup_threshold:
                    near_dups.append({"a": valid_idx[i], "b": valid_idx[j], "similarity": round(s, 3)})
            if s > best_s:
                best_s, best_j = s, valid_idx[j]
        nearest[i] = {"index": valid_idx[i], "nn_index": best_j, "similarity": round(best_s, 3)}

    mean_sim = sum(sims_all) / len(sims_all) if sims_all else 0.0
    diversity_score = round(1.0 - mean_sim, 3)

    # Bemis-Murcko scaffolds.
    scaf_counts: dict[str, int] = {}
    for m in mols:
        try:
            scaf = MurckoScaffold.MurckoScaffoldSmiles(mol=m)
        except Exception:
            scaf = ""
        scaf_counts[scaf] = scaf_counts.get(scaf, 0) + 1
    scaffolds = sorted(
        [{"scaffold": s or "(acyclic)", "count": c} for s, c in scaf_counts.items()],
        key=lambda x: x["count"], reverse=True)

    return {
        "source_type": SourceType.REAL_TOOL_OUTPUT.value, "available": True, "count": n,
        "diversity_score": diversity_score, "mean_pairwise_similarity": round(mean_sim, 3),
        "duplicates": duplicates, "near_duplicate_threshold": near_dup_threshold,
        "near_duplicates": near_dups, "scaffold_count": len(scaf_counts),
        "scaffolds": scaffolds[:20], "nearest_neighbors": nearest, "warnings": warnings,
    }
