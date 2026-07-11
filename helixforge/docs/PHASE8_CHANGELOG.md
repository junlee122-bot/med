# Phase 8 Changelog — CPU-First Scientific Expansion & External-GPU-Ready Infrastructure

Phase 8 makes HelixForge scientifically stronger **without a GPU** and adds a safe,
provider-neutral architecture for **future** remote GPU jobs — without rewriting the
FastAPI app, agent runtime, reports, snapshots, or frontend. No live paid GPU or LLM
calls were made during implementation; fakes, recorded artifacts, and dry-run specs
are used throughout.

> Research decision support only. In-silico; not clinical/regulatory validation. No
> wet-lab, synthesis, reaction conditions, reagents, purification, dosage, or medical
> advice. No fabricated GPU/model results. Human responsibility is retained.

## New source types (12)
`REAL_CPU_MODEL_OUTPUT`, `BASELINE_CPU_MODEL_OUTPUT`, `RECORDED_CPU_MODEL_OUTPUT`,
`REAL_REMOTE_GPU_OUTPUT`, `RECORDED_GPU_OUTPUT`, `GPU_CONFIGURED_NOT_RUN`,
`GPU_JOB_ERROR`, `GPU_BUDGET_BLOCKED`, `GPU_SAFETY_BLOCKED`, `GPU_ARTIFACT_UNVERIFIED`,
`COMPUTE_FALLBACK_OUTPUT`, `LOCAL_HEURISTIC_GENERATED`. Reasoning source types (LLM)
remain a separate namespace.

## Priority 1 — compute foundation (non-negotiable)
- `app/compute/`: `schemas` (profiles, backends, statuses, allowlisted job types +
  images/entrypoints, resource ceilings), `config` (env-driven; remote disabled by
  default), `capability_detector` (safe, time-limited; local mode does no network;
  deep/remote opt-in), `security` (secret redaction, path-traversal, forbidden-field
  scan, audit + policies), `job_spec` (validate + `build_safe_job_payload` — image
  and entrypoint from server allowlist only), `cost_guard` (approximate,
  user-configured pricing; per-run/day budget), `providers` (LocalCPU, Recorded,
  GenericREST **disabled by default**, Fake with 10 scenarios), `provider_registry`,
  `artifact_registry` (checksum/type/size/path → `GPU_ARTIFACT_UNVERIFIED`),
  `job_manager` (create→validate→estimate→budget→approve; never auto-submits a paid job).
- `compute_aware_planner`: deterministic GPU→CPU-substitute routing + `ComputeDecision`
  records. No LLM key needed; cannot emit shell/synthesis/budget-bypass.
- `compute_api` + `/api/workflow/runs/{id}/compute-decisions`. 13 new db tables.

## Priority 2 — CPU-first science
- `chem_utils` (shared RDKit helpers). `dataset_curation` (identity/structure/label/
  split quality, duplicate + scaffold leakage, data-rights, quality score, trainable
  gating, data card). `cpu_qsar` (scikit-learn baselines, scaffold split,
  leakage detection, bootstrap uncertainty, applicability; sklearn-optional →
  configured-not-run; prediction needs a trained model; `BASELINE_CPU_MODEL_OUTPUT`).
  `ligand_screening` (Morgan/Tanimoto + scaffold + property window + applicability;
  "not a docking result / not binding proof"). `active_learning` (held-out-oracle
  simulation vs random baseline; deterministic seed; surrogate labels ≠ experiments).
  `cpu_multiobjective` (decision-policy layer over existing Pareto; no single-best
  overclaim; CPU-vs-recorded-GPU comparison). `model_lab_api`.

## Priority 3 — GPU readiness (all configured-not-run)
- `gpu_worker_contracts` (8 workers: Chemprop, REINVENT4 TL/RL, GNINA, Vina-GPU,
  Boltz-2, Chai-1, OpenMM, ESM) with input/output contracts + output validators that
  reject fabrication (docking needs a protocol; metrics need a split; no binding/
  efficacy claim). `compute_snapshot` (record/replay; replay = no provider call, zero
  cost; excludes credentials/binaries/logs). `cpu_demo` (one-click CPU scientific demo
  + GPU readiness dry-run — nothing submitted). `compute_demo_api`.

## Priority 4 — product
- Frontend: **Compute Center** (`/compute`), **Data & Model Lab** (`/model-lab`),
  **Active Learning** (`/active-learning`) + a "Compute & Models" nav group. 12 new
  compute/GPU source badges. `tsc` clean, `vite build` passes.

## Tests
+61 offline Phase 8 tests (no GPU/network/key): `test_compute_layer` (35),
`test_cpu_science` (16), `test_compute_gpu_readiness` (10). Full suite **325 passed,
1 skipped** (opt-in live-LLM smoke), up from 264 — no regressions.

## Remaining configured-not-run (intentional)
Live Chemprop/REINVENT4/GNINA/Vina-GPU/Boltz-2/Chai-1/OpenMM execution. Their schemas,
validators, security, job specs, and recorded/dry-run paths exist; live runs are
gated behind `HELIXFORGE_REMOTE_GPU_ENABLED` + `HELIXFORGE_ENABLE_LIVE_GPU_TEST` and
were not exercised.
