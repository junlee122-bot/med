# Translational Development Readiness

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `translational_readiness.py` · **Endpoints:** `/api/translational/readiness/{run,*}`

**Levels.** TRL_0_CONCEPT_ONLY → TRL_4_READY_FOR_EXPERIMENTAL_PLANNING. **Hard cap at TRL_4** — the system holds no wet-lab/clinical data, so no higher level is possible.

**Output.** target/molecule/biomarker/safety readiness, manufacturability unknowns, clinical precedent (precedent ≠ efficacy), patient-selection & endpoint-strategy notes, regulatory-documentation status, evidence-grade summary, blocking gaps, high-level next actions.

**Honesty.** No wet-lab protocol, no dosing, no treatment recommendation, no clinical-validation claim. Human review is required and stated.
