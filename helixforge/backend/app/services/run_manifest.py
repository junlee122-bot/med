"""Reproducibility manifest for a workflow run."""
from __future__ import annotations

import platform
import subprocess
from importlib import metadata
from typing import Any

from app.adapters import registry as reg
from app.config import get_settings
from app.models.schemas import utcnow
from app.services.provenance import redact_secrets
from app.storage import db

KEY_PACKAGES = ["fastapi", "starlette", "pydantic", "httpx", "rdkit", "PyTDC"]


def _pkg_versions() -> dict[str, str]:
    out = {}
    for p in KEY_PACKAGES:
        try:
            out[p] = metadata.version(p)
        except Exception:
            out[p] = "not installed"
    return out


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], stderr=subprocess.DEVNULL,
                                       timeout=3).decode().strip()
    except Exception:
        return "unknown"


def build_manifest(run_id: str) -> dict[str, Any]:
    s = get_settings()
    run = db.get("workflow_runs", run_id) or {}
    project_id = run.get("project_id")
    tool_health = []
    for h in reg.health_all():
        tool_health.append({"tool": h.tool_id, "status": h.status.value, "mode": h.mode})
    counts = run.get("counts", {})
    manifest = {
        "run_id": run_id, "project_id": project_id, "app_version": s.app_version,
        "git_commit": _git_commit(), "python_version": platform.python_version(),
        "package_versions": _pkg_versions(),
        "configured_tools": {"vina_bin": bool(s.vina_bin), "reinvent4": bool(s.reinvent4_python or s.reinvent4_bin),
                             "ncbi_api_key": bool(s.ncbi_api_key), "ncbi_email": bool(s.ncbi_email)},
        "tool_health": tool_health,
        "condition": run.get("condition"), "target_query": run.get("target_query"),
        "source_counts": counts,
        "evidence_count": db.count("evidence_items", project_id),
        "target_count": db.count("target_candidates", project_id),
        "molecule_count": db.count("molecule_candidates", project_id),
        "agent_run_count": db.count("agent_runs", project_id),
        "revision_count": db.count("revision_events", project_id),
        "started_at": run.get("created_at"), "completed_at": run.get("completed_at"),
        "generated_at": utcnow(),
        "disclaimer": "Research decision support only. Final responsibility belongs to the human research team.",
    }
    db.insert("run_manifests", {"id": f"man-{run_id}", "project_id": project_id, "created_at": utcnow(), **manifest})
    return {k: (redact_secrets(v) if isinstance(v, str) else v) for k, v in manifest.items()}
