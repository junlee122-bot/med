# Dataset Curation Protocol

Turns raw activity/label records into a trainable, quality-scored `DatasetVersion`
(`services/dataset_curation.py`). Deterministic, RDKit-based.

## Stages
1. **Identity** — canonical SMILES; endpoint type / units / relation captured.
2. **Structure validation** — invalid SMILES removed + counted; duplicate canonical
   SMILES counted.
3. **Activity comparability** — mixed endpoint types (e.g. IC50 with EC50) flagged;
   unsupported/ambiguous units (anything outside nM/µM/mM/M) flagged.
4. **Label quality** — missing labels counted.
5. **Split quality** — scaffold split; duplicate leakage (canonical) and scaffold
   overlap across train/test measured.
6. **Data rights** — source, retrieval timestamp, license status, redistribution
   caveat, snapshot policy recorded.

## Quality score (0–100)
Mean of: identity completeness, structural validity, label completeness, unit
comparability, duplicate-leakage, split quality, data-rights completeness.

## Trainable gating
A dataset is **not** trainable (unless `exploratory=true`) when it has: < 8 valid unique
structures, train/test duplicate leakage, mixed endpoints, or no labels. Blocking gaps
and warnings are surfaced explicitly.

## Endpoints
`POST /api/datasets/curate` · `GET /api/datasets` · `/{id}` · `/{id}/quality` · `/{id}/card`.
