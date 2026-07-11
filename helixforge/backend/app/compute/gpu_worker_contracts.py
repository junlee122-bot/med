"""GPU worker contracts (Phase 8, Section 19).

Declarative input/output contracts + validators for each GPU worker. NO live GPU
work runs here — every worker is GPU_CONFIGURED_NOT_RUN. Each contract documents
required inputs, expected outputs, validation rules, the CPU substitute, and the
future scientific value. Output validators reject fabrication (e.g. a docking score
with no protocol, a prediction with no molecule id, a metric with no split).
"""
from __future__ import annotations

from typing import Any

from app.compute import job_spec as JS
from app.models.schemas import SourceType, utcnow

CONTRACTS: dict[str, dict[str, Any]] = {
    "CHEMPROP_TRAIN": {
        "inputs": ["curated dataset artifact", "task type", "target column", "split manifest",
                   "feature config", "ensemble size", "seed", "epochs", "early stopping", "requested resources"],
        "outputs": ["checkpoint", "predictions", "metrics", "calibration", "uncertainty",
                    "applicability summary", "model card", "logs"],
        "validation": ["required files present", "metric JSON schema", "dataset hash match",
                       "checkpoint checksum", "no metric fabrication", "no prediction without molecule id"],
        "cpu_substitute": "RDKit fingerprints + scikit-learn baseline (scaffold split, bootstrap uncertainty)",
        "future_value": "message-passing GNN accuracy on larger datasets.",
        "no_binding_or_efficacy_claim": True},
    "REINVENT4_TRANSFER_LEARNING": {
        "inputs": ["seed molecules", "target", "scoring configuration", "safety constraints",
                   "generation count", "maximum candidates", "output directory contract"],
        "outputs": ["config", "generated SMILES", "training curve", "score history",
                    "checkpoint", "generation metadata", "logs"],
        "validation": ["RDKit validation", "duplicate filtering", "source labeling", "safety gate",
                       "no synthesis instructions", "no fake result when config only"],
        "cpu_substitute": "selection-based optimization + safe local enumeration (no synthesis route)",
        "future_value": "learned de-novo generation beyond seed chemotypes.",
        "no_binding_or_efficacy_claim": True},
    "REINVENT4_REINFORCEMENT_LEARNING": {
        "inputs": ["seed molecules", "scoring configuration", "safety constraints", "generation count"],
        "outputs": ["generated SMILES", "score history", "metrics", "logs"],
        "validation": ["RDKit validation", "safety gate", "no synthesis instructions"],
        "cpu_substitute": "score-weight search + Pareto re-ranking (selection optimization)",
        "future_value": "RL-guided exploration of novel scaffolds.",
        "no_binding_or_efficacy_claim": True},
    "GNINA_SCREEN": {
        "inputs": ["prepared receptor artifact", "prepared ligand library", "docking box", "mode",
                   "controls", "resource limit"],
        "outputs": ["candidate IDs", "poses (if allowed)", "docking/CNN scores", "logs", "protocol manifest"],
        "validation": ["prepared input requirement", "no binding-proof claim", "score schema",
                       "control metadata", "protocol completeness"],
        "cpu_substitute": "ligand-based Morgan similarity + scaffold screen (prioritization signal only)",
        "future_value": "structure-based docking signal (still not binding proof).",
        "no_binding_or_efficacy_claim": True},
    "VINA_GPU_SCREEN": {
        "inputs": ["prepared receptor", "prepared ligand library", "docking box", "resource limit"],
        "outputs": ["candidate IDs", "docking scores", "logs", "protocol manifest"],
        "validation": ["prepared input requirement", "no binding-proof claim", "score schema"],
        "cpu_substitute": "ligand-based similarity screen; CPU Vina only if installed + inputs prepared",
        "future_value": "GPU-accelerated docking throughput.",
        "no_binding_or_efficacy_claim": True},
    "BOLTZ2_INFERENCE": {
        "inputs": ["target sequence or approved structure input", "ligand SMILES", "model settings", "candidate IDs"],
        "outputs": ["structure artifact", "confidence metrics", "affinity/binder outputs (if provided)",
                    "logs", "version manifest"],
        "validation": ["candidate identity mapping", "model/version present", "confidence present",
                       "no clinical efficacy claim", "no binding-proof claim"],
        "cpu_substitute": "target structure metadata + ligand-based confidence (no fabricated structure score)",
        "future_value": "co-folded structure + confidence (not clinical efficacy).",
        "no_binding_or_efficacy_claim": True},
    "CHAI1_INFERENCE": {
        "inputs": ["target input", "ligand SMILES", "model settings", "candidate IDs"],
        "outputs": ["structure artifact", "confidence metrics", "logs", "version manifest"],
        "validation": ["candidate identity mapping", "model/version present", "no binding-proof claim"],
        "cpu_substitute": "structure availability metadata only until a real run is performed",
        "future_value": "structure prediction for prioritized candidates.",
        "no_binding_or_efficacy_claim": True},
    "OPENMM_REFINEMENT": {
        "inputs": ["validated prepared system artifact", "protocol ID", "maximum simulation time",
                   "seed", "compute budget"],
        "outputs": ["trajectory summary", "energy summary", "RMSD/contact summary", "logs", "protocol manifest"],
        "validation": ["no stability proof claim", "no unvalidated force-field claim",
                       "system preparation status", "protocol completeness"],
        "cpu_substitute": "protocol readiness record only (no stability claim without a real run)",
        "future_value": "dynamics-informed refinement (not proof of stability).",
        "no_binding_or_efficacy_claim": True},
    "ESM_EMBEDDING": {
        "inputs": ["protein sequence IDs", "sequence artifacts", "model ID"],
        "outputs": ["embedding artifact", "metadata", "checksum", "logs"],
        "validation": ["no downstream biological claim from embedding alone", "checksum present"],
        "cpu_substitute": "sequence identity metadata; no embedding without a real run",
        "future_value": "protein representations for downstream models.",
        "no_binding_or_efficacy_claim": True},
    "GPU_BATCH_EVALUATION": {
        "inputs": ["input artifact ids", "evaluation config"],
        "outputs": ["metrics", "logs"],
        "validation": ["metric schema", "no fabricated metrics"],
        "cpu_substitute": "CPU evaluation harness",
        "future_value": "large-batch GPU evaluation throughput.",
        "no_binding_or_efficacy_claim": True},
}


