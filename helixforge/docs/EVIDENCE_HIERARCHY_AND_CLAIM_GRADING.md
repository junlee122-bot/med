# Evidence Hierarchy and Claim Grading

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `evidence_grading.py` · **Endpoints:** `/api/evidence-grades/{compute,grade-claim,lint-report}`

**Purpose.** Grade every claim by the STRENGTH of the evidence behind it so a reviewer sees whether a statement rests on clinical evidence, an assay, a database association, or an assumption.

**Evidence levels (1 strongest → 9 weakest).** Clinical guideline/approval context; RCT/interventional trial; observational/real-world; preclinical in-vivo; in-vitro/biochemical assay; computational/in-silico; review/background; database association; assumption/unverified.

**Claim grades.** A_STRONG, B_MODERATE, C_PRELIMINARY, D_WEAK, E_UNVERIFIED, F_CONTRADICTED.

**Rules (non-negotiable).** Computational-only support cannot be phrased as clinical truth. Database association is preliminary. Review-only support is not direct experimental evidence. A contradiction downgrades; a majority contradiction → F. A failed/unverified citation → E. An in-silico molecule score is not efficacy. ClinicalTrials precedent is precedent (capped at B). ChEMBL activity is assay evidence (capped at B). TDC outputs are model outputs. Heuristic regulatory checklists are not advice.

**Report linter.** `detect_unsupported_strong_claims()` flags strong-claim language (EN+KO) and delegates forbidden/overclaim detection to `safety_lint`.
