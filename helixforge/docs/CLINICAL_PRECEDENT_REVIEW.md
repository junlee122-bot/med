# Clinical Precedent Review

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `clinical_precedent_review.py` · **Endpoints:** `/api/clinical/precedent-review*`

**Interpretation.** From ClinicalTrials.gov evidence: trial count, inferred phase/status/intervention patterns (default UNKNOWN when absent), high-level endpoint categories (survival, response rate, biomarker, safety/tolerability, PK, quality of life, other/unknown), termination/withdrawal signals.

**Precedent strength.** HIGH / MODERATE / LIMITED / NO_PRECEDENT_FOUND / UNKNOWN_DUE_TO_TOOL_ERROR.

**Honesty.** Efficacy is never inferred; precedent is precedent. No treatment or dosage advice. `expert_review_needed = True`.