def list_contracts() -> dict[str, Any]:
    from app.compute import schemas as S
    rows = []
    for jt, c in CONTRACTS.items():
        rows.append({"job_type": jt, "status": "GPU_CONFIGURED_NOT_RUN",
                     "image": S.IMAGE_ALLOWLIST.get(jt), "entrypoint": S.ENTRYPOINT_ALLOWLIST.get(jt),
                     "input_requirements": c["inputs"], "output_requirements": c["outputs"],
                     "validation_rules": c["validation"], "cpu_substitute": c["cpu_substitute"],
                     "future_scientific_value": c["future_value"]})
    return {"contracts": rows, "count": len(rows),
            "note": "All GPU workers are configured-not-run: schemas/validators/specs exist; no live run.",
            "source_type": SourceType.GPU_CONFIGURED_NOT_RUN.value, "checked_at": utcnow()}


def get_contract(job_type: str) -> dict[str, Any]:
    c = CONTRACTS.get(job_type)
    if not c:
        return {"status": "UNKNOWN_JOB_TYPE"}
    return {"job_type": job_type, "status": "GPU_CONFIGURED_NOT_RUN", **c}


def build_job_spec(job_type: str, project_id: str | None = None, workflow_run_id: str | None = None,
                   input_artifact_ids: list[str] | None = None, dataset_version_id: str | None = None,
                   model_config: dict | None = None) -> dict[str, Any]:
    """Assemble + validate a job spec for a worker type (no submission)."""
    spec = {
        "job_type": job_type, "project_id": project_id, "workflow_run_id": workflow_run_id,
        "input_artifact_ids": input_artifact_ids or [], "dataset_version_id": dataset_version_id,
        "model_config": model_config or {}, "resource_request": JS.default_resource_request(),
        "output_contract": {"maximum_total_size_mb": 2048},
        "human_approval_required": True,
    }
    return JS.validate_gpu_job_spec(spec)


def validate_worker_output(job_type: str, artifact_types: list[str],
                           has_protocol: bool = False, has_split: bool = False) -> dict[str, Any]:
    """Reject fabrication: docking/structure need a protocol; metrics need a split; etc."""
    contract = JS.validate_output_contract(job_type, artifact_types)
    reasons: list[str] = list(contract.get("missing", []))
    c = CONTRACTS.get(job_type, {})
    safety_class = JS.JOB_CONTRACTS.get(job_type, {}).get("safety_class")
    if safety_class == "docking" and not has_protocol:
        reasons.append("docking output without a protocol manifest is not accepted (no binding proof).")
    if safety_class in ("model_training", "evaluation") and ("metrics" in artifact_types) and not has_split:
        reasons.append("metrics without a declared split are not accepted (no fabricated metric).")
    return {"accepted": not reasons, "reasons": reasons,
            "no_binding_or_efficacy_claim": c.get("no_binding_or_efficacy_claim", True)}
