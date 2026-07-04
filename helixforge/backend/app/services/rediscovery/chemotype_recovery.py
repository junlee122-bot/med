"""Chemotype recovery metrics against a set of public reference comparators.

Given a list of candidate SMILES from the pipeline and a comparator set (from
``comparator_library``), these functions quantify how strongly the candidates
*retrospectively recover* known drug chemotypes for a target:

* exact matches (canonical SMILES or InChIKey identity),
* Tanimoto (Morgan-fingerprint) similarity recovery, hit@k, MRR, recall@k,
* Bemis-Murcko scaffold overlap,
* the nearest comparator + qualitative role for a single candidate.

SAFETY: This is a retrospective SANITY CHECK against known drug classes. High
similarity means "looks like a known chemotype", NOT that anything was
discovered, is efficacious, or is safe. Everything degrades gracefully when
RDKit is unavailable (``RDKIT`` flag) rather than fabricating numbers.
"""
from __future__ import annotations

from typing import Any, Optional

try:
    from rdkit import Chem, DataStructs, RDLogger
    from rdkit.Chem import AllChem
    from rdkit.Chem.Scaffolds import MurckoScaffold

    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover - depends on environment
    RDKIT = False


# ---------------------------------------------------------------------------
# Low-level RDKit helpers (all None-safe)
# ---------------------------------------------------------------------------
def _mol(smiles: str):
    if not RDKIT or not smiles:
        return None
    try:
        return Chem.MolFromSmiles(smiles)
    except Exception:
        return None


def _canonical(smiles: str) -> Optional[str]:
    m = _mol(smiles)
    return Chem.MolToSmiles(m) if m is not None else None


def _inchikey(smiles: str) -> Optional[str]:
    m = _mol(smiles)
    if m is None:
        return None
    try:
        return Chem.MolToInchiKey(m)
    except Exception:
        return None


def _fingerprint(smiles: str):
    m = _mol(smiles)
    if m is None:
        return None
    try:
        return AllChem.GetMorganFingerprintAsBitVect(m, 2, nBits=2048)
    except Exception:
        return None


def _scaffold(smiles: str) -> Optional[str]:
    if not RDKIT or not smiles:
        return None
    try:
        scaf = MurckoScaffold.MurckoScaffoldSmiles(smiles=smiles)
    except Exception:
        return None
    return scaf or None


def _tanimoto(fp_a, fp_b) -> float:
    if fp_a is None or fp_b is None:
        return 0.0
    return float(DataStructs.TanimotoSimilarity(fp_a, fp_b))


