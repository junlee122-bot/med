# Phase 8 — CPU-First Scientific Expansion & External-GPU-Ready Infrastructure — Audit

Status labels: `IMPLEMENTED` · `EXTENDED` · `CPU_ONLY` · `GPU_READY` ·
`GPU_CONFIGURED_NOT_RUN` · `RECORDED_ONLY` · `OPTIONAL_DEPENDENCY` ·
`INTENTIONAL_LIMITATION` · `NOT_IMPLEMENTED`

> Research decision support only. No wet-lab protocol, synthesis route, reaction
> conditions, reagent list, purification, dosage, or medical advice. No fabricated
> GPU/model results. Final responsibility belongs to the human research team.

## Baseline (before Phase 8)
- Baseline commit: `5fa9f39` (report-retrieval fix).
- Backend tests: **264 passed, 1 skipped** (skip = opt-in live-LLM smoke).
- Frontend: `tsc --noEmit` clean; `vite build` passes.
- `docker compose config`: valid.
- No GPU, no `ANTHROPIC_API_KEY`, no external GPU provider in this environment.

## Existing modules relevant to compute (avoid duplication → EXTEND)
- `services/applicability_domain.py` — Morgan/Tanimoto applicability. **EXTENDED** (reused by ligand screen, QSAR, active learning).
- `services/pareto_optimization.py` — non-dominated sorting, roles. **EXTENDED** by `cpu_multiobjective` (thin wrapper, no fork).
- `services/optimization_loop.py`* (Phase 7) — safe optimization loop. **EXTENDED** with explicit CPU backend modes.
- `services/admet_validation.py` — ADMET baseline w/ split & leakage checks. Reused patterns for `cpu_qsar`.
- `services/molecule_diversity.py`, `services/chembl_analysis.py`, `services/activity_normalization.py` — reused by dataset curation.
- `services/snapshots.py` — record/replay. **EXTENDED** with compute manifest.
- `services/release_readiness.py` / `professional_release.py` — **EXTENDED** with compute categories.
- `api/health.py` — tiered tool health. Compute capability detection is a **new** first-class layer that complements it.
- `llm/` package + `llm/cost_estimator.py` — cost-guard pattern mirrored for compute (`compute/cost_guard.py`); reasoning source types kept **separate** from scientific/compute source types.

## Current CPU capabilities (pre-Phase-8)
- RDKit validation/descriptors/fingerprints/scaffolds; TDC dataset metadata; ChEMBL activity normalization; applicability domain; Pareto; medchem review; rediscovery; selection-based optimization loop. `CPU_ONLY` already viable for much of the pipeline.

## Current GPU capabilities (pre-Phase-8)
- None. Vina/REINVENT4 are honest `CONFIGURED_BUT_NOT_RUN`. No remote GPU layer, no job spec, no provider interface, no compute cost guard. → the Phase 8 gap.

## Phase 8 implementation checklist (priority order per §34)
Priority 1 — non-negotiable:
1. Compute capability detection — `compute/capability_detector.py` + `GET /api/compute/capabilities` — **IMPLEMENTED / CPU_ONLY**
2. Compute profile + source types — `compute/schemas.py`, `SourceType` additions — **IMPLEMENTED**
3. Compute-aware planner — `services/compute_aware_planner.py` (deterministic, no key needed) — **IMPLEMENTED / EXTENDED**
4. Safe `GPUJobSpec` + validator — `compute/job_spec.py`, `compute/job_validator.py` — **IMPLEMENTED / GPU_READY**
5. `LocalCPUProvider` — `compute/local_cpu_provider.py` — **IMPLEMENTED**
6. `FakeRemoteGPUProvider` (tests) — `compute/providers.py` — **IMPLEMENTED / RECORDED_ONLY**
7. Cost & approval guard — `compute/cost_guard.py` — **IMPLEMENTED**
8. Compute job/artifact registry — `compute/artifact_registry.py`, `services/compute_jobs.py`, db tables — **IMPLEMENTED**

