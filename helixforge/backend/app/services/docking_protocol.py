"""Docking protocol governance — honest capture, never binding proof.

Records an AutoDock Vina docking attempt as a *governed protocol record* with an
explicit, honest validation checklist (receptor/ligand preparation, redocking,
decoy enrichment, scoring status). Docking here is treated strictly as a
PRIORITIZATION signal, never as evidence that a ligand binds the target.

This module deliberately does NOT emit receptor-preparation instructions,
wet-lab protocols, or synthesis content, and it never fabricates a docking
score. Scores are only carried through when they are supplied by a real
tool/fixture run; otherwise the record is labelled as configured-but-not-run.
"""
from __future__ import annotations

import uuid
from typing import Any

from app.models.schemas import SourceType, utcnow
from app.storage import db

# ---------------------------------------------------------------------------
# Protocol modes (module constants)
# ---------------------------------------------------------------------------
FIXTURE_ONLY = "FIXTURE_ONLY"                    # illustrative fixture, heuristic
JOB_SPEC_ONLY = "JOB_SPEC_ONLY"                  # parameters recorded, nothing run
REAL_VINA_FIXTURE_RUN = "REAL_VINA_FIXTURE_RUN"  # real Vina executed on a fixture
NOT_CONFIGURED = "NOT_CONFIGURED"                # tool not configured / not run
FUTURE_FULL_DOCKING = "FUTURE_FULL_DOCKING"      # planned, not implemented here

_DOCKING_TOOL = "AutoDock Vina"

# Always-present honest limitations. Phrased to never contain the banned
# substrings "binding proof" / "binding confirmed".
_BASE_LIMITATIONS = [
    "Docking is a prioritization signal only; it is not evidence that a ligand "
    "binds the target and does not establish binding.",
    "Receptor and ligand preparation are NOT performed in this module; parameters "
    "are recorded for governance and review only.",
    "In-silico docking scores are not experimental affinities and require "
    "expert review plus orthogonal validation before any conclusion.",
]


def _prep_status(mode: str) -> str:
    """Receptor/ligand preparation status.

    Defaults to NOT_PERFORMED unless the mode indicates a real run, in which
    case preparation was provided externally (by the fixture), never here.
    """
    return "PROVIDED_IN_FIXTURE" if mode == REAL_VINA_FIXTURE_RUN else "NOT_PERFORMED"


def _source_type(mode: str, score: float | None) -> str:
    """Provenance label — honest, never over-claimed."""
    if mode == REAL_VINA_FIXTURE_RUN and score is not None:
        return SourceType.REAL_TOOL_OUTPUT.value
    if mode == FIXTURE_ONLY:
        return SourceType.HEURISTIC_ANALYSIS.value
    # NOT_CONFIGURED / JOB_SPEC_ONLY / FUTURE_FULL_DOCKING, or a real-run mode
    # that produced no score: nothing was actually run to completion.
    return SourceType.CONFIGURED_BUT_NOT_RUN.value


def create_protocol(
    run_id: str | None = None,
    receptor_identifier: str | None = None,
    box_center: list | None = None,
    box_size: list | None = None,
    exhaustiveness: int | None = None,
    mode: str = NOT_CONFIGURED,
    score: float | None = None,
) -> dict[str, Any]:
    """Build (and persist) a governed docking protocol record.

    Returns a DockingProtocolRecord dict. Never fabricates a score, never emits
    preparation or synthesis instructions, and never labels docking as binding
    evidence.
    """
    real_run = mode == REAL_VINA_FIXTURE_RUN
    has_box = bool(box_center) and bool(box_size)

    prep = _prep_status(mode)
    scoring_status = "NO_SCORE" if score is None else "FIXTURE_SCORE"

    # Redocking / decoy validation are NOT_PERFORMED unless a real run explicitly
    # provides them. There is no parameter to provide them here, so they remain
    # honestly NOT_PERFORMED in every case.
    redocking_validation_status = "NOT_PERFORMED"
    decoy_validation_status = "NOT_PERFORMED"

    receptor_source = "FIXTURE" if mode in (FIXTURE_ONLY, REAL_VINA_FIXTURE_RUN) else "NOT_SPECIFIED"
    binding_site_definition = (
        "Defined by explicit grid box (center + size)." if has_box
        else "NOT_DEFINED — no grid box provided."
    )

    record: dict[str, Any] = {
        "id": f"docking-protocol-{uuid.uuid4().hex[:8]}",
        "run_id": run_id,
        "protocol_id": f"DOCKPROT-{uuid.uuid4().hex[:6].upper()}",
        "docking_tool": _DOCKING_TOOL,
        "receptor_source": receptor_source,
        "receptor_identifier": receptor_identifier,
        "receptor_preparation_status": prep,
        "ligand_preparation_status": prep,
        "binding_site_definition": binding_site_definition,
        "box_center": box_center,
        "box_size": box_size,
        "exhaustiveness": exhaustiveness,
        "control_ligands": [],
        "redocking_validation_status": redocking_validation_status,
        "decoy_validation_status": decoy_validation_status,
        "scoring_status": scoring_status,
        "limitations": list(_BASE_LIMITATIONS),
        "source_type": _source_type(mode, score),
        "expert_review_status": "PENDING_EXPERT_REVIEW",
        "created_at": utcnow(),
    }

    try:
        db.insert("docking_protocols", record)
    except Exception:  # pragma: no cover - persistence is best-effort
        pass
    return record


