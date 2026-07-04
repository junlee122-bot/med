"""Seed selection for the optimization loop.

Picks a diverse set of valid seed molecules from a run's candidate pool. Seeds
are ordered by composite score (higher first) and, when RDKit is available,
de-duplicated by Bemis-Murcko scaffold so the loop starts from structurally
distinct starting points rather than a cluster of near-identical molecules.

The selector trusts a record's ``valid`` flag for eligibility but does NOT drop
a molecule merely because its SMILES fails to parse — such records are kept so
the downstream validity gate can reject them explicitly (and be counted).
"""
from __future__ import annotations

from typing import Any

try:
    from rdkit import Chem, RDLogger
    from rdkit.Chem.Scaffolds import MurckoScaffold

    RDLogger.DisableLog("rdApp.*")
    RDKIT = True
except Exception:  # pragma: no cover - environment without RDKit
    RDKIT = False


def _smiles_of(mol: dict[str, Any]) -> str:
    return mol.get("canonical_smiles") or mol.get("smiles") or ""


def _scaffold_key(smiles: str) -> str:
    """Return a scaffold key for diversity. Falls back to the raw SMILES.

    Molecules whose SMILES cannot be parsed get their raw string as key so they
    are never silently merged with a real scaffold — they pass through and are
    rejected later by the validity gate.
    """
    if not RDKIT or not smiles:
        return smiles
    try:
        scaffold = MurckoScaffold.MurckoScaffoldSmiles(smiles)
    except Exception:
        return smiles
    return scaffold or smiles


def select_seeds(mols: list[dict], k: int = 8) -> list[dict]:
    """Select up to ``k`` diverse, valid seed molecules.

    Parameters
    ----------
    mols:
        Molecule-candidate records (as stored in ``molecule_candidates``).
    k:
        Maximum number of seeds to return.

    Returns
    -------
    list of dict
        Each seed is ``{id, label, smiles, descriptors, composite_score}``.
        Ordered by descending composite score with scaffold-level diversity.
    """
    eligible = [m for m in mols if m.get("valid") is True]

    # Deterministic ordering: composite score desc, then id asc for stable ties.
    eligible.sort(
        key=lambda m: (-float(m.get("composite_score") or 0.0), str(m.get("id") or ""))
    )

    seeds: list[dict] = []
    seen_scaffolds: set[str] = set()
    for m in eligible:
        if len(seeds) >= k:
            break
        smiles = _smiles_of(m)
        key = _scaffold_key(smiles)
        # Empty scaffold key (unparseable-but-kept) should not collapse together;
        # give each such record a unique key so they all pass through.
        if key and key in seen_scaffolds:
            continue
        seen_scaffolds.add(key or f"__unkeyed__{m.get('id')}")
        seeds.append(
            {
                "id": m.get("id"),
                "label": m.get("label") or m.get("molecule_chembl_id") or m.get("id"),
                "smiles": smiles,
                "descriptors": m.get("descriptors") or {},
                "composite_score": float(m.get("composite_score") or 0.0),
                "pchembl_value": m.get("pchembl_value"),
            }
        )
    return seeds