Priority 2 — CPU scientific value:
9. Dataset curation studio — `services/dataset_curation.py` — **IMPLEMENTED / CPU_ONLY**
10. CPU QSAR baseline — `services/cpu_qsar.py` (scikit-learn OPTIONAL_DEPENDENCY; graceful skip) — **IMPLEMENTED / CPU_ONLY**
11. Ligand-based screening — `services/ligand_screening.py` — **IMPLEMENTED / CPU_ONLY**
12. Applicability & uncertainty integration — reuses `applicability_domain` + bootstrap — **EXTENDED**
13. Active-learning simulation — `services/active_learning.py` — **IMPLEMENTED / CPU_ONLY**
14. CPU optimization 2.0 — CPU backend modes on the loop — **EXTENDED**
15. CPU multi-objective — `services/cpu_multiobjective.py` — **EXTENDED**

Priority 3 — GPU readiness:
16. Generic REST GPU provider — `compute/providers.py::GenericRESTGPUProvider` (disabled by default, no paid calls) — **GPU_READY**
17. GPU worker contracts — `compute/gpu_worker_contracts.py` (Chemprop/REINVENT4/GNINA/Vina-GPU/Boltz2/Chai1/OpenMM/ESM) — **GPU_CONFIGURED_NOT_RUN**
18. Artifact validation — `compute/artifact_registry.py` (checksum, type/size, path-traversal) — **IMPLEMENTED**
19. Compute record/replay — `services/compute_snapshot.py` — **IMPLEMENTED / RECORDED_ONLY**
20. GPU dry-run demo — `POST /api/demo/run-gpu-readiness-dry-run` — **IMPLEMENTED**

Priority 4 — product integration:
21–27. Compute Center, Data & Model Lab, Active Learning pages, Cockpit compute decisions, reports/submission artifacts, evaluation, release readiness — **IMPLEMENTED** (subset of tabs; see PHASE8_CHANGELOG).

Priority 5: docs, tests, commit — **IMPLEMENTED**.

## Security risks & controls
- LLM/planner must never emit shell → job types are an **allowlist enum**; specs carry no command field; validator rejects `command`/`entrypoint`/`image` overrides, path traversal, secret-looking values, over-budget/over-runtime. (`compute/security.py`, `compute/job_validator.py`)
- Credentials via env only, masked in config endpoint, never in job payload/snapshot/export.
- Remote provider **disabled by default**; live calls gated on `HELIXFORGE_ENABLE_LIVE_GPU_TEST=true`; local health does no network.

## Cost risks & controls
- Pricing is user-configured, labeled "verify in provider console" — never asserted as permanent truth. Per-run + per-day budget guard; human approval required before any paid/remote job; replay cost = 0.

## Data-rights risks
- Dataset curation records source, retrieval timestamp, license status, redistribution caveat, snapshot policy; large datasets/checkpoints/artifacts are gitignored and never committed.

## Intentional limitations (`INTENTIONAL_LIMITATION` / `GPU_CONFIGURED_NOT_RUN`)
- No live GPU execution (Chemprop/REINVENT4/GNINA/Vina-GPU/Boltz-2/Chai-1/OpenMM) — schemas, validators, security, job specs, and recorded/dry-run paths exist; live runs remain configured-not-run.
- No paid LLM or GPU calls made during implementation (per §9–11): fake providers, recorded artifacts, dry-run specs only.
- scikit-learn is an OPTIONAL_DEPENDENCY: CPU QSAR degrades honestly to `CONFIGURED_BUT_NOT_RUN`/unavailable if absent (no fabricated metrics).

## Final validation result
- Backend: **325 passed, 1 skipped** (was 264; +61 offline Phase 8 tests; the skip is
  the opt-in live-LLM smoke). No regressions.
- Frontend: `tsc --noEmit` clean; `vite build` passes (pre-existing chunk-size advisory only).
- `docker compose config`: valid.
- `scripts/check_repo_hygiene.py`: PASS (0 warnings) — no db/secrets/large artifacts committed.
- No live paid GPU or LLM calls; 0 provider submissions; every GPU worker configured-not-run.
See PHASE8_CHANGELOG.md for the per-priority breakdown.
