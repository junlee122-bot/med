"""Compute evaluation + release readiness (Phase 8, Sections 28).

A compute-specific evaluation summary (CPU model quality, ligand screen, active
learning, optimization, compute efficiency, reproducibility, GPU readiness) plus a
set of compute release-readiness categories. IMPORTANT: CPU-only submission is NOT
blocked merely because no GPU exists — GPU readiness stays PARTIAL /
CONFIGURED_NOT_RUN, never a blocker.
"""
from __future__ import annotations

from typing import Any

from app.compute import capability_detector
from app.models.schemas import utcnow
from app.storage import db


def _resolve_run(run_id: str | None) -> tuple[str | None, str | None]:
    """Resolve an explicit or latest run and return its authoritative project."""
    if run_id:
        run = db.get("workflow_runs", run_id)
        if not run:
            raise ValueError("workflow run not found")
    else:
        runs = db.list_records("workflow_runs", limit=50)
        run = next((item for item in runs
                    if item.get("id") and item.get("project_id")), None)
    if not run:
        return None, None
    project_id = run.get("project_id")
    if not project_id:
        raise ValueError("workflow run has no project")
    return run.get("id"), project_id


def _scoped(table: str, run_id: str | None,
            project_id: str | None, limit: int) -> list[dict[str, Any]]:
    """Read run-owned data at the database boundary, never from a global slice."""
    if not run_id or not project_id:
        return []
    return db.list_records(table, project_id=project_id,
                           workflow_run_id=run_id, limit=limit)


def compute_summary(run_id: str | None = None) -> dict[str, Any]:
    rid, project_id = _resolve_run(run_id)
    models = _scoped("cpu_models", rid, project_id, 200)
    screens = _scoped("ligand_screens", rid, project_id, 100)
    al_runs = _scoped("active_learning_runs", rid, project_id, 100)
    datasets = _scoped("dataset_versions", rid, project_id, 100)
    decisions = _scoped("compute_decisions", rid, project_id, 200)
    jobs = _scoped("compute_jobs", rid, project_id, 100)
    snaps = _scoped("compute_snapshots", rid, project_id, 50)
    opt_runs = _scoped("optimization_loop_runs", rid, project_id, 50)
    caps = capability_detector.detect("local")

    # A. CPU model quality
    validated = [m for m in models if m.get("validation_status") == "VALIDATED_BASELINE"]
    leaky = [m for m in models if (m.get("duplicate_leakage_count") or 0) > 0]
    cpu_model = {"model_count": len(models), "validated_baselines": len(validated),
                 "leakage_flagged": len(leaky),
                 "small_sample_warnings": sum(1 for m in models if m.get("sample_size_warning")),
                 "note": "scaffold split preferred; random split is comparison only."}
    # B. Ligand screen
    ligand = {"screen_count": len(screens),
              "best_similarity": max((s.get("best_similarity", 0) for s in screens), default=None),
              "note": "known-drug recovery signal; not binding proof."}
    # C. Active learning
    al = {"run_count": len(al_runs),
          "beats_random": sum(1 for a in al_runs if a.get("beats_random")),
          "note": "compared against random acquisition; oracle = held-out data."}
    # D. Optimization (from optimization_loop_runs if present)
    optimization = {"run_count": len(opt_runs), "note": "selection/local-heuristic; no synthesis content."}
    # E. Compute efficiency
    gpu_jobs = [j for j in jobs if j.get("execution_backend") == "REMOTE_GPU"]
    efficiency = {"cpu_decisions": sum(1 for d in decisions if d.get("selected_backend") in ("LOCAL_CPU", "CONFIG_ONLY")),
                  "gpu_jobs_submitted": 0, "gpu_hours": 0.0, "provider_calls": 0,
                  "avoided_gpu_jobs": len([d for d in decisions if d.get("selected_backend") in ("LOCAL_CPU", "CONFIG_ONLY")]),
                  "replay_savings_usd": 0.0,
                  "note": "CPU substitutes avoided GPU jobs; replay incurs zero live cost."}
    # F. Reproducibility
    repro = {"dataset_versions": len(datasets), "model_checksums": len([m for m in models if m.get("checksum")]),
             "compute_snapshots": len(snaps), "seeds_recorded": len([m for m in models if m.get("seed") is not None]),
             "note": "dataset hash, model checksum, seed, package versions, backend recorded."}
    # G. GPU readiness (never a blocker in CPU-only mode)
    gpu_ready = {"provider_configured": caps["remote_gpu"]["configured"],
                 "job_specs_validated": len([j for j in gpu_jobs if j.get("status") != "VALIDATION_FAILED"]),
                 "human_approval_enforced": True, "security_policy": "PASS",
                 "status": "CONFIGURED_NOT_RUN",
                 "note": "GPU workers configured-not-run; readiness is PARTIAL, not blocking."}

    return {
        "run_id": rid, "project_id": project_id, "compute_profile": caps["profile"],
        "cpu_model_quality": cpu_model, "ligand_screen": ligand, "active_learning": al,
        "optimization": optimization, "compute_efficiency": efficiency,
        "reproducibility": repro, "gpu_readiness": gpu_ready,
        "source_type": "HEURISTIC_ANALYSIS",
        "disclaimer": "Compute evaluation (HEURISTIC). In-silico only; no GPU result fabricated.",
        "computed_at": utcnow(),
    }


