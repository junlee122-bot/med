# ADMET Baseline Validation Protocol

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `admet_validation.py` · **Endpoints:** `/api/admet/validation/{train,models}`

**Structure.** dataset, endpoint type, split strategy, leakage checks, feature method, model family, metrics, calibration, applicability domain, limitations, status.

**Splits.** random, scaffold (Bemis-Murcko); time split reported NOT_AVAILABLE (no timestamps).

**Leakage checks.** duplicate canonical SMILES across split, invalid SMILES removed/counted, train/valid/test counts, label distribution.

**Metrics.** Regression: RMSE, MAE, R². Classification: ROC-AUC/accuracy. Metrics are ACTUALLY computed — never hardcoded.

**Honesty.** Requires optional scikit-learn/RDKit; without them status is SKIPPED_MISSING_DEPENDENCY, `metrics={}`, source_type CONFIGURED_BUT_NOT_RUN — no fabricated numbers. A trained model is `BASELINE_MODEL_OUTPUT`, explicitly NOT a safety-validated or clinical determination.
