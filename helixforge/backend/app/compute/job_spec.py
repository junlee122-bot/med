"""Safe GPU job specification: allowlisted job types, resource contracts, and a
strict validator. An LLM/user provides only structured, allowlisted fields — never
a command, image, or code. `build_safe_job_payload()` produces the payload that a
provider receives; the image/entrypoint come from the server-side allowlist only.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from app.compute import schemas as S
from app.compute.security import scan_spec_for_forbidden
from app.models.schemas import utcnow

# Per-job-type required inputs + expected output artifact types (the output contract).
JOB_CONTRACTS: dict[str, dict[str, Any]] = {
    "CHEMPROP_TRAIN": {"required": ["dataset_version_id"],
                       "outputs": ["model_checkpoint", "metrics", "predictions", "applicability", "logs"],
                       "safety_class": "model_training"},
    "CHEMPROP_PREDICT": {"required": ["input_artifact_ids"],
                         "outputs": ["predictions", "logs"], "safety_class": "inference"},
    "REINVENT4_TRANSFER_LEARNING": {"required": ["input_artifact_ids"],
                                    "outputs": ["model_checkpoint", "metrics", "logs"], "safety_class": "generation"},
    "REINVENT4_REINFORCEMENT_LEARNING": {"required": ["input_artifact_ids"],
                                         "outputs": ["predictions", "metrics", "logs"], "safety_class": "generation"},
    "GNINA_SCREEN": {"required": ["input_artifact_ids"],
                     "outputs": ["predictions", "poses", "logs"], "safety_class": "docking"},
    "VINA_GPU_SCREEN": {"required": ["input_artifact_ids"],
                        "outputs": ["predictions", "logs"], "safety_class": "docking"},
    "BOLTZ2_INFERENCE": {"required": ["input_artifact_ids"],
                         "outputs": ["structure", "metrics", "logs"], "safety_class": "structure"},
    "CHAI1_INFERENCE": {"required": ["input_artifact_ids"],
                        "outputs": ["structure", "metrics", "logs"], "safety_class": "structure"},
    "OPENMM_REFINEMENT": {"required": ["input_artifact_ids"],
                          "outputs": ["trajectory_summary", "metrics", "logs"], "safety_class": "simulation"},
    "ESM_EMBEDDING": {"required": ["input_artifact_ids"],
                      "outputs": ["embedding", "logs"], "safety_class": "embedding"},
    "GPU_BATCH_EVALUATION": {"required": ["input_artifact_ids"],
                             "outputs": ["metrics", "logs"], "safety_class": "evaluation"},
}

# Objectives that are never permitted (dual-use / harmful optimization).
FORBIDDEN_OBJECTIVE_TERMS = (
    "toxicity", "lethal", "lethality", "pathogen", "virulence", "weapon",
    "nerve agent", "explosive", "harmful delivery", "evasion", "bioweapon",
)


def _spec_hash(spec: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode()).hexdigest()[:16]


def default_resource_request() -> dict[str, Any]:
    return {"gpu_count": 1, "requested_vram_gb": 24, "cpu_cores": 4, "memory_gb": 16,
            "max_runtime_minutes": 120, "max_cost_usd": 5.0}


def _objective_text(spec: dict[str, Any]) -> str:
    parts: list[str] = []
    for key in ("model_config", "scoring_config", "objective", "objectives", "notes"):
        v = spec.get(key)
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, (dict, list)):
            parts.append(json.dumps(v, default=str))
    return " ".join(parts).lower()


def validate_gpu_job_spec(spec: dict[str, Any], max_cost_ceiling: float | None = None) -> dict[str, Any]:
    """Return {valid, errors, warnings, normalized}. Deterministic; no I/O."""
    errors: list[str] = []
    warnings: list[str] = []
    job_type = str(spec.get("job_type", "")).strip()

    if job_type not in S.GPU_JOB_TYPES:
        errors.append(f"job_type '{job_type}' is not in the allowlist {sorted(S.GPU_JOB_TYPES)}.")
    # 1. Forbidden / injection fields anywhere in the spec.
    forbidden = scan_spec_for_forbidden(spec)
    if forbidden:
        errors.append(f"forbidden/unsafe fields present: {forbidden}")
    # 2. Resource ceilings.
    rr = spec.get("resource_request") or {}
    gpu_count = int(rr.get("gpu_count", 1) or 1)
    vram = int(rr.get("requested_vram_gb", 24) or 24)
    runtime = int(rr.get("max_runtime_minutes", 120) or 120)
    max_cost = float(rr.get("max_cost_usd", 5.0) or 5.0)
    if gpu_count < 1 or gpu_count > S.MAX_GPU_COUNT:
        errors.append(f"gpu_count must be 1..{S.MAX_GPU_COUNT}.")
    if vram > S.MAX_VRAM_GB:
        errors.append(f"requested_vram_gb exceeds ceiling {S.MAX_VRAM_GB}.")
    if runtime < 1 or runtime > S.MAX_RUNTIME_MINUTES:
        errors.append(f"max_runtime_minutes must be 1..{S.MAX_RUNTIME_MINUTES}.")
    ceiling = min(S.MAX_JOB_COST_USD_CEILING, max_cost_ceiling) if max_cost_ceiling else S.MAX_JOB_COST_USD_CEILING
    if max_cost <= 0 or max_cost > ceiling:
        errors.append(f"max_cost_usd must be >0 and <= {ceiling}.")
    # 3. Output contract.
    oc = spec.get("output_contract") or {}
    size_mb = int(oc.get("maximum_total_size_mb", S.MAX_OUTPUT_SIZE_MB) or S.MAX_OUTPUT_SIZE_MB)
    if size_mb > S.MAX_OUTPUT_SIZE_MB:
        errors.append(f"output size exceeds ceiling {S.MAX_OUTPUT_SIZE_MB} MB.")
    # 4. Required inputs per contract.
    contract = JOB_CONTRACTS.get(job_type, {})
    for req in contract.get("required", []):
        if not spec.get(req):
            errors.append(f"missing required input '{req}' for {job_type}.")
    # 5. Harmful objective terms.
    otext = _objective_text(spec)
    bad = [t for t in FORBIDDEN_OBJECTIVE_TERMS if t in otext]
    if bad:
        errors.append(f"objective references forbidden dual-use terms: {bad}")
    # 6. Human approval must be required for any paid/remote job.
    if spec.get("human_approval_required") is False:
        warnings.append("human_approval_required was false; forcing True for a paid/remote job.")

    normalized = {
        "job_type": job_type, "job_version": str(spec.get("job_version", "1")),
        "project_id": spec.get("project_id"), "workflow_run_id": spec.get("workflow_run_id"),
        "input_artifact_ids": list(spec.get("input_artifact_ids") or []),
        "dataset_version_id": spec.get("dataset_version_id"),
        "model_config": spec.get("model_config") or {},
        "scoring_config": spec.get("scoring_config") or {},
        "resource_request": {"gpu_count": gpu_count, "requested_vram_gb": vram, "cpu_cores": int(rr.get("cpu_cores", 4) or 4),
                             "memory_gb": int(rr.get("memory_gb", 16) or 16),
                             "max_runtime_minutes": runtime, "max_cost_usd": max_cost},
        "output_contract": {"required_artifact_types": contract.get("outputs", []),
                            "maximum_total_size_mb": size_mb},
        "safety_policy_version": str(spec.get("safety_policy_version", "phase8-1")),
        "safety_class": contract.get("safety_class"),
        "human_approval_required": True,
    }
    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "normalized": normalized, "spec_hash": _spec_hash(normalized)}


def build_safe_job_payload(normalized_spec: dict[str, Any]) -> dict[str, Any]:
    """Build the payload a provider receives. Image + entrypoint come ONLY from the
    server-side allowlist — never from the caller. Secrets are never included."""
    jt = normalized_spec["job_type"]
    return {
        "job_type": jt,
        "image": S.IMAGE_ALLOWLIST.get(jt),           # immutable digest, server-chosen
        "entrypoint": S.ENTRYPOINT_ALLOWLIST.get(jt),  # fixed, non-overridable
        "spec": normalized_spec,
        "spec_hash": _spec_hash(normalized_spec),
        "network_policy": "no-arbitrary-egress; approved data sources only",
        "privileged": False, "host_mounts": [],
        "built_at": utcnow(),
    }


def validate_output_contract(job_type: str, artifact_types: list[str]) -> dict[str, Any]:
    """Check that returned artifact types satisfy the job's declared output contract."""
    required = set(JOB_CONTRACTS.get(job_type, {}).get("outputs", []))
    present = set(artifact_types)
    missing = sorted(required - present)
    unexpected = sorted(present - required - S.ALLOWED_ARTIFACT_TYPES)
    return {"satisfied": not missing, "missing": missing, "unexpected": unexpected}
