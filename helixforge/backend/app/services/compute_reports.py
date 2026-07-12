"""Compute submission artifacts (Phase 8, Section 27).

Judge-facing, export-safe markdown artifacts describing the compute architecture:
CPU scientific capability, external-GPU readiness, cost/budget plan, CPU/GPU method
comparison, compute security appendix, and 'what works without GPU' / 'what GPU would
add' sheets. Every artifact passes the multilingual safety lint and embeds the
human-responsibility disclaimer.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import utcnow
from app.services import compute_evaluation
from app.services.safety_lint import lint_report
from app.storage import db

DISCLAIMER = ("연구 의사결정 보조 도구입니다. in-silico 단계이며 임상·규제 검증이 아닙니다. "
              "Research decision support only; in-silico, not clinical/regulatory validation. "
              "최종 책임은 연구자에게 있습니다.")

ARTIFACT_TYPES = [
    "cpu_scientific_capability", "external_gpu_readiness", "compute_cost_budget_plan",
    "cpu_gpu_method_comparison", "compute_security_appendix",
    "what_works_without_gpu", "what_gpu_would_add",
]


def _cpu_capability(s: dict[str, Any]) -> str:
    m = s["cpu_model_quality"]
    return f"""# CPU Scientific Capability Report

> {DISCLAIMER}

**Compute profile:** {s['compute_profile']} · GPU is an optional accelerator; CPU-only is a complete mode.

## What runs on CPU (no GPU, no LLM key)
- Dataset curation (identity/structure/label/split quality, leakage, data rights)
- CPU QSAR baselines: {m['model_count']} model(s), {m['validated_baselines']} validated baseline(s); scaffold split, bootstrap uncertainty, applicability domain
- Ligand-based screening: {s['ligand_screen']['screen_count']} screen(s) — prioritization signal, not binding proof
- Active-learning simulation: {s['active_learning']['run_count']} run(s), beats-random {s['active_learning']['beats_random']}× — oracle is held-out data, not experiments
- Multi-objective / Pareto decision policy

## Honesty
CPU baselines are not validated clinical models and are never called production-grade. No metric is fabricated; missing dependency ⇒ configured-not-run.
"""


def _gpu_readiness(s: dict[str, Any]) -> str:
    g = s["gpu_readiness"]
    return f"""# External GPU Readiness Report

> {DISCLAIMER}

**Status:** GPU workers are `CONFIGURED_NOT_RUN`. Provider configured: {g['provider_configured']}. No live/paid GPU job was run.

## Governed path
- Allowlisted job types + immutable images; no shell/command/image override.
- Per-run & per-day budget guard; human approval required before any paid job.
- Artifacts validated (checksum/type/size/path) or marked `GPU_ARTIFACT_UNVERIFIED`.
- Output validators reject fabrication (docking needs a protocol; metrics need a split).

## Workers (configured-not-run)
Chemprop, REINVENT4 (TL/RL), GNINA, Vina-GPU, Boltz-2, Chai-1, OpenMM, ESM — each with a CPU substitute.

CPU-only submission is NOT blocked by missing GPU. See docs/EXTERNAL_GPU_ARCHITECTURE.md.
"""


def _cost_plan(s: dict[str, Any]) -> str:
    from app.compute.cost_guard import costs_summary
    c = costs_summary()
    return f"""# Compute Cost & Budget Plan

> {DISCLAIMER}

- Per-run cap: ${c['run_cap_usd']} · Per-day cap: ${c['daily_cap_usd']} · Spent today: ${c['spent_today_usd']}
- Replay cost: ${c['replay_cost_usd']} (recorded compute has zero live cost)
- CPU jobs cost $0; GPU cost is estimated from a **user-configured** pricing snapshot.

> {c['disclaimer']}
"""


def _method_comparison(s: dict[str, Any]) -> str:
    e = s["compute_efficiency"]
    return f"""# CPU / GPU Method Comparison

> {DISCLAIMER}

- CPU decisions this run: {e['cpu_decisions']} · GPU jobs submitted: {e['gpu_jobs_submitted']} · avoided GPU jobs: {e['avoided_gpu_jobs']}
- Each GPU capability has a CPU substitute (see Compute-Aware Planning). GPU would add throughput/capacity, not proof of efficacy or binding.
- The value is not only accuracy: evidence traceability, standardized candidate packages, fewer unnecessary GPU jobs, easier reproduction, safer external-model use.
"""


def _security_appendix(s: dict[str, Any]) -> str:
    return f"""# Compute Security Appendix

> {DISCLAIMER}

- No arbitrary shell/image/code can reach a worker (allowlist + forbidden-field scan).
- Secrets from env only; masked in UI; redacted from logs/snapshots/exports.
- Resource caps (GPU/VRAM/runtime/output/cost); harmful objectives blocked.
- Artifacts: checksum + type/size + path-traversal protection; unverified ⇒ excluded from ranking.
- Human approval for paid jobs; kill switch (cancel job / disable provider / daily budget stop).
"""


def _artifact_body(kind: str, s: dict[str, Any]) -> str:
    if kind == "cpu_scientific_capability":
        return _cpu_capability(s)
    if kind == "external_gpu_readiness":
        return _gpu_readiness(s)
    if kind == "compute_cost_budget_plan":
        return _cost_plan(s)
    if kind == "cpu_gpu_method_comparison":
        return _method_comparison(s)
    if kind == "compute_security_appendix":
        return _security_appendix(s)
    if kind == "what_works_without_gpu":
        return _cpu_capability(s).replace("# CPU Scientific Capability Report", "# What Works Without GPU")
    if kind == "what_gpu_would_add":
        return _gpu_readiness(s).replace("# External GPU Readiness Report", "# What GPU Would Add")
    raise ValueError(f"unknown compute artifact kind: {kind}")


def generate(kind: str, run_id: str | None = None) -> dict[str, Any]:
    if kind not in ARTIFACT_TYPES:
        raise ValueError(f"kind must be one of {ARTIFACT_TYPES}")
    s = compute_evaluation.compute_summary(run_id)
    md = _artifact_body(kind, s)
    lint = lint_report(md)
    art = {"id": f"comp-art-{kind}-{uuid.uuid4().hex[:8]}", "type": kind, "kind": kind,
           "title": kind.replace("_", " ").title(), "markdown": md,
           "safety_lint": lint, "export_safe": lint["export_safe"],
           "source_type": "HEURISTIC_ANALYSIS", "created_at": utcnow()}
    db.insert("submission_artifacts", art)
    return art


def generate_all(run_id: str | None = None) -> list[dict[str, Any]]:
    return [generate(k, run_id) for k in ARTIFACT_TYPES]
