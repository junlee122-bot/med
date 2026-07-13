"""Record / replay of real agentic runs.

A successful *real* run can be captured as a named snapshot. Later the snapshot
can be replayed with NO live external calls. Replayed outputs are honestly
labeled ``RECORDED_REAL_TOOL_OUTPUT`` (never faked demo data), and reports
disclose the replay with both the original retrieval timestamp and the replay
timestamp. This is the demo-day safety net for flaky networks.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import uuid
from pathlib import Path
from typing import Any, Optional

from app.config import DATA_DIR
from app.models.schemas import SourceType, utcnow
from app.services import audit
from app.services.provenance import redact_secrets
from app.storage import db

SNAP_DIR = DATA_DIR / "snapshots"
SNAP_DIR.mkdir(parents=True, exist_ok=True)

REAL = SourceType.REAL_TOOL_OUTPUT.value
RECORDED = SourceType.RECORDED_REAL_TOOL_OUTPUT.value

REPLAY_WARNING = (
    "This is a replay of previously captured real outputs. No live external API "
    "call was made during replay."
)

# Built-in fixtures are part of the trusted application image. Pin their
# canonical payload checksum so a modified file is rejected even when the DB
# is empty and the fixture is being registered for the first time.
BUILTIN_CHECKSUMS = {
    "builtin-egfr-nsclc": "sha256:ab85a89b95a4e1dfb5587b70d7f2ca7c",
}


def _sanitize(obj: Any) -> Any:
    """Recursively redact secrets from any string in a captured payload."""
    # The shared redactor handles both nested values and sensitive dictionary
    # keys (api_key, token, password, ...). Delegating the whole object avoids
    # losing key-aware redaction while recursing here.
    return redact_secrets(obj)


def _checksum(payload: Any) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str).encode()
    return "sha256:" + hashlib.sha256(blob).hexdigest()[:32]


def _by_run(table: str, run_id: str, project_id: Optional[str]) -> list[dict]:
    return db.list_records(
        table, project_id=project_id, workflow_run_id=run_id, limit=4000
    )


def _report_for_run(report_id: Optional[str], run_id: str, project_id: Optional[str]) -> Optional[dict]:
    if not report_id:
        return None
    report = db.get("reports", report_id)
    if not report:
        return None
    if (report.get("project_id") != project_id
            or report.get("workflow_run_id") != run_id):
        return None
    return report


def _count_source_types(*lists: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for lst in lists:
        for r in lst:
            sts = r.get("source_types") or ([r.get("source_type")] if r.get("source_type") else [])
            for st in sts:
                if st:
                    counts[st] = counts.get(st, 0) + 1
    return counts


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
def create_snapshot_from_run(run_id: str, name: str, description: str = "", created_by: str = "user") -> dict[str, Any]:
    run = db.get("workflow_runs", run_id)
    if not run:
        raise ValueError("run not found")
    project_id = run.get("project_id")

    payload = {
        "run": run,
        "plan": next(iter(_by_run("agent_plans", run_id, project_id)), None),
        "agent_runs": _by_run("agent_runs", run_id, project_id),
        "tool_runs": _by_run("tool_runs", run_id, project_id),
        "audit_events": _by_run("audit_events", run_id, project_id),
        "evidence_items": _by_run("evidence_items", run_id, project_id),
        "target_candidates": _by_run("target_candidates", run_id, project_id),
        "molecule_candidates": _by_run("molecule_candidates", run_id, project_id),
        "hypotheses": _by_run("hypotheses", run_id, project_id),
        "evaluation_results": _by_run("evaluation_results", run_id, project_id),
        "revision_events": _by_run("revision_events", run_id, project_id),
        "reports": {
            "en": _report_for_run(run.get("report_id"), run_id, project_id),
            "ko": _report_for_run(run.get("ko_report_id"), run_id, project_id),
        },
        "counts": run.get("counts", {}),
        "metrics": run.get("metrics", {}),
    }
    payload = _sanitize(payload)

    snap_id = f"snap-{uuid.uuid4().hex[:10]}"
    checksum = _checksum(payload)
    st_counts = _count_source_types(payload["agent_runs"], payload["tool_runs"])
    tool_counts = {"tool_runs": len(payload["tool_runs"]), "agent_runs": len(payload["agent_runs"]),
                   "evidence": len(payload["evidence_items"]), "targets": len(payload["target_candidates"]),
                   "molecules": len(payload["molecule_candidates"])}

    storage_path = SNAP_DIR / f"{snap_id}.json"
    storage_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")

    manifest = {
        "condition": run.get("condition"), "target_query": run.get("target_query"),
        "original_run_id": run_id, "captured_at": utcnow(), "checksum": checksum,
        "tool_output_counts": tool_counts, "source_type_counts": st_counts,
    }
    snap = {
        "id": snap_id, "name": name, "description": description, "source_run_id": run_id,
        "project_id": project_id, "workflow_run_id": run_id,
        "created_at": utcnow(), "created_by": created_by,
        "condition": run.get("condition"), "target_query": run.get("target_query"),
        "tool_output_counts": tool_counts, "source_type_counts": st_counts,
        "checksum": checksum, "manifest": manifest, "storage_path": str(storage_path),
        "is_builtin": False, "notes": "Captured from a real agentic run; secrets redacted.",
    }
    db.insert("run_snapshots", snap)

    # Lightweight artifact index rows (queryable; heavy payload lives in the file).
    for etype in ("evidence_items", "target_candidates", "molecule_candidates", "agent_runs"):
        for e in payload[etype]:
            db.insert("snapshot_artifacts", {
                "id": f"sa-{snap_id}-{etype[:3]}-{e.get('id', uuid.uuid4().hex[:6])}",
                "project_id": project_id, "created_at": utcnow(), "snapshot_id": snap_id,
                "artifact_type": "entity", "entity_type": etype, "entity_id": e.get("id"),
                "source_type_original": e.get("source_type") or (e.get("source_types") or [None])[0],
                "source_type_replay": RECORDED if REAL in (e.get("source_types") or [e.get("source_type")]) else e.get("source_type"),
                "checksum": _checksum(e),
            })
    return snap


# ---------------------------------------------------------------------------
# Read
# ---------------------------------------------------------------------------
def list_snapshots() -> list[dict]:
    rows = db.list_records("run_snapshots", limit=200)
    # Discover any committed built-in snapshots on disk not yet in the DB.
    for f in sorted(SNAP_DIR.glob("builtin-*.json")):
        sid = f.stem
        if not db.get("run_snapshots", sid):
            _register_builtin(f)
    return db.list_records("run_snapshots", limit=200)


def _register_builtin(path: Path) -> Optional[dict]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    checksum = _checksum(payload)
    expected = BUILTIN_CHECKSUMS.get(path.stem)
    if expected is None or not hmac.compare_digest(expected, checksum):
        return None
    run = payload.get("run", {})
    snap = {
        "id": path.stem, "name": payload.get("_name", "Built-in EGFR/NSCLC recorded real snapshot"),
        "description": payload.get("_description", "Limited, sanitized, timestamped built-in snapshot."),
        "source_run_id": run.get("id"), "project_id": run.get("project_id"), "created_at": utcnow(),
        "created_by": "builtin", "condition": run.get("condition"), "target_query": run.get("target_query"),
        "tool_output_counts": {"agent_runs": len(payload.get("agent_runs", [])),
                               "evidence": len(payload.get("evidence_items", [])),
                               "molecules": len(payload.get("molecule_candidates", []))},
        "source_type_counts": _count_source_types(payload.get("agent_runs", []), payload.get("tool_runs", [])),
        "checksum": checksum, "manifest": {"builtin": True}, "storage_path": str(path),
        "is_builtin": True, "notes": "Built-in EGFR/NSCLC recorded real snapshot — limited, sanitized, timestamped.",
    }
    db.insert("run_snapshots", snap)
    return snap


def get_snapshot(snap_id: str) -> Optional[dict]:
    return db.get("run_snapshots", snap_id)


def _load_payload(snap: dict) -> dict:
    payload = json.loads(Path(snap["storage_path"]).read_text(encoding="utf-8"))
    expected = str(snap.get("checksum") or "")
    actual = _checksum(payload)
    if not expected or not hmac.compare_digest(expected, actual):
        raise ValueError("snapshot checksum mismatch; refusing export/replay")
    return payload


def snapshot_manifest(snap_id: str) -> dict:
    snap = get_snapshot(snap_id)
    if not snap:
        raise ValueError("snapshot not found")
    payload = _load_payload(snap)
    orig_run = payload.get("run", {})
    return {
        "snapshot_id": snap_id, "name": snap["name"], "checksum": snap["checksum"],
        "original_run_id": snap["source_run_id"], "condition": snap["condition"],
        "target_query": snap["target_query"],
        "original_started_at": orig_run.get("created_at"),
        "original_completed_at": orig_run.get("completed_at"),
        "captured_at": snap["created_at"], "is_builtin": snap.get("is_builtin", False),
        "tool_output_counts": snap["tool_output_counts"], "source_type_counts": snap["source_type_counts"],
        "replay_note": REPLAY_WARNING,
    }


def export_snapshot(snap_id: str) -> dict:
    snap = get_snapshot(snap_id)
    if not snap:
        raise ValueError("snapshot not found")
    payload = _sanitize(_load_payload(snap))  # sanitize again on export
    return {"snapshot": snap, "manifest": snapshot_manifest(snap_id), "payload": payload,
            "disclaimer": REPLAY_WARNING}


def delete_snapshot(snap_id: str) -> bool:
    snap = get_snapshot(snap_id)
    if not snap or snap.get("is_builtin"):
        return False
    try:
        Path(snap["storage_path"]).unlink(missing_ok=True)
    except Exception:
        pass
    db.delete("run_snapshots", snap_id)
    return True


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------
def _flip(st: Any) -> Any:
    if isinstance(st, list):
        return [RECORDED if x == REAL else x for x in st]
    return RECORDED if st == REAL else st


def replay_snapshot(snap_id: str) -> dict[str, Any]:
    snap = get_snapshot(snap_id)
    if not snap:
        raise ValueError("snapshot not found")
    payload = _load_payload(snap)
    replay_run_id = f"replay-{uuid.uuid4().hex[:10]}"
    replay_project_id = f"{snap.get('project_id') or 'proj'}-rp-{uuid.uuid4().hex[:6]}"
    replayed_at = utcnow()

    def clone_list(items: list[dict], run_scoped: bool) -> list[dict]:
        out = []
        for e in items:
            c = dict(e)
            c["id"] = f"{e.get('id', uuid.uuid4().hex[:6])}~{replay_run_id}"
            c["project_id"] = replay_project_id
            if run_scoped or "workflow_run_id" in c:
                c["workflow_run_id"] = replay_run_id
            if "source_type" in c:
                c["source_type"] = _flip(c["source_type"])
            if "source_types" in c:
                c["source_types"] = _flip(c["source_types"])
            c["replay_mode"] = True
            c["replayed_at"] = replayed_at
            c["original_retrieved_at"] = e.get("retrieved_at") or e.get("created_at")
            out.append(c)
        return out

    # Recreate each entity group under the replay project/run.
    def persist(table: str, items: list[dict], run_scoped: bool) -> list[dict]:
        cloned = clone_list(items, run_scoped)
        for c in cloned:
            db.insert(table, c)
        return cloned

    # These entities are run-owned in the current schema. Older/built-in
    # snapshots predate workflow_run_id, so force the replay run id instead of
    # leaving their rows unscoped and invisible to exact-run queries.
    evidence = persist("evidence_items", payload.get("evidence_items", []), True)
    targets = persist("target_candidates", payload.get("target_candidates", []), True)
    molecules = persist("molecule_candidates", payload.get("molecule_candidates", []), True)
    hypotheses = persist("hypotheses", payload.get("hypotheses", []), True)
    agent_runs = persist("agent_runs", payload.get("agent_runs", []), True)
    persist("tool_runs", payload.get("tool_runs", []), True)
    evaluation = persist("evaluation_results", payload.get("evaluation_results", []), True)
    revisions = persist("revision_events", payload.get("revision_events", []), True)

    plan = payload.get("plan")
    if plan:
        plan = {**plan, "id": f"plan-{replay_run_id}", "workflow_run_id": replay_run_id, "project_id": replay_project_id}
        db.insert("agent_plans", plan)

    # Reports: keep original real content, prepend a replay disclosure banner.
    metrics = payload.get("metrics", {})
    orig_run = payload.get("run", {})
    report_ids = {}
    for key, lang in (("en", "en_technical"), ("ko", "ko_judge")):
        rep = (payload.get("reports") or {}).get(key)
        if not rep:
            continue
        rid = f"rep-{key}-{replay_run_id}"
        banner = (
            f"> **RECORDED REPLAY.** {REPLAY_WARNING}\n"
            f"> Original run: `{orig_run.get('id')}` retrieved {orig_run.get('created_at')} · "
            f"replayed {replayed_at}.\n\n"
        )
        db.insert("reports", {
            "id": rid, "project_id": replay_project_id, "created_at": replayed_at,
            "workflow_run_id": replay_run_id, "type": rep.get("type", lang),
            "title": (rep.get("title", "Report") + " (recorded replay)"),
            "markdown": banner + rep.get("markdown", ""), "language": rep.get("language", key),
            "safety_lint": rep.get("safety_lint"), "export_safe": rep.get("export_safe", True),
            "source_type": RECORDED, "replay_mode": True, "replayed_at": replayed_at,
            "original_retrieved_at": orig_run.get("created_at"),
        })
        report_ids[key] = rid

    counts = {}
    for st, n in (payload.get("counts") or {}).items():
        counts[_flip(st)] = counts.get(_flip(st), 0) + n

    steps = [{"step": r.get("stage"), "agent": r.get("agent_name"), "status": r.get("status"),
              "source_type": (r.get("source_types") or [RECORDED])[0], "summary": r.get("output_summary")}
             for r in agent_runs]

    db.insert("workflow_runs", {
        "id": replay_run_id, "project_id": replay_project_id, "created_at": replayed_at,
        "status": orig_run.get("status", "complete"), "kind": "agentic_replay",
        "completed_at": replayed_at, "condition": snap["condition"], "target_query": snap["target_query"],
        "counts": counts, "metrics": metrics, "report_id": report_ids.get("en"),
        "ko_report_id": report_ids.get("ko"), "replay_of_snapshot": snap_id,
        "original_run_id": orig_run.get("id"), "original_retrieved_at": orig_run.get("created_at"),
    })
    audit.record_event(event_type="replay", agent_name="Snapshot Replayer",
                       source_type=SourceType.RECORDED_REAL_TOOL_OUTPUT,
                       input_summary=f"snapshot {snap_id}", output_summary=REPLAY_WARNING,
                       project_id=replay_project_id, workflow_run_id=replay_run_id)

    return {
        "run_id": replay_run_id, "project_id": replay_project_id,
        "status": orig_run.get("status", "complete"), "mode": "RECORDED_REPLAY",
        "snapshot_id": snap_id, "replayed_at": replayed_at,
        "original_run_id": orig_run.get("id"), "original_retrieved_at": orig_run.get("created_at"),
        "agent_runs": agent_runs, "plan": plan, "steps": steps,
        "revision_events": revisions, "counts": counts, "metrics": metrics,
        "report_id": report_ids.get("en"), "ko_report_id": report_ids.get("ko"),
        "warning": REPLAY_WARNING,
        "disclaimer": ("This system is research decision support only. Final responsibility "
                       "belongs to the human research team."),
    }
