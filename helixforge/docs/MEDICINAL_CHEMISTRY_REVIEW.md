# Medicinal Chemistry Review

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `medchem_review.py` · **Endpoints:** `/api/medchem/{review-molecule,review-run,molecule/*}`

**Checks (real RDKit).** Lipinski Ro5 (≤1 violation), Veber (rotatable bonds ≤10, TPSA ≤140), lead-likeness (tighter ranges), QED, and structural alerts via the RDKit PAINS FilterCatalog plus a small set of non-actionable reactive-group SMARTS.

**Status.** FAVORABLE_FOR_REVIEW / NEEDS_OPTIMIZATION / STRUCTURAL_ALERT_REVIEW / LOW_CONFIDENCE / REJECT_INVALID.

**Honesty.** Degrades to CONFIGURED_BUT_NOT_RUN/HEURISTIC when RDKit or the PAINS catalog is unavailable — alerts are never faked. No synthesis instructions, no dosage, no safety determination. Alerts are recognition patterns only.
