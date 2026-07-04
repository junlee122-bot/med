# Phase 5 — Professionalism Audit

Phase 5 adds a **professional scientific validation layer** on top of the existing
agentic pipeline. It does not rebuild anything. Every item below is labeled:
**IMPLEMENTED · PARTIALLY_IMPLEMENTED · NEEDS_HARDENING · INTENTIONAL_LIMITATION · NOT_IMPLEMENTED**.

> Research decision support only. No wet-lab protocol, synthesis route, reagent list,
> reaction condition, purification procedure, dosage, or medical advice. In-silico
> outputs are not efficacy, safety, or regulatory evidence. Final responsibility
> belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

## 0. Baseline validation (before Phase 5 changes)

- **Backend tests:** `pytest app/tests -q` → initially **95 passed, 1 failed**.
  The single failure (`test_source_type_audit_flags_missing_source_type`) was a
  pre-existing **test-isolation flake**: the suite ran against the persistent
  `backend/data/helixforge.db`, and the governance audit silently truncated its
  findings list to 50, so under accumulation the newly-inserted record fell past
  the cap. Fixed two ways (both shipped in Phase 5):
  1. `app/tests/conftest.py` isolates each test session to a temp `HELIXFORGE_DATA_DIR`
     (carrying the committed built-in snapshot forward), so tests no longer pollute
     a shared DB.
  2. `source_type_governance.audit()` now reports **full `counts`** and a
     `sample_truncated` flag instead of silently dropping findings ("no silent caps").
  → After the fix: **96 passed**.
- **Frontend:** `npm run typecheck` clean; `npm run build` passes (one non-blocking
  Vite chunk-size warning — see Phase 4 audit item, INTENTIONAL_LIMITATION).
- **Docker:** `docker compose config` → OK.

## Existing professional features found (do NOT duplicate)

| Area | Existing module | Phase 5 action |
|---|---|---|
| Evidence QA / citation verify | `evidence_linter.py`, citation verifier agent | **Extend** with formal grading, don't replace |
| ChEMBL assay analysis | `chembl_analysis.py` | **Extend** with unit normalization + endpoint comparability |
| Molecule scoring | `scoring.py` (composite) | **Feed** activity-reliability + applicability into it |
| Molecule diversity/scaffold | `molecule_diversity.py` | **Reuse** fingerprints for applicability domain |
| Safety/overclaim lint (KO+EN) | `safety_lint.py` | **Wrap** with a claim-language linter that suggests rewrites |
| Source-type governance | `source_type_governance.py` | **Hardened** (transparent counts) |
| Rubric scorecard | `rubric_scorecard.py` | Keep; complemented by professional release scorecard |
| Red-team suite | `red_team.py` (18) | **Extend** into scientific red-team 2.0 |
| Release readiness | `release_readiness.py` | Complement with professional category scorecard |
| Plausibility (Lipinski/Veber) | `scientific_plausibility.py` | **Reuse** thresholds in MedChem review |
| Proposal / submission | `proposal_writer.py`, `submission_pack.py` | Add reviewer briefs, whitepaper, professional docs |

## Phase 5 implementation checklist (priority order from spec §28)

1. Evidence hierarchy + claim grading — `evidence_grading.py` — **IMPLEMENTED**
2. ChEMBL activity normalization 2.0 — `activity_normalization.py` — **IMPLEMENTED**
3. Medicinal chemistry review — `medchem_review.py` — **IMPLEMENTED**
4. Applicability domain + uncertainty — `applicability_domain.py` — **IMPLEMENTED**
5. Scientific language linter — `scientific_language_linter.py` — **IMPLEMENTED**
6. Target biology review — `target_biology_review.py` — **IMPLEMENTED**
7. Translational readiness — `translational_readiness.py` — **IMPLEMENTED**
8. Clinical precedent review — `clinical_precedent_review.py` — **IMPLEMENTED**
9. Professional release scorecard — `professional_release.py` — **IMPLEMENTED**
10. Scientific whitepaper — `scientific_whitepaper.py` — **IMPLEMENTED**
11. Professional documentation pack — `professional_docs.py` — **IMPLEMENTED**
12. Expert review board — `expert_review_board.py` — **IMPLEMENTED**
13. Pareto multi-objective optimization — `pareto_optimization.py` — **IMPLEMENTED**
14. Docking protocol governance — `docking_protocol.py` — **IMPLEMENTED**
15. ADMET baseline validation protocol — `admet_validation.py` — **IMPLEMENTED (graceful skip without scikit-learn)**
16. Professional evaluation harness 2.0 — `professional_evaluation.py` — **IMPLEMENTED**
17. Professional red-team 2.0 — extended `red_team.py` — **IMPLEMENTED**
18. Identity normalization — `identity_normalization.py` — **IMPLEMENTED**
19. Expert-mode UI — new pages + tabs — **PARTIALLY_IMPLEMENTED** (dedicated expert pages; global toggle is INTENTIONAL_LIMITATION)
20. Optional external adapters (UniProt/PubChem/PDB/OpenTargets) — **PARTIALLY_IMPLEMENTED / NEEDS_HARDENING** (see §23)
21. Docs — **IMPLEMENTED**
22. Tests — **IMPLEMENTED**
23. Commit + push — **IMPLEMENTED**

## Duplicate/overlapping features avoided

- No parallel evidence store: grading reads existing `evidence_items`/`hypotheses`.
- No second scoring engine: normalization + applicability feed the existing composite.
- No second safety filter: the language linter delegates to `safety_lint` for forbidden content and only adds claim-language rewrites.
- No second fingerprinting: applicability domain reuses RDKit Morgan via existing helpers.

## Known limitations (INTENTIONAL_LIMITATION unless noted)

- AutoDock Vina & REINVENT4 remain `CONFIGURED_BUT_NOT_RUN` unless installed; docking is a prioritization signal, never binding proof.
- ADMET baseline requires optional scikit-learn; without it, no model is trained and no safety claim is made.
- Target biology / pathway context is drawn from available public evidence only; where data is absent it is marked unavailable — never fabricated.
- Regulatory documentation is quality-management-*inspired*, not a compliance claim.
- Expert-mode global UI toggle is not shipped; expert depth is exposed via dedicated pages/tabs instead.
- External knowledge adapters (UniProt/PubChem/PDB/Open Targets) ship as governed, health-checked adapters with offline/`CONFIGURED_BUT_NOT_RUN` fallback; live calls are optional and never a baseline dependency.

## Final validation results

See the bottom of `PHASE5_CHANGELOG.md` for the final test/build/compose results after all modules landed.
