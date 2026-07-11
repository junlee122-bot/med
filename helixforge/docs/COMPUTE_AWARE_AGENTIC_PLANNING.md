# Compute-Aware Agentic Planning

The planner understands compute availability and routes each requested capability to a
CPU substitute, a validated GPU spec, or a recorded replay
(`services/compute_aware_planner.py`). Deterministic — works with no LLM key. An optional
LLM may *suggest* a strategy, but the route is always validated deterministically and can
never introduce shell, unsafe steps, or a budget bypass.

## GPU capability → CPU substitute
| GPU task | CPU substitute | Quality lost without GPU |
|---|---|---|
| CHEMPROP_TRAIN | RDKit FP + sklearn baseline (scaffold split, bootstrap uncertainty, applicability) | GNN capacity/accuracy |
| REINVENT4_OPTIMIZATION | selection optimization + Pareto re-rank + safe local enumeration | RL generative exploration |
| GNINA/VINA_GPU_SCREEN | ligand-based Morgan similarity + scaffold screen | 3D docking score/pose |
| BOLTZ2/CHAI1_INFERENCE | structure metadata + ligand-based confidence | predicted structure/confidence |
| OPENMM_REFINEMENT | protocol readiness record only | MD refinement / stability |

## ComputeDecision record
`requested_capability`, `selected_backend`, `selected_method`, `fallback_method`,
`reason`, `expected_quality`, `expected_latency`, `estimated_cost`,
`human_approval_required`, `quality_lost_without_gpu`, `gpu_would_add`, `source_type`,
`limitations`. Persisted per run and shown in **Agent Cockpit → Compute Decisions**.

## Guarantees (tested)
- No GPU present ⇒ every decision routes to `LOCAL_CPU` / `CONFIG_ONLY` (never a pipeline failure).
- The planner cannot emit shell, synthesis routes, dosage steps, or bypass the budget guard.
- Deterministic fallback works without an LLM key.

## Endpoints
`POST /api/compute/plan` · `GET /api/workflow/runs/{run_id}/compute-decisions` ·
`GET /api/compute/runs/{run_id}/decisions`.
