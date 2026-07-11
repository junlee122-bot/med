# CPU-Only Scientific Mode

CPU-only is a **complete and useful scientific mode** in HelixForge — not a degraded
fallback. GPU is an optional accelerator; a missing GPU is never an error.

> Research decision support only. In-silico; not clinical/regulatory validation.

## What runs on CPU (no GPU, no LLM key required)
| Capability | Module | Source type | Honest limits |
|---|---|---|---|
| Compute capability detection | `compute/capability_detector` | — | local mode does no network |
| Dataset curation + quality/leakage | `services/dataset_curation` | `REAL_TOOL_OUTPUT`/`HUMAN_INPUT` | small demo-scale |
| CPU QSAR baseline | `services/cpu_qsar` | `BASELINE_CPU_MODEL_OUTPUT` | not a validated clinical model; sklearn-optional |
| Ligand-based screening | `services/ligand_screening` | `HEURISTIC_ANALYSIS` | prioritization signal, **not** binding proof |
| Applicability domain | `services/applicability_domain` | `REAL_TOOL_OUTPUT` | Morgan/Tanimoto only |
| Active-learning simulation | `services/active_learning` | `BASELINE_CPU_MODEL_OUTPUT` | oracle = held-out data, not experiments |
| Multi-objective / Pareto | `pareto_optimization` + `cpu_multiobjective` | `COMPUTE_FALLBACK_OUTPUT` | no single-best overclaim |
| Optimization loop (selection / local enum) | `services/optimization_loop` | `LOCAL_HEURISTIC_GENERATED` | no synthesis route |

## Scientific-honesty rules (enforced)
- A CPU prediction is **not** clinical validation and is never called "production-grade".
- Ligand similarity is a screening signal, **not** binding proof.
- No metric is fabricated: if scikit-learn/RDKit/data are missing, the result is
  `CONFIGURED_BUT_NOT_RUN` with the reason, not invented numbers.
- Prediction requires a trained in-process model; a missing artifact blocks prediction.
- Every model shows training-set size, split method, applicability domain, version, checksum.

## Run it
- One-click: `POST /api/demo/run-cpu-scientific-demo` or the **Compute Center → CPU Scientific Demo** button.
- Endpoints: `/api/datasets/*`, `/api/cpu-models/*`, `/api/ligand-screen/*`, `/api/active-learning/*`,
  `/api/optimization/cpu-multiobjective`.

## Optional dependency
scikit-learn is an OPTIONAL_DEPENDENCY. Absent → CPU QSAR and active learning degrade
to `CONFIGURED_BUT_NOT_RUN` (honest), while curation, screening, applicability, and
Pareto continue on RDKit alone.
