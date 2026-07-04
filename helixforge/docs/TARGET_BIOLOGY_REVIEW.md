# Target Biology Review

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `target_biology_review.py` · **Endpoints:** `/api/target-biology/{review-run,run/*,target/*}`

**Dimensions (0–5 each).** Disease relevance, mechanistic plausibility, tractability/druggability, selectivity concern, safety liability, biomarker availability, clinical precedent, patient stratification, data sufficiency, development risk.

**Status.** PASS / REVIEW_REQUIRED / WEAK_SUPPORT / NOT_RECOMMENDED from the mean dimension score.

**Honesty.** Scores derive only from available signals (evidence volume/direction, precedent count, activity availability, target type). Pathway/mechanism text is a fixed honest "not independently retrieved; requires expert curation" statement when unavailable — never fabricated. Next steps are HIGH-LEVEL research needs only (e.g. "selectivity profiling required"), never protocols. Precedent ≠ efficacy.
