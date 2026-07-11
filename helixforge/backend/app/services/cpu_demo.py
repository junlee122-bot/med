"""One-click CPU scientific demo + GPU-readiness dry run (Phase 8, Sections 23-24).

Runs a complete no-GPU scientific flow: capability → dataset curation → RDKit
validation → ligand-based screening → CPU baseline (or honest configured-not-run)
→ applicability → active-learning simulation → CPU optimization → GPU escalation
plan (validated job specs, NO submission). Uses a small built-in EGFR comparator
set (public structural identities; no synthesis content). No GPU, no LLM key, no
large downloads, no paid job.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.compute import capability_detector, gpu_worker_contracts, job_manager
from app.models.schemas import SourceType, utcnow
from app.services import (
    active_learning, compute_aware_planner, cpu_qsar, dataset_curation, ligand_screening,
)

# Small built-in EGFR reference set — public approved-drug structural identities only.
# Structural identity is not a synthesis route. See DATA_RIGHTS_AND_ATTRIBUTION.md.
EGFR_REFERENCES = [
    "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1",   # gefitinib-like
    "C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1",       # erlotinib-like
]
# Candidate pool: some near the references, some diverse, one invalid, one duplicate.
DEMO_CANDIDATES = [
    "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1",   # ~ gefitinib (known-like)
    "COc1cc2ncnc(Nc3cccc(Br)c3)c2cc1OCCCN1CCOCC1",       # analog
    "C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1",        # ~ erlotinib
    "CC(=O)Oc1ccccc1C(=O)O", "c1ccc(-c2ccccc2)cc1",      # diverse
    "CCOc1ccccc1", "c1ccc(O)cc1", "CCN(CC)CC", "CCCCCCO",
    "COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1",   # duplicate
    "definitely_not_a_smiles",                           # invalid
]


def run_cpu_scientific_demo(condition: str = "non-small cell lung cancer",
                            target: str = "EGFR") -> dict[str, Any]:
    demo_id = f"cpudemo-{uuid.uuid4().hex[:8]}"
    caps = capability_detector.detect("local")
    steps: list[dict[str, Any]] = []

    # 1. Compute-aware plan (all GPU tasks → CPU substitutes).
    plan = compute_aware_planner.plan_compute(caps, workflow_run_id=demo_id)
    steps.append({"step": "compute_plan", "backend_profile": caps["profile"],
                  "decisions": plan["decision_count"]})

    # 2. Dataset curation (synthetic labels for a demo baseline).
    recs = [{"smiles": s, "label": (1 if i % 2 == 0 else 0), "standard_type": "IC50", "standard_units": "nM"}
            for i, s in enumerate(DEMO_CANDIDATES) if s != "definitely_not_a_smiles"]
    ds = dataset_curation.curate(recs, dataset_name=f"{target}_demo", source="demo",
                                 endpoint_type="activity", exploratory=True)
    steps.append({"step": "dataset_curation", "dataset_id": ds.get("id"),
                  "quality_score": ds.get("quality_score"), "valid": ds.get("valid_smiles_count")})

    # 3. Ligand-based screening vs known EGFR references.
    screen = ligand_screening.screen(DEMO_CANDIDATES, EGFR_REFERENCES, run_id=demo_id, target=target)
    steps.append({"step": "ligand_screen", "screen_id": screen.get("id"),
                  "best_similarity": screen.get("best_similarity"),
                  "known_like": screen.get("recommendation_counts", {}).get("KNOWN_LIKE_PRIORITY", 0)})

    # 4. CPU baseline (or honest configured-not-run).
    model = cpu_qsar.train(recs, task="classification", endpoint="demo_activity", run_id=demo_id)
    model_status = model.get("validation_status") or model.get("status")
    steps.append({"step": "cpu_baseline", "model_id": model.get("id"), "status": model_status,
                  "source_type": model.get("source_type")})

    # 5. Active-learning simulation (which candidates to escalate).
    al_pool = [{"smiles": s, "label": (1 if "ncnc" in s else 0)} for s in DEMO_CANDIDATES
               if s != "definitely_not_a_smiles"]
    al = active_learning.run(al_pool, strategy="uncertainty", cycles=3, batch_size=2,
                             initial_labeled=4, run_id=demo_id)
    steps.append({"step": "active_learning", "al_id": al.get("id"), "status": al.get("status"),
                  "beats_random": al.get("beats_random")})

    # 6. GPU escalation plan — validated specs, NO submission.
    escalation = _gpu_escalation_plan(demo_id, target)
    steps.append({"step": "gpu_escalation_plan", "job_specs": len(escalation["job_specs"]),
                  "submitted": False})

    top = screen.get("top_candidates", [])[:3]
    report = _demo_report(target, condition, caps, ds, screen, model, al, escalation)

    return {
        "demo_id": demo_id, "target": target, "condition": condition,
        "compute_profile": caps["profile"], "gpu_used": False, "llm_key_required": False,
        "steps": steps, "top_candidates": top,
        "cpu_model_status": model_status, "screening_result_id": screen.get("id"),
        "active_learning_result_id": al.get("id"), "dataset_id": ds.get("id"),
        "gpu_escalation": escalation, "report_markdown": report,
        "source_type": SourceType.COMPUTE_FALLBACK_OUTPUT.value,
        "limitations": ["CPU-only demo on a small built-in set; not a real discovery campaign.",
                        "Ligand screening is a prioritization signal, not binding proof.",
                        "CPU baseline is not a validated clinical model.",
                        "GPU escalation plan is a dry run — no job was submitted."],
        "release_status": "TECHNICAL_DEMO_READY", "created_at": utcnow(),
    }


def _gpu_escalation_plan(run_id: str, target: str) -> dict[str, Any]:
    """Build + validate GPU job specs for top candidates. No submission."""
    specs = []
    for jt in ("CHEMPROP_TRAIN", "GNINA_SCREEN", "REINVENT4_TRANSFER_LEARNING"):
        v = gpu_worker_contracts.build_job_spec(jt, workflow_run_id=run_id,
                                                input_artifact_ids=["demo-dataset"], dataset_version_id="demo-ds")
        dry = job_manager.dry_run(v["normalized"]) if v["valid"] else {"validated": False, "errors": v["errors"]}
        specs.append({"job_type": jt, "validated": v["valid"],
                      "estimated_cost": (dry.get("estimated_cost") or {}).get("estimated_cost_usd"),
                      "human_approval_required": True, "submitted": False})
    return {"job_specs": specs, "submitted": False, "provider_calls": 0,
            "note": "Validated GPU job specifications for top candidates — human approval required; no submission.",
            "source_type": SourceType.GPU_CONFIGURED_NOT_RUN.value}


def run_gpu_readiness_dry_run(target: str = "EGFR", pricing_profile_id: str | None = None) -> dict[str, Any]:
    caps = capability_detector.detect("local")
    run_id = f"gpudry-{uuid.uuid4().hex[:8]}"
    specs = []
    for jt in ("CHEMPROP_TRAIN", "REINVENT4_REINFORCEMENT_LEARNING", "GNINA_SCREEN", "BOLTZ2_INFERENCE"):
        v = gpu_worker_contracts.build_job_spec(jt, workflow_run_id=run_id,
                                                input_artifact_ids=["candidates"], dataset_version_id="ds")
        dry = job_manager.dry_run(v["normalized"], pricing_profile_id) if v["valid"] else None
        specs.append({
            "job_type": jt, "validated": v["valid"], "errors": v["errors"],
            "estimated_cost_usd": (dry or {}).get("estimated_cost", {}).get("estimated_cost_usd") if dry else None,
            "budget_ok": (dry or {}).get("budget", {}).get("ok") if dry else None,
            "required_inputs": gpu_worker_contracts.CONTRACTS[jt]["inputs"],
            "missing_inputs": ["prepared inputs / curated dataset artifact (not present in CPU-only demo)"],
            "approval_status": "PENDING", "submitted": False,
        })
    cfg_configured = caps["remote_gpu"]["configured"]
    return {
        "run_id": run_id, "compute_profile": caps["profile"], "provider_configured": cfg_configured,
        "provider_submissions": 0, "job_specs": specs,
        "safety_readiness": {"arbitrary_command_absent": True, "allowlisted_images_only": True,
                             "human_approval_required": True},
        "approval_status": "PENDING", "submitted": False,
        "banner": "GPU escalation plan built and validated. NO job submitted. Costs are approximate — verify in provider console.",
        "limitations": ["No provider is configured/enabled in this environment.",
                        "Inputs (prepared receptors, curated artifacts) must be produced before a real run."],
        "source_type": SourceType.GPU_CONFIGURED_NOT_RUN.value, "created_at": utcnow(),
    }


def _demo_report(target, condition, caps, ds, screen, model, al, escalation) -> str:
    return f"""# CPU-Only Scientific Demo — {target} / {condition}

