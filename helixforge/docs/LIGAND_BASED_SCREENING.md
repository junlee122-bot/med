# Ligand-Based Virtual Screening (CPU)

Without GPU docking, HelixForge provides a useful ligand-based screen
(`services/ligand_screening.py`). **This is a prioritization signal — not a docking
result and not binding proof.**

## Method
- Canonical-SMILES validation; invalid → `REJECT_INVALID`.
- Morgan fingerprints; `BulkTanimoto` to reference (known) ligands; nearest + top-k.
- Bemis-Murcko scaffold overlap with the reference scaffold set.
- Drug-like property window filter (MW/logP/HBD/HBA/TPSA).
- Applicability: `IN_DOMAIN` / `BORDERLINE` / `OUT_OF_DOMAIN` by nearest similarity.
- Duplicate filtering by canonical SMILES.

## Recommendation labels
`KNOWN_LIKE_PRIORITY` (≥ 0.7 to a known active), `DIVERSE_EXPLORATION`, `BORDERLINE`,
`OUT_OF_DOMAIN` (< 0.2), `DUPLICATE`, `REJECT_INVALID`, `SAFETY_BLOCKED`.

## Honesty
Every result carries the banner: *"Ligand-based screening is a prioritization signal —
NOT a docking result and NOT binding proof."* No binding energy or pose is produced.
Source type `HEURISTIC_ANALYSIS`.

## Endpoints
`POST /api/ligand-screen/run` · `GET /api/ligand-screen/runs/{id}`.
