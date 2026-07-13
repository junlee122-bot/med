"""Compute-aware planning (Phase 8).

Given a compute profile, chooses a scientific method per requested capability:
a CPU substitute when no GPU is available, or a validated GPU job spec when GPU is
enabled and approved. Deterministic — works with no LLM key. An optional LLM may
*suggest* a strategy, but the route here is validated deterministically and can
never introduce shell, unsafe steps, or budget bypass.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.compute.schemas import ExecutionBackend
from app.models.schemas import SourceType, utcnow
from app.storage import db

# GPU capability → CPU substitute contract. Each entry documents what is lost
# without GPU and what a future GPU job would add.
SUBSTITUTIONS: dict[str, dict[str, Any]] = {
    "CHEMPROP_TRAIN": {
        "cpu_method": "RDKit fingerprints + scikit-learn baseline (scaffold split, bootstrap uncertainty, applicability domain)",
        "cpu_backend": ExecutionBackend.LOCAL_CPU, "gpu_job_type": "CHEMPROP_TRAIN",
        "quality_lost": "message-passing GNN capacity; larger models; faster epochs.",
        "gpu_would_add": "graph neural net accuracy on larger datasets."},
    "REINVENT4_OPTIMIZATION": {
        "cpu_method": "selection-based optimization + Pareto re-ranking + safe local enumeration (no synthesis route)",
        "cpu_backend": ExecutionBackend.LOCAL_CPU, "gpu_job_type": "REINVENT4_REINFORCEMENT_LEARNING",
        "quality_lost": "reinforcement-learning generative exploration of novel chemotypes.",
        "gpu_would_add": "learned de-novo generation beyond the seed library."},
    "GNINA_OR_VINA_GPU_SCREEN": {
        "cpu_method": "ligand-based Morgan similarity + scaffold screen + applicability (not binding proof)",
        "cpu_backend": ExecutionBackend.LOCAL_CPU, "gpu_job_type": "GNINA_SCREEN",
        "quality_lost": "structure-based docking scores / poses.",
        "gpu_would_add": "3D docking signal (still not binding proof)."},
    "BOLTZ2_OR_CHAI1_INFERENCE": {
        "cpu_method": "target structure metadata lookup + ligand-based confidence (no fabricated structure score)",
        "cpu_backend": ExecutionBackend.CONFIG_ONLY, "gpu_job_type": "BOLTZ2_INFERENCE",
        "quality_lost": "predicted co-folded structure + confidence.",
        "gpu_would_add": "structure/affinity inference (not clinical efficacy)."},
    "OPENMM_REFINEMENT": {
        "cpu_method": "protocol readiness record only (no stability claim without a real run)",
        "cpu_backend": ExecutionBackend.CONFIG_ONLY, "gpu_job_type": "OPENMM_REFINEMENT",
        "quality_lost": "MD refinement / stability estimates.",
        "gpu_would_add": "dynamics-informed refinement (not proof of stability)."},
}


def _profile_allows_gpu(profile: str) -> bool:
    return profile in ("REMOTE_GPU_ENABLED",)


def plan_compute(capabilities: dict[str, Any], requested_capabilities: list[str] | None = None,
                 workflow_run_id: str | None = None, budget_usd: float | None = None,
                 presentation_safe: bool = True) -> dict[str, Any]:
    """Produce compute decisions for each requested capability. Deterministic."""
    profile = capabilities.get("profile", "CPU_ONLY")
    gpu_ok = _profile_allows_gpu(profile)
    recorded = capabilities.get("recorded_gpu_artifacts", {})
    recorded_types = {str(value) for value in recorded.get("job_types", [])}
    requested = requested_capabilities or list(SUBSTITUTIONS.keys())
    decisions: list[dict[str, Any]] = []
    project_id = None
    if workflow_run_id:
        run = db.get("workflow_runs", workflow_run_id)
        project_id = run.get("project_id") if run else None

    for cap in requested:
        sub = SUBSTITUTIONS.get(cap)
        if not sub:
            continue
        replay_ok = profile == "RECORDED_GPU_REPLAY" and sub["gpu_job_type"] in recorded_types
        if gpu_ok:
            backend = ExecutionBackend.REMOTE_GPU
            method = f"GPU job spec: {sub['gpu_job_type']} (validated, requires approval)"
            reason = "GPU enabled and configured → validated GPU job (human approval required)."
            source_type = SourceType.GPU_CONFIGURED_NOT_RUN.value
            approval = True
            expected_quality = "GPU-grade"
            expected_latency = "minutes (GPU, queued)"
            limitations = ["GPU result requires artifact validation before use."]
        elif replay_ok:
            backend = ExecutionBackend.RECORDED_ARTIFACT
            method = f"Recorded GPU output replay for {sub['gpu_job_type']}"
            reason = "Recorded GPU artifacts available → replay (labeled, zero cost)."
            source_type = SourceType.RECORDED_GPU_OUTPUT.value
            approval = False
            expected_quality = "Recorded GPU output (not a new run)"
            expected_latency = "seconds (recorded replay)"
            limitations = ["Recorded output is reusable only for its original job type and provenance."]
        else:
            backend = sub["cpu_backend"]
            method = sub["cpu_method"]
            reason = f"No GPU available → CPU substitute. Lost: {sub['quality_lost']}"
            source_type = (SourceType.COMPUTE_FALLBACK_OUTPUT.value
                           if backend != ExecutionBackend.CONFIG_ONLY
                           else SourceType.GPU_CONFIGURED_NOT_RUN.value)
            approval = False
            expected_quality = "CPU-baseline / screening signal"
            expected_latency = "seconds-minutes (CPU)"
            limitations = ["CPU substitute is a screening/prioritization signal, not a GPU-grade result."]
        rec = {
            "id": f"cdec-{uuid.uuid4().hex[:8]}", "project_id": project_id,
            "workflow_run_id": workflow_run_id,
            "stage": cap, "requested_capability": cap, "selected_backend": backend,
            "selected_method": method, "fallback_method": sub["cpu_method"],
            "reason": reason, "expected_quality": expected_quality,
            "expected_latency": expected_latency,
            "estimated_cost": 0.0 if not gpu_ok else None,
            "human_approval_required": approval, "gpu_would_add": sub["gpu_would_add"],
            "quality_lost_without_gpu": sub["quality_lost"], "source_type": source_type,
            "limitations": limitations,
            "created_at": utcnow(),
        }
        if workflow_run_id:
            db.insert("compute_decisions", rec)
        decisions.append(rec)

    replay_selected = any(d["selected_backend"] == ExecutionBackend.RECORDED_ARTIFACT for d in decisions)
    return {
        "profile": profile, "gpu_enabled": gpu_ok, "recorded_replay_available": replay_selected,
        "decisions": decisions, "decision_count": len(decisions),
        "summary": ("All GPU tasks routed to validated CPU substitutes (no GPU present)."
                    if not gpu_ok and not replay_selected else
                    "GPU/replay routing available for selected capabilities."),
        "safety_note": ("The planner cannot add wet-lab, synthesis, dosage, or shell steps; "
                        "GPU work is an allowlisted, human-approved spec only."),
        "source_type": SourceType.HEURISTIC_ANALYSIS.value, "planned_at": utcnow(),
    }


def get_decisions(run_id: str) -> list[dict[str, Any]]:
    return db.list_records("compute_decisions", workflow_run_id=run_id, limit=500)
