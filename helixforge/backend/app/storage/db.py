"""Lightweight SQLite persistence.

One table per entity: (id, project_id, created_at, payload JSON). This keeps the
storage layer trivial to run (no server, no migrations) while remaining
Postgres-portable — the same insert/get/list/count surface maps onto a JSONB
column in Postgres. Every tool call persists a ToolRun and an AuditEvent.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings

_LOCK = threading.RLock()
_CONN: Optional[sqlite3.Connection] = None
_SCHEMA_READY = False

ENTITIES = [
    "projects",
    "workflow_runs",
    "tool_runs",
    "audit_events",
    "evidence_items",
    "target_candidates",
    "molecule_candidates",
    "docking_jobs",
    "reinvent_jobs",
    "tdc_dataset_records",
    "safety_flags",
    "reports",
    # --- Phase 2: agentic layer ---
    "agent_runs",
    "agent_plans",
    "revision_events",
    "hypotheses",
    "evaluation_results",
    "run_manifests",
    # --- Phase 3: submission-grade hardening ---
    "run_snapshots",
    "snapshot_artifacts",
    "ai_interactions",
    "scenario_runs",
    "run_configs",
    "regulatory_docs",
    "submission_artifacts",
]


def _connect() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        db_path = get_settings().db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _CONN = sqlite3.connect(db_path, check_same_thread=False)
        _CONN.row_factory = sqlite3.Row
    return _CONN


def _ensure_schema() -> None:
    """Idempotently create the schema on first data access.

    Guarantees tables exist even when the FastAPI startup hook did not run
    (e.g. tests using a module-level TestClient, or direct adapter usage).
    """
    global _SCHEMA_READY
    if not _SCHEMA_READY:
        init_db()
        _SCHEMA_READY = True


def init_db() -> None:
    global _SCHEMA_READY
    with _LOCK:
        conn = _connect()
        cur = conn.cursor()
        for table in ENTITIES:
            cur.execute(
                f"""CREATE TABLE IF NOT EXISTS {table} (
                    id TEXT PRIMARY KEY,
                    project_id TEXT,
                    created_at TEXT,
                    payload TEXT NOT NULL
                )"""
            )
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_project ON {table}(project_id)")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_created ON {table}(created_at)")
        conn.commit()
        _SCHEMA_READY = True


def _validate_table(table: str) -> None:
    if table not in ENTITIES:
        raise ValueError(f"Unknown entity table: {table}")


def insert(table: str, record: dict[str, Any]) -> dict[str, Any]:
    _validate_table(table)
    with _LOCK:
        _ensure_schema()
        conn = _connect()
        conn.execute(
            f"INSERT OR REPLACE INTO {table} (id, project_id, created_at, payload) VALUES (?, ?, ?, ?)",
            (
                str(record["id"]),
                record.get("project_id"),
                record.get("created_at") or record.get("timestamp"),
                json.dumps(record, default=str),
            ),
        )
        conn.commit()
    return record


def get(table: str, entity_id: str) -> Optional[dict[str, Any]]:
    _validate_table(table)
    with _LOCK:
        _ensure_schema()
        conn = _connect()
        row = conn.execute(f"SELECT payload FROM {table} WHERE id = ?", (entity_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def list_records(
    table: str,
    project_id: Optional[str] = None,
    limit: Optional[int] = None,
    order: str = "DESC",
) -> list[dict[str, Any]]:
    _validate_table(table)
    order = "DESC" if str(order).upper() == "DESC" else "ASC"
    q = f"SELECT payload FROM {table}"
    params: list[Any] = []
    if project_id:
        q += " WHERE project_id = ?"
        params.append(project_id)
    q += f" ORDER BY created_at {order}"
    if limit:
        q += " LIMIT ?"
        params.append(limit)
    with _LOCK:
        _ensure_schema()
        conn = _connect()
        rows = conn.execute(q, params).fetchall()
    return [json.loads(r["payload"]) for r in rows]


def count(table: str, project_id: Optional[str] = None) -> int:
    _validate_table(table)
    q = f"SELECT COUNT(*) AS c FROM {table}"
    params: list[Any] = []
    if project_id:
        q += " WHERE project_id = ?"
        params.append(project_id)
    with _LOCK:
        conn = _connect()
        row = conn.execute(q, params).fetchone()
    return int(row["c"]) if row else 0


def delete(table: str, entity_id: str) -> bool:
    _validate_table(table)
    with _LOCK:
        _ensure_schema()
        conn = _connect()
        cur = conn.execute(f"DELETE FROM {table} WHERE id = ?", (entity_id,))
        conn.commit()
        return cur.rowcount > 0


def clear_all() -> None:
    with _LOCK:
        conn = _connect()
        for table in ENTITIES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
