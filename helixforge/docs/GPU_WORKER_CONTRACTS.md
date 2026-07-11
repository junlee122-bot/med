# GPU Worker Contracts

Schemas, validators, job builders, and CPU substitutes for 8 GPU workers
(`compute/gpu_worker_contracts.py`). **All are `GPU_CONFIGURED_NOT_RUN`** — no live GPU
work runs. Each documents inputs, outputs, validation rules, the CPU substitute, and the
future scientific value.

| Worker | CPU substitute | Future value | Never claims |
|---|---|---|---|
| CHEMPROP_TRAIN | RDKit FP + sklearn baseline | GNN accuracy on larger data | efficacy |
| REINVENT4_TL / RL | selection opt + safe local enumeration | learned de-novo generation | efficacy |
| GNINA_SCREEN | ligand-based similarity screen | docking signal | binding proof |
| VINA_GPU_SCREEN | ligand-based similarity screen | docking throughput | binding proof |
| BOLTZ2_INFERENCE | structure metadata + ligand confidence | co-folded structure | clinical efficacy |
| CHAI1_INFERENCE | structure availability metadata | structure prediction | binding proof |
| OPENMM_REFINEMENT | protocol readiness record | dynamics refinement | stability proof |
| ESM_EMBEDDING | sequence identity metadata | protein representations | biological claim |

## Output validators (anti-fabrication)
`validate_worker_output(job_type, artifact_types, has_protocol, has_split)`:
- docking output **without a protocol manifest** ⇒ rejected (no binding proof);
- training/eval **metrics without a declared split** ⇒ rejected (no fabricated metric);
- missing required outputs per the contract ⇒ rejected.

## Endpoints
`GET /api/compute/worker-contracts` · `GET /api/compute/worker-contracts/{job_type}`.
