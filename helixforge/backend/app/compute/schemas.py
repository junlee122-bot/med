"""Compute-layer enums and allowlists (Phase 8).

Plain string classes (mirrors the llm/ layer) so values serialize as-is in JSON
payload tables and FastAPI responses. Compute source types live in the shared
SourceType enum (app.models.schemas); the *reasoning* source types stay separate.
"""
from __future__ import annotations


class ComputeProfile:
    CPU_ONLY = "CPU_ONLY"
    CPU_WITH_OPTIONAL_LOCAL_TOOLS = "CPU_WITH_OPTIONAL_LOCAL_TOOLS"
    REMOTE_GPU_READY = "REMOTE_GPU_READY"
    REMOTE_GPU_ENABLED = "REMOTE_GPU_ENABLED"
    RECORDED_GPU_REPLAY = "RECORDED_GPU_REPLAY"
    COMPUTE_DEGRADED = "COMPUTE_DEGRADED"
    ALL = {CPU_ONLY, CPU_WITH_OPTIONAL_LOCAL_TOOLS, REMOTE_GPU_READY,
           REMOTE_GPU_ENABLED, RECORDED_GPU_REPLAY, COMPUTE_DEGRADED}


class ExecutionBackend:
    LOCAL_CPU = "LOCAL_CPU"
    LOCAL_PROCESS_POOL = "LOCAL_PROCESS_POOL"
    LOCAL_OPTIONAL_BINARY = "LOCAL_OPTIONAL_BINARY"
    REMOTE_GPU = "REMOTE_GPU"
    RECORDED_ARTIFACT = "RECORDED_ARTIFACT"
    CONFIG_ONLY = "CONFIG_ONLY"
    NOT_AVAILABLE = "NOT_AVAILABLE"
    ALL = {LOCAL_CPU, LOCAL_PROCESS_POOL, LOCAL_OPTIONAL_BINARY, REMOTE_GPU,
           RECORDED_ARTIFACT, CONFIG_ONLY, NOT_AVAILABLE}


class ComputeJobStatus:
    CREATED = "CREATED"
    VALIDATING = "VALIDATING"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    CHECKPOINTED = "CHECKPOINTED"
    SUCCEEDED = "SUCCEEDED"
    SUCCEEDED_WITH_WARNINGS = "SUCCEEDED_WITH_WARNINGS"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"
    BUDGET_BLOCKED = "BUDGET_BLOCKED"
    SAFETY_BLOCKED = "SAFETY_BLOCKED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    TOOL_ERROR = "TOOL_ERROR"
    ARTIFACT_INVALID = "ARTIFACT_INVALID"
    CONFIGURED_NOT_RUN = "CONFIGURED_NOT_RUN"
    ALL = {CREATED, VALIDATING, WAITING_FOR_APPROVAL, QUEUED, RUNNING, CHECKPOINTED,
           SUCCEEDED, SUCCEEDED_WITH_WARNINGS, CANCEL_REQUESTED, CANCELLED, TIMED_OUT,
           BUDGET_BLOCKED, SAFETY_BLOCKED, VALIDATION_FAILED, TOOL_ERROR, ARTIFACT_INVALID,
           CONFIGURED_NOT_RUN}
    TERMINAL = {SUCCEEDED, SUCCEEDED_WITH_WARNINGS, CANCELLED, TIMED_OUT, BUDGET_BLOCKED,
                SAFETY_BLOCKED, VALIDATION_FAILED, TOOL_ERROR, ARTIFACT_INVALID, CONFIGURED_NOT_RUN}


class ApprovalStatus:
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ALL = {NOT_REQUIRED, PENDING, APPROVED, REJECTED}


# Allowlisted GPU job types. NOTHING outside this set may be submitted.
GPU_JOB_TYPES = {
    "CHEMPROP_TRAIN",
    "CHEMPROP_PREDICT",
    "REINVENT4_TRANSFER_LEARNING",
    "REINVENT4_REINFORCEMENT_LEARNING",
    "GNINA_SCREEN",
    "VINA_GPU_SCREEN",
    "BOLTZ2_INFERENCE",
    "CHAI1_INFERENCE",
    "OPENMM_REFINEMENT",
    "ESM_EMBEDDING",
    "GPU_BATCH_EVALUATION",
}