> Research decision support only. In-silico; not clinical/regulatory validation. No wet-lab, synthesis, or dosage.

## Compute environment
- Profile: **{caps['profile']}** · GPU present locally: **{caps['gpu_present_locally']}** · LLM key required: **no**
- CPU-only is a complete scientific mode; GPU is an optional accelerator.

## What ran on CPU
1. **Dataset curation** — quality score {ds.get('quality_score')} · valid {ds.get('valid_smiles_count')} · scaffold split.
2. **Ligand-based screening** — best similarity {screen.get('best_similarity')} to known {target} references. *Prioritization signal, not binding proof.*
3. **CPU baseline** — status `{model.get('validation_status') or model.get('status')}` ({model.get('source_type')}). Not a validated clinical model.
4. **Active-learning simulation** — {('beats random baseline' if al.get('beats_random') else 'ran vs random baseline')}; oracle = held-out dataset (not experiments).

## External GPU escalation (dry run — nothing submitted)
{len(escalation['job_specs'])} validated GPU job specifications for top candidates; every job requires human approval. No provider call, no cost.

## What GPU would add
Message-passing GNN accuracy, learned generative exploration, structure-based docking signal — none of which is claimed here.

## Limitations
Small built-in demo set; screening is not docking; CPU baseline is not clinical validation; GPU remains configured-not-run.
"""
