# Active-Learning Simulation (CPU)

Demonstrates how HelixForge could decide which candidates deserve expensive GPU
calculations or future experiments — without a GPU (`services/active_learning.py`).
**This is a simulation against a dataset oracle; surrogate labels are never called
experiments.**

## Design
- Input: candidate pool `[{smiles, label}]` (label = held-out oracle truth), acquisition
  strategy, cycles, batch size, initial labeled set, deterministic seed.
- Each cycle: train a RandomForest on the labeled set → score the pool → acquire a batch
  by strategy → reveal held-out labels → retrain → record hit rate.
- Strategies: `uncertainty`, `top_score`, `uncertainty_x_utility`,
  `diversity_uncertainty`, `random`.
- Oracle modes: `HELD_OUT_DATASET_LABEL`, `CPU_SURROGATE`, `RECORDED_GPU_OUTPUT`,
  `RECORDED_LABEL`, `NO_ORACLE`. Every result states the oracle and that it is **not experiments**.

## Output
Learning curve, area-under-curve, mean hit rate, comparison vs a **random baseline**
(`beats_random`), and `gpu_escalation_candidates` (top picks for a future GPU job).
Deterministic seed → reproducible. Source type `BASELINE_CPU_MODEL_OUTPUT`.

## Endpoints
`POST /api/active-learning/run` · `GET /api/active-learning/runs` · `/{id}`.
