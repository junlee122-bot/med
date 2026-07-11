# GPU Job Specification

A `GPUJobSpec` is the only way GPU work is expressed. It carries structured, allowlisted
fields — never a command, image, or code.

```json
{
  "job_type": "CHEMPROP_TRAIN",
  "job_version": "1",
  "project_id": "...",
  "workflow_run_id": "...",
  "input_artifact_ids": [],
  "dataset_version_id": "...",
  "model_config": {},
  "resource_request": {
    "gpu_count": 1, "requested_vram_gb": 24, "cpu_cores": 4, "memory_gb": 16,
    "max_runtime_minutes": 120, "max_cost_usd": 5.0
  },
  "output_contract": { "required_artifact_types": [], "maximum_total_size_mb": 2048 },
  "safety_policy_version": "phase8-1",
  "human_approval_required": true
}
```

## Allowed job types (`compute/schemas.py::GPU_JOB_TYPES`)
`CHEMPROP_TRAIN`, `CHEMPROP_PREDICT`, `REINVENT4_TRANSFER_LEARNING`,
`REINVENT4_REINFORCEMENT_LEARNING`, `GNINA_SCREEN`, `VINA_GPU_SCREEN`,
`BOLTZ2_INFERENCE`, `CHAI1_INFERENCE`, `OPENMM_REFINEMENT`, `ESM_EMBEDDING`,
`GPU_BATCH_EVALUATION`. No other type is accepted unless added in code.

## Server-controlled fields
`build_safe_job_payload()` attaches the **image** (immutable digest) and **entrypoint**
(fixed) from the server allowlist — the caller never sets them. `privileged=false`,
`host_mounts=[]`, `network_policy="no-arbitrary-egress"`.

## Validation (`validate_gpu_job_spec`)
Rejects: unapproved job type, forbidden/injection fields, over-ceiling resources,
over-budget cost, oversized output, missing required inputs per contract, harmful
objective terms. Forces `human_approval_required=true`.

## Dry run (no submission)
`POST /api/compute/jobs/dry-run` returns the validated spec, selected provider, cost
estimate, expected artifacts, blocked fields, and approval requirement — with
`submitted: false`.

## Output contract
`validate_output_contract(job_type, artifact_types)` + `validate_worker_output(...)`
reject fabrication: docking output needs a protocol manifest; training/eval metrics
need a declared split; no binding/efficacy claim.
