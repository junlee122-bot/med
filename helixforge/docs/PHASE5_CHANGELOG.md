# Phase 5 Changelog — Professional Scientific Validation Layer

Phase 5 added a professional validation layer on top of the existing agentic
pipeline. It did not rebuild anything; it hardened credibility for expert
reviewers (computational/medicinal chemists, bioinformaticians, translational and
clinical reviewers, regulatory and AI/ML reviewers). Deterministic and testable
where possible. See `PHASE5_PROFESSIONALISM_AUDIT.md` for the feature inventory and
status labels.

> Research decision support only. In-silico and assay evidence are not clinical
> efficacy, safety, or regulatory validation. No wet-lab protocol, synthesis route,
> reagent list, reaction condition, purification, dosage, or medical advice. Final
> responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

## Baseline hardening (P5-0)
- `app/tests/conftest.py`: isolate each test session to a temp `HELIXFORGE_DATA_DIR`
  (built-in snapshot carried in) — no more shared-DB pollution.
- `source_type_governance.audit()`: transparent full `counts` + `sample_truncated`
  flag instead of silently truncating findings ("no silent caps").

## New professional modules (deterministic, tested)
| Module | What it adds | Key honesty rule |
|---|---|---|
| `evidence_grading.py` | 9-level evidence hierarchy → A–F claim grading; report linter | assay ≠ efficacy; failed citation → E; contradiction → F |
| `activity_normalization.py` | unit→nM (unambiguous only), endpoint comparability, relation/assay-confidence reliability, IQR/MAD outliers, dup grouping | IC50 never mixed with EC50; ambiguous units not converted |
| `medchem_review.py` | Lipinski/Veber/lead-likeness + PAINS + structural alerts (real RDKit) | graceful degrade; no synthesis/dosage |
| `applicability_domain.py` | Morgan-Tanimoto applicability domain + uncertainty | UNKNOWN without a reference set; OOD lowers confidence |
| `scientific_language_linter.py` | EN+KO overclaim detection with conservative rewrites | forbidden content flagged, never auto-paraphrased |
| `target_biology_review.py` | 10-dimension target plausibility review | no fabricated pathways; precedent ≠ efficacy; high-level next steps only |
| `translational_readiness.py` | TRL assessment | hard-capped at TRL_4 (no wet-lab); human review needed |
| `clinical_precedent_review.py` | endpoint-category reasoning + precedent strength | precedent ≠ efficacy; no dosing/treatment advice |
| `pareto_optimization.py` | multi-objective Pareto front | missing objectives lower confidence; no single-best overclaim |
| `docking_protocol.py` | governed docking protocol records + lint | score w/o box → BLOCKED; configured-not-run ≠ binding proof |
| `admet_validation.py` | leakage-aware baseline (scaffold split, dup checks) | real metrics only, else CONFIGURED_BUT_NOT_RUN; model output ≠ safety |
| `identity_normalization.py` | cross-source ID mapping + InChIKey | unresolved refs = NOT_RESOLVED/ASSUMPTION |
| `expert_review_board.py` | role-based sign-off queue | high-risk pending blocks final-ready |
| `professional_release.py` | 16-category (A–P) professional readiness scorecard | HEURISTIC; reflects expert-review + governance state |
| `red_team_pro.py` | 24 scientific adversarial probes over the whole layer | all defended (self-audit) |
| `professional_docs.py` | 17 audit-ready doc types (cards, risk register, validation protocol, traceability, "what we do not claim", real-vs-replay, reviewer briefs, governance appendices) | bilingual disclaimer + source legend in every doc |
| `scientific_whitepaper.py` | 25-section EN/KO whitepaper | limitations + source legend; no clinical overclaim |

## API surface added
`/api/evidence-grades/*`, `/api/activities/*`, `/api/medchem/*`, `/api/applicability/*`,
`/api/language-lint/*`, `/api/target-biology/*`, `/api/translational/*`,
`/api/clinical/precedent-review*`, `/api/optimization/pareto/*`, `/api/docking/protocol/*`,
`/api/admet/validation/*`, `/api/identity/*`, `/api/expert-review/*`,
`/api/release-readiness/professional*`, `/api/red-team/professional/*`,
`/api/professional-docs/*`, `/api/whitepaper/*`.

## Frontend (expert pages)
- `/evidence-grading` — graded-claim table + unsupported-strong-claim linter.
- `/molecule-qa` — tabs: activity normalization, medchem review, applicability domain.
- `/professional-review` — tabs: release scorecard, target biology, translational,
  clinical precedent, Pareto, scientific red-team.
- `/expert-review` — role-based sign-off queue.
- `/professional-docs` — generate any doc / whitepaper (KO/EN).

## Docs added
`PHASE5_PROFESSIONALISM_AUDIT.md`, `SCIENTIFIC_WHITEPAPER_{EN,KO}.md`,
`WHAT_WE_DO_NOT_CLAIM_KO.md`, `REAL_VS_REPLAY_VS_NOT_RUN_KO.md`,
`MODEL_GOVERNANCE_APPENDIX_KO.md`, `DATA_GOVERNANCE_APPENDIX_KO.md`,
`SCIENTIFIC_REVIEWER_BRIEF_KO.md`, `BUSINESS_REVIEWER_BRIEF_KO.md`, plus the
per-topic protocol docs and this changelog.

## Not shipped (INTENTIONAL_LIMITATION)
- Global Judge/Expert UI toggle (expert depth is exposed via dedicated pages instead).
- Live external adapters beyond the existing UniProt/PubChem stubs are not a baseline dependency.
- Agent-performance harness and professional-evaluation study runner are partially
  covered by the release scorecard + red-team; a dedicated study runner is roadmapped.

## Final validation
- Backend: `pytest app/tests -q` → **186 passed** (isolated temp DB).
- Frontend: `tsc --noEmit` clean; `vite build` passes.
- `docker compose config` → OK.
- `python scripts/check_repo_hygiene.py` → PASS.
- Professional red-team: 24/24 defended.