# Local CPU job types (run in-process / process pool; never require GPU).
CPU_JOB_TYPES = {
    "CPU_DATASET_CURATE",
    "CPU_QSAR_TRAIN",
    "CPU_QSAR_PREDICT",
    "CPU_LIGAND_SIMILARITY_SCREEN",
    "CPU_ACTIVE_LEARNING_SIMULATION",
    "CPU_OPTIMIZATION_LOOP",
    "CPU_APPLICABILITY_ANALYSIS",
    "CPU_REDISCOVERY_BENCHMARK",
    "CPU_LOCAL_RAG_INDEX",
    "CPU_LOCAL_RAG_SEARCH",
    "CPU_REPORT_EVALUATION",
}

# Allowlisted container images per GPU job type — immutable digests are examples
# (verify in provider console). No arbitrary image may ever be used.
IMAGE_ALLOWLIST = {
    "CHEMPROP_TRAIN": "ghcr.io/helixforge/chemprop@sha256:PLACEHOLDER_DIGEST",
    "CHEMPROP_PREDICT": "ghcr.io/helixforge/chemprop@sha256:PLACEHOLDER_DIGEST",
    "REINVENT4_TRANSFER_LEARNING": "ghcr.io/helixforge/reinvent4@sha256:PLACEHOLDER_DIGEST",
    "REINVENT4_REINFORCEMENT_LEARNING": "ghcr.io/helixforge/reinvent4@sha256:PLACEHOLDER_DIGEST",
    "GNINA_SCREEN": "ghcr.io/helixforge/gnina@sha256:PLACEHOLDER_DIGEST",
    "VINA_GPU_SCREEN": "ghcr.io/helixforge/vina-gpu@sha256:PLACEHOLDER_DIGEST",
    "BOLTZ2_INFERENCE": "ghcr.io/helixforge/boltz2@sha256:PLACEHOLDER_DIGEST",
    "CHAI1_INFERENCE": "ghcr.io/helixforge/chai1@sha256:PLACEHOLDER_DIGEST",
    "OPENMM_REFINEMENT": "ghcr.io/helixforge/openmm@sha256:PLACEHOLDER_DIGEST",
    "ESM_EMBEDDING": "ghcr.io/helixforge/esm@sha256:PLACEHOLDER_DIGEST",
    "GPU_BATCH_EVALUATION": "ghcr.io/helixforge/eval@sha256:PLACEHOLDER_DIGEST",
}

# Fixed, non-overridable entrypoint per job type (the LLM/user never sets this).
ENTRYPOINT_ALLOWLIST = {jt: f"helixforge-worker --job-type {jt}" for jt in GPU_JOB_TYPES}

# Hard resource ceilings enforced by the validator regardless of request.
MAX_GPU_COUNT = 8
MAX_VRAM_GB = 80
MAX_RUNTIME_MINUTES = 240
MAX_OUTPUT_SIZE_MB = 4096
MAX_JOB_COST_USD_CEILING = 50.0  # absolute ceiling; per-provider caps may be lower

# Artifact policy.
ALLOWED_ARTIFACT_TYPES = {
    "dataset_manifest", "model_checkpoint", "predictions", "metrics",
    "calibration", "applicability", "plot_data", "gpu_config", "gpu_output",
    "logs", "report", "embedding", "structure", "trajectory_summary", "poses",
}
ALLOWED_ARTIFACT_MEDIA = {
    "application/json", "text/plain", "text/csv", "text/markdown",
    "application/octet-stream", "application/gzip",
}


def is_gpu_job_type(job_type: str) -> bool:
    return job_type in GPU_JOB_TYPES


def is_cpu_job_type(job_type: str) -> bool:
    return job_type in CPU_JOB_TYPES
