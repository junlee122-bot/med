# ChEMBL Activity Normalization Protocol

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `activity_normalization.py` · **Endpoints:** `/api/activities/{normalize,run/*/summary,molecule/*,recompute-candidate-scores}`

**Unit conversion.** Only unambiguous units are converted to nM (nM, µM, mM, M). Ambiguous/unsupported units (e.g. µg·mL⁻¹) are marked `UNSUPPORTED`, reliability is lowered, and a warning is recorded — never guessed.

**Relation penalty.** `=` is most reliable; `<`,`>`,`~`,missing are penalized.

**Assay confidence.** ChEMBL assay-confidence score is used when present; otherwise marked UNKNOWN with a conservative default.

**Endpoint comparability.** IC50/Ki/Kd/EC50/AC50/GI50 are grouped and summarized SEPARATELY. IC50 is never mixed with EC50.

**Outliers.** Per comparable group, robust IQR (with MAD fallback for degenerate spread); flagged, never removed.

**Duplicates.** Same molecule + endpoint grouped; raw records preserved; median aggregation for the per-molecule pChEMBL.

**Reliability → score.** A per-molecule `activity_reliability_score` (relation, units, assay confidence, endpoint comparability) scales the activity contribution and uncertainty of the recomputed composite score. Low-reliability data cannot inflate the score.