def lint_protocol(record: dict) -> dict[str, Any]:
    """Honest checklist lint over a protocol record.

    Returns {status, findings, checked_at}. A score without a defined binding
    box, or any over-claim of binding, is BLOCKED; an un-prepared receptor
    alongside a score is REVIEW_REQUIRED; an honest not-run record PASSes.
    """
    findings: list[dict[str, str]] = []

    scoring_status = record.get("scoring_status")
    has_score = scoring_status not in (None, "NO_SCORE")
    box_center = record.get("box_center")
    box_size = record.get("box_size")

    # A score without a defined binding site/box is not trustworthy.
    if has_score and (not box_center or not box_size):
        findings.append({
            "severity": "BLOCK",
            "detail": "A docking score is present but box_center/box_size is "
                      "missing — a score without a defined binding site is not trustworthy.",
        })

    # A score against an un-prepared receptor needs expert review.
    if has_score and record.get("receptor_preparation_status") == "NOT_PERFORMED":
        findings.append({
            "severity": "REVIEW",
            "detail": "A score is present while receptor preparation is "
                      "NOT_PERFORMED — expert review required before use.",
        })

    # Scan any free-text claim field for over-claims of binding.
    claim = str(record.get("claim", "")).lower()
    if "binding proof" in claim or "binding confirmed" in claim:
        findings.append({
            "severity": "BLOCK",
            "detail": "Record claims binding is proven/confirmed — docking is a "
                      "prioritization signal only and cannot establish binding.",
        })

    if any(f["severity"] == "BLOCK" for f in findings):
        status = "BLOCKED"
    elif any(f["severity"] == "REVIEW" for f in findings):
        status = "REVIEW_REQUIRED"
    else:
        status = "PASS"

    return {"status": status, "findings": findings, "checked_at": utcnow()}


def generate_job_spec(
    receptor_identifier: str,
    box_center: list,
    box_size: list,
    exhaustiveness: int = 8,
) -> dict[str, Any]:
    """Return a benign docking job SPECIFICATION (parameters only).

    Contains no preparation, wet-lab, or synthesis instructions — only the
    numeric search-space parameters. Execution is left to qualified users.
    """
    return {
        "docking_tool": _DOCKING_TOOL,
        "receptor_identifier": receptor_identifier,
        "box_center": box_center,
        "box_size": box_size,
        "exhaustiveness": exhaustiveness,
        "note": "Parameter specification only; receptor/ligand preparation and "
                "execution are performed by qualified users with appropriate tools.",
        "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
    }


def _first_real_score(jobs: list[dict]) -> tuple[float, dict] | None:
    """Find the best real docking score among jobs, or None.

    Only considers jobs explicitly labelled REAL_TOOL_OUTPUT with an actual
    numeric score present. Never fabricates a score.
    """
    real = SourceType.REAL_TOOL_OUTPUT.value
    for j in jobs:
        if j.get("source_type") != real:
            continue
        numeric = [s for s in (j.get("scores") or []) if isinstance(s, (int, float))]
        if numeric:
            return min(numeric), j
        sc = j.get("score")
        if isinstance(sc, (int, float)):
            return sc, j
    return None


def run(run_id: str | None = None) -> dict[str, Any]:
    """Inspect docking_jobs for a run and build a governed protocol + lint.

    Builds a REAL_VINA_FIXTURE_RUN protocol only when a real fixture score
    actually exists; otherwise records an honest NOT_CONFIGURED protocol.
    """
    runs = db.list_records("workflow_runs", limit=200)
    run_rec = db.get("workflow_runs", run_id) if run_id else (runs[0] if runs else {})
    run_rec = run_rec or {}
    pid = run_rec.get("project_id")
    jobs = (
        db.list_records("docking_jobs", project_id=pid, limit=200)
        if pid else db.list_records("docking_jobs", limit=200)
    )

    hit = _first_real_score(jobs)
    if hit is not None:
        score, job = hit
        protocol = create_protocol(
            run_id=run_rec.get("id"),
            receptor_identifier=job.get("receptor_identifier") or job.get("receptor_fixture"),
            box_center=job.get("box_center") or job.get("center"),
            box_size=job.get("box_size"),
            exhaustiveness=job.get("exhaustiveness"),
            mode=REAL_VINA_FIXTURE_RUN,
            score=score,
        )
    else:
        protocol = create_protocol(run_id=run_rec.get("id"), mode=NOT_CONFIGURED)

    lint = lint_protocol(protocol)
    return {
        "run_id": run_rec.get("id"),
        "protocol": protocol,
        "lint": lint,
        "checked_at": utcnow(),
    }