# ---------------------------------------------------------------------------
# Exact matches
# ---------------------------------------------------------------------------
def exact_matches(
    candidate_smiles: list[str], comparators: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Return exact candidate<->comparator matches by canonical SMILES OR InChIKey.

    Each hit is ``{"candidate": <smiles>, "comparator_name": <name>}``. Without
    RDKit we fall back to raw-string equality so behavior stays deterministic.
    """
    hits: list[dict[str, Any]] = []
    if not comparators:
        return hits

    # Build comparator lookup indexes.
    comp_index: list[dict[str, Any]] = []
    for comp in comparators:
        smi = comp.get("smiles", "")
        comp_index.append(
            {
                "name": comp.get("name", ""),
                "canonical": _canonical(smi) if RDKIT else smi,
                "inchikey": _inchikey(smi) if RDKIT else None,
                "raw": smi,
            }
        )

    for cand in candidate_smiles:
        cand_canon = _canonical(cand) if RDKIT else cand
        cand_key = _inchikey(cand) if RDKIT else None
        for comp in comp_index:
            same_canon = (
                cand_canon is not None and cand_canon == comp["canonical"]
            )
            same_key = (
                cand_key is not None
                and comp["inchikey"] is not None
                and cand_key == comp["inchikey"]
            )
            raw_equal = (not RDKIT) and cand == comp["raw"]
            if same_canon or same_key or raw_equal:
                hits.append({"candidate": cand, "comparator_name": comp["name"]})
                break
    return hits


# ---------------------------------------------------------------------------
# Similarity recovery
# ---------------------------------------------------------------------------
def similarity_recovery(
    candidate_smiles: list[str],
    comparators: list[dict[str, Any]],
    scores: Optional[list[float]] = None,
    k_list: tuple[int, ...] = (1, 5, 10),
    sim_threshold: float = 0.7,
) -> dict[str, Any]:
    """Tanimoto-based recovery of comparator chemotypes by the candidate set.

    For every candidate the maximum Tanimoto to any comparator is computed
    (its "nearest comparator"). Returns:

    * ``best_similarity`` — best candidate->comparator similarity overall,
    * ``per_candidate`` — nearest comparator + similarity for each candidate,
    * ``hit_at_k`` — for each k, True if any candidate whose nearest-comparator
      similarity >= ``sim_threshold`` falls within the top-k candidates ranked
      by their own composite score,
    * ``mean_reciprocal_rank`` — mean over comparators of 1/rank of the first
      candidate (score-ranked) that recovers that comparator,
    * ``recall_at_k`` — fraction of comparators recovered by the top-k
      score-ranked candidates.

    ``scores`` (parallel to ``candidate_smiles``) drives the ranking; when
    absent, candidates are ranked in their given order.
    """
    n = len(candidate_smiles)
    k_list = tuple(sorted(set(int(k) for k in k_list)))
    warnings: list[str] = []

    if not RDKIT:
        warnings.append("RDKit unavailable; similarity recovery not computed.")
    if n == 0:
        warnings.append("no candidates supplied")
    if not comparators:
        warnings.append("no comparators supplied")

    if not RDKIT or n == 0 or not comparators:
        return {
            "available": False,
            "best_similarity": 0.0,
            "similarity_threshold": sim_threshold,
            "per_candidate": [],
            "hit_at_k": {k: False for k in k_list},
            "mean_reciprocal_rank": 0.0,
            "recall_at_k": {k: 0.0 for k in k_list},
            "warnings": warnings,
        }

    comp_fps = [(_c.get("name", ""), _fingerprint(_c.get("smiles", ""))) for _c in comparators]
    cand_fps = [_fingerprint(s) for s in candidate_smiles]

    # Per-candidate nearest comparator (max Tanimoto).
    per_candidate: list[dict[str, Any]] = []
    nearest_sims: list[float] = []
    # sim_matrix[i][j] = similarity of candidate i to comparator j
    sim_matrix: list[list[float]] = []
    for i, cfp in enumerate(cand_fps):
        row = [_tanimoto(cfp, cmp_fp) for _, cmp_fp in comp_fps]
        sim_matrix.append(row)
        if row:
            best_j = max(range(len(row)), key=lambda j: row[j])
            best_s = row[best_j]
            best_name = comp_fps[best_j][0]
        else:
            best_s, best_name = 0.0, ""
        nearest_sims.append(best_s)
        per_candidate.append(
            {
                "candidate": candidate_smiles[i],
                "nearest_comparator": best_name,
                "similarity": round(best_s, 4),
            }
        )

    best_similarity = round(max(nearest_sims), 4) if nearest_sims else 0.0

    # Rank candidate indices by composite score (desc); stable fallback = order.
    if scores is not None and len(scores) == n:
        order = sorted(range(n), key=lambda i: (-(scores[i] if scores[i] is not None else 0.0), i))
    else:
        order = list(range(n))

    # hit@k: is a >=threshold candidate within the top-k by score?
    hit_at_k: dict[int, bool] = {}
    for k in k_list:
        topk = order[:k]
        hit_at_k[k] = any(nearest_sims[i] >= sim_threshold for i in topk)

    # recall@k: fraction of comparators recovered by top-k score-ranked candidates.
    n_comp = len(comparators)
    recall_at_k: dict[int, float] = {}
    for k in k_list:
        topk = order[:k]
        recovered = set()
        for j in range(n_comp):
            if any(sim_matrix[i][j] >= sim_threshold for i in topk):
                recovered.add(j)
        recall_at_k[k] = round(len(recovered) / n_comp, 4) if n_comp else 0.0

    # MRR over comparators: rank candidates by score, first recovering candidate.
    rr_sum = 0.0
    for j in range(n_comp):
        rr = 0.0
        for rank, i in enumerate(order, start=1):
            if sim_matrix[i][j] >= sim_threshold:
                rr = 1.0 / rank
                break
        rr_sum += rr
    mean_reciprocal_rank = round(rr_sum / n_comp, 4) if n_comp else 0.0

    return {
        "available": True,
        "best_similarity": best_similarity,
        "similarity_threshold": sim_threshold,
        "per_candidate": per_candidate,
        "hit_at_k": hit_at_k,
        "mean_reciprocal_rank": mean_reciprocal_rank,
        "recall_at_k": recall_at_k,
        "warnings": warnings,
    }


# ---------------------------------------------------------------------------
# Scaffold recovery
# ---------------------------------------------------------------------------
def scaffold_recovery(
    candidate_smiles: list[str], comparators: list[dict[str, Any]]
) -> dict[str, Any]:
    """Bemis-Murcko scaffold overlap between candidates and comparators.

    ``scaffold_recovery_rate`` = fraction of distinct comparator scaffolds that
    are matched by at least one candidate scaffold.
    """
    if not RDKIT or not comparators or not candidate_smiles:
        return {
            "available": False,
            "scaffold_recovery_rate": 0.0,
            "matched_scaffolds": [],
            "matched_count": 0,
            "comparator_scaffold_count": 0,
            "candidate_scaffold_count": 0,
            "warnings": ["RDKit unavailable or empty input"],
        }

    cand_scaffolds = {s for s in (_scaffold(c) for c in candidate_smiles) if s}
    comp_scaffolds: dict[str, str] = {}
    for comp in comparators:
        scaf = _scaffold(comp.get("smiles", ""))
        if scaf:
            comp_scaffolds.setdefault(scaf, comp.get("name", ""))

    matched = [scaf for scaf in comp_scaffolds if scaf in cand_scaffolds]
    n_comp_scaf = len(comp_scaffolds)
    rate = round(len(matched) / n_comp_scaf, 4) if n_comp_scaf else 0.0

    return {
        "available": True,
        "scaffold_recovery_rate": rate,
        "matched_scaffolds": [
            {"scaffold": scaf, "comparator_name": comp_scaffolds[scaf]} for scaf in matched
        ],
        "matched_count": len(matched),
        "comparator_scaffold_count": n_comp_scaf,
        "candidate_scaffold_count": len(cand_scaffolds),
        "warnings": [],
    }


# ---------------------------------------------------------------------------
# Nearest comparator (single candidate)
# ---------------------------------------------------------------------------
def _role_for(similarity: float) -> str:
    if similarity >= 0.7:
        return "known-like"
    if similarity >= 0.4:
        return "novel-ish"
    return "unrelated"


def nearest_comparator(
    candidate_smi: str, comparators: list[dict[str, Any]]
) -> dict[str, Any]:
    """Nearest comparator to a single candidate + a qualitative role label.

    role: "known-like" (sim>=0.7), "novel-ish" (0.4<=sim<0.7),
    "unrelated" (sim<0.4), or "insufficient_data" (no RDKit / no comparators /
    unparseable candidate).
    """
    if not RDKIT or not comparators or _fingerprint(candidate_smi) is None:
        return {
            "name": None,
            "similarity": None,
            "scaffold_match": False,
            "role": "insufficient_data",
        }

    cand_fp = _fingerprint(candidate_smi)
    cand_scaf = _scaffold(candidate_smi)

    best_name, best_sim = None, -1.0
    best_scaf_match = False
    for comp in comparators:
        smi = comp.get("smiles", "")
        sim = _tanimoto(cand_fp, _fingerprint(smi))
        if sim > best_sim:
            best_sim = sim
            best_name = comp.get("name", "")
            comp_scaf = _scaffold(smi)
            best_scaf_match = bool(cand_scaf and comp_scaf and cand_scaf == comp_scaf)

    return {
        "name": best_name,
        "similarity": round(best_sim, 4) if best_sim >= 0 else None,
        "scaffold_match": best_scaf_match,
        "role": _role_for(best_sim) if best_sim >= 0 else "insufficient_data",
    }