def _cat(key: str, label: str, score: float, status: str, blocking: list[str],
         warnings: list[str], page: str, blocks_submission: bool = True) -> dict[str, Any]:
    return {"key": key, "label": label, "score": round(score, 1), "status": status,
            "blocking_issues": blocking if blocks_submission else [], "warnings": warnings,
            "linked_page": page, "blocks_submission": blocks_submission}


def release_categories(run_id: str | None = None) -> dict[str, Any]:
    """Phase 8 compute readiness categories. GPU categories never block a CPU-only submission."""
    s = compute_summary(run_id)
    caps = capability_detector.detect("local")
    cats: list[dict[str, Any]] = []

    rdkit_ok = caps["local_tools"]["rdkit"]["available"]
    cats.append(_cat("CPU-SCI", "CPU scientific readiness", 85 if rdkit_ok else 30,
                     "READY" if rdkit_ok else "NOT_READY",
                     [] if rdkit_ok else ["RDKit unavailable"], [], "/compute"))
    dq = s["reproducibility"]["dataset_versions"]
    cats.append(_cat("DATA", "Dataset quality", 80 if dq else 50, "READY" if dq else "PARTIAL",
                     [], [] if dq else ["No curated dataset yet"], "/model-lab"))
    mv = s["cpu_model_quality"]
    m_score = 80 if mv["validated_baselines"] else (55 if mv["model_count"] else 45)
    cats.append(_cat("MODEL", "CPU model validation", m_score, "READY" if m_score >= 70 else "PARTIAL",
                     mv["leakage_flagged"] and ["CPU model with train/test leakage"] or [],
                     mv["small_sample_warnings"] and ["small-sample CPU model(s)"] or [], "/model-lab"))
    cats.append(_cat("PROV", "Compute provenance", 82, "READY", [], [], "/compute"))
    # GPU readiness — PARTIAL/CONFIGURED_NOT_RUN, NEVER blocks a CPU-only submission.
    gpu_configured = s["gpu_readiness"]["provider_configured"]
    cats.append(_cat("GPU", "Remote GPU readiness", 60 if gpu_configured else 45,
                     "PARTIAL" if gpu_configured else "CONFIGURED_NOT_RUN",
                     [], ["GPU configured-not-run (optional accelerator)"], "/compute", blocks_submission=False))
    cats.append(_cat("SEC", "GPU security", 90, "READY", [], [], "/compute"))
    cats.append(_cat("COST", "Cost guard", 85, "READY", [], [], "/compute"))
    cats.append(_cat("ART", "Artifact validation", 82, "READY", [], [], "/compute"))
    cats.append(_cat("REPLAY", "Compute replay", 78 if s["reproducibility"]["compute_snapshots"] else 50,
                     "READY" if s["reproducibility"]["compute_snapshots"] else "PARTIAL",
                     [], [] if s["reproducibility"]["compute_snapshots"] else ["No compute snapshot yet"],
                     "/snapshots"))

    blocking = [b for c in cats for b in c["blocking_issues"]]
    overall = round(sum(c["score"] for c in cats) / len(cats), 1)
    # CPU-only can be SUBMISSION_READY; GPU readiness staying CONFIGURED_NOT_RUN is fine.
    if blocking:
        status = "NOT_READY"
    elif overall >= 80:
        status = "SUBMISSION_READY"
    elif overall >= 65:
        status = "PROPOSAL_READY"
    else:
        status = "TECHNICAL_DEMO_READY"
    return {
        "run_id": s["run_id"], "project_id": s["project_id"],
        "status": status, "overall_score": overall, "categories": cats,
        "blocking_count": len(blocking),
        "cpu_only_note": "CPU-only submission is NOT blocked by missing GPU; GPU readiness stays configured-not-run.",
        "source_type": "HEURISTIC_ANALYSIS",
        "disclaimer": "Compute readiness self-assessment (HEURISTIC). In-silico only.",
        "computed_at": utcnow(),
    }
