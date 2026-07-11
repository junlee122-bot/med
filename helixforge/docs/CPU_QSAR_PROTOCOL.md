# CPU QSAR Baseline Protocol

Honest scikit-learn baselines on RDKit features — for prioritization and expert review,
**never** clinical or safety validation.

> A CPU baseline is not a validated clinical model and is never called "production-grade".

## Pipeline (`services/cpu_qsar.py`)
1. **Features** — Morgan fingerprints (radius 2, 1024 bits). Invalid SMILES dropped + counted.
2. **Split** — Bemis-Murcko **scaffold split** (whole scaffolds to one side, no leakage);
   random split shown only as a comparison.
3. **Leakage** — duplicate canonical SMILES across train/test counted; nonzero ⇒
   `REVIEW_REQUIRED_LEAKAGE`.
4. **Models** — classification: RandomForest / LogisticRegression; regression:
   RandomForest / Ridge. No XGBoost/LightGBM/GPU dependency.
5. **Metrics** — classification: ROC-AUC, balanced accuracy, sensitivity, specificity,
   Brier, confusion matrix. Regression: RMSE, MAE, R², Spearman (if scipy).
6. **Uncertainty** — bootstrap ensemble std over test predictions.
7. **Applicability domain** — Morgan/Tanimoto nearest-neighbour to the training set;
   out-of-domain predictions flagged unreliable.
8. **Provenance** — model version, checksum, seed, package versions; source type
   `BASELINE_CPU_MODEL_OUTPUT`.

## Honesty rules
- < 8 valid rows ⇒ `INSUFFICIENT_DATA` (no model, no metrics).
- Test set < 20 ⇒ explicit `sample_size_warning` (indicative, not statistically powered).
- scikit-learn/RDKit/numpy absent ⇒ `CONFIGURED_BUT_NOT_RUN` (no fabricated metrics).
- **Prediction requires a trained in-process model**; if the artifact is gone
  (process restart) prediction returns `MODEL_ARTIFACT_MISSING` — never a fabricated value.
- No model binary is committed (models live in-process + metadata in the DB).

## Endpoints
`POST /api/cpu-models/train` · `GET /api/cpu-models` · `/{id}` · `/{id}/card` ·
`/{id}/validation` · `POST /{id}/predict`. Presentation-safe: small dataset, fixed seed,
short runtime, no downloads.
