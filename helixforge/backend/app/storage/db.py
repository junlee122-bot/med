"""Lightweight SQLite persistence.

One table per entity: (id, project_id, created_at, payload JSON). This keeps the
storage layer trivial to run (no server, no migrations) while remaining
Postgres-portable — the same insert/get/list/count surface maps onto a JSONB
column in Postgres. Every tool call persists a ToolRun and an AuditEvent.
"""
from __future__ import annotations

import json
import re
import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

from app.config import get_settings

_LOCK = threading.RLock()
_CONN: Optional[sqlite3.Connection] = None
_SCHEMA_READY = False
MAX_LIST_LIMIT = 5000

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
    "evaluation_metrics",
    "run_manifests",
    # --- Phase 3: submission-grade hardening ---
    "run_snapshots",
    "snapshot_artifacts",
    "ai_interactions",
    "scenario_runs",
    "run_configs",
    "regulatory_docs",
    "submission_artifacts",
    # --- Phase 5: professional scientific validation layer ---
    "evidence_claims",
    "target_biology_reviews",
    "activity_normalizations",
    "medchem_reviews",
    "applicability_results",
    "admet_validation_jobs",
    "docking_protocols",
    "pareto_analyses",
    "professional_evaluations",
    "translational_assessments",
    "clinical_precedent_reviews",
    "professional_documents",
    "expert_review_items",
    "identity_normalizations",
    "whitepapers",
    # --- Phase 7: hybrid Fable agentic layer ---
    "llm_calls",
    "hybrid_plans",
    "replan_events",
    "semantic_critiques",
    "rediscovery_runs",
    "optimization_loop_runs",
    # --- Phase 8: CPU-first + external-GPU-ready compute layer ---
    "compute_jobs",
    "compute_job_attempts",
    "compute_artifacts",
    "compute_cost_events",
    "compute_decisions",
    "compute_providers",
    "compute_snapshots",
    "dataset_versions",
    "dataset_curations",
    "cpu_models",
    "model_checkpoints",
    "ligand_screens",
    "active_learning_runs",
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
                    workflow_run_id TEXT,
                    created_at TEXT,
                    payload TEXT NOT NULL
                )"""
            )
            columns = {row[1] for row in cur.execute(f"PRAGMA table_info({table})").fetchall()}
            if "workflow_run_id" not in columns:
                cur.execute(f"ALTER TABLE {table} ADD COLUMN workflow_run_id TEXT")
            # Preserve run scoping for databases created by older releases and
            # for early builds that only backfilled llm_calls.  `run_id` is the
            # historical spelling used by several run-owned entity types.
            for row in cur.execute(
                f"SELECT id, payload FROM {table} WHERE workflow_run_id IS NULL"
            ).fetchall():
                try:
                    payload = json.loads(row[1])
                    run_id = payload.get("workflow_run_id") or payload.get("run_id")
                except (TypeError, ValueError, json.JSONDecodeError):
                    run_id = None
                if run_id:
                    cur.execute(
                        f"UPDATE {table} SET workflow_run_id = ? WHERE id = ?",
                        (str(run_id), row[0]),
                    )
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_project ON {table}(project_id)")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_created ON {table}(created_at)")
            cur.execute(f"CREATE INDEX IF NOT EXISTS idx_{table}_run ON {table}(workflow_run_id)")
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
        entity_id = str(record["id"])
        project_id = record.get("project_id")
        workflow_run_id = record.get("workflow_run_id") or record.get("run_id")
        existing = conn.execute(
            f"SELECT project_id, workflow_run_id FROM {table} WHERE id = ?", (entity_id,)
        ).fetchone()
        if existing is not None and existing["project_id"] != project_id:
            raise ValueError(
                f"Cross-project id collision in {table}: {entity_id!r} already belongs "
                f"to project {existing['project_id']!r}, not {project_id!r}"
            )
        if existing is not None and existing["workflow_run_id"] != workflow_run_id:
            raise ValueError(
                f"Cross-run id collision in {table}: {entity_id!r} already belongs "
                f"to run {existing['workflow_run_id']!r}, not {workflow_run_id!r}"
            )
        conn.execute(
            f"INSERT OR REPLACE INTO {table} "
            "(id, project_id, workflow_run_id, created_at, payload) VALUES (?, ?, ?, ?, ?)",
            (
                entity_id,
                project_id,
                workflow_run_id,
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
    workflow_run_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    _validate_table(table)
    order = "DESC" if str(order).upper() == "DESC" else "ASC"
    q = f"SELECT payload FROM {table}"
    params: list[Any] = []
    conditions: list[str] = []
    if project_id is not None:
        conditions.append("project_id = ?")
        params.append(project_id)
    if workflow_run_id is not None:
        conditions.append("workflow_run_id = ?")
        params.append(workflow_run_id)
    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    q += f" ORDER BY created_at {order}"
    # SQLite treats a negative LIMIT as unbounded. Normalize centrally so an
    # API caller cannot bypass bounds with -1 or force an excessive scan.
    if limit is None:
        normalized_limit = MAX_LIST_LIMIT
    else:
        try:
            normalized_limit = int(limit)
        except (TypeError, ValueError) as exc:
            raise ValueError("limit must be an integer") from exc
        if normalized_limit <= 0:
            return []
        normalized_limit = min(normalized_limit, MAX_LIST_LIMIT)
    q += " LIMIT ?"
    params.append(normalized_limit)
    with _LOCK:
        _ensure_schema()
        conn = _connect()
        rows = conn.execute(q, params).fetchall()
    return [json.loads(r["payload"]) for r in rows]


def count(
    table: str,
    project_id: Optional[str] = None,
    workflow_run_id: Optional[str] = None,
) -> int:
    _validate_table(table)
    q = f"SELECT COUNT(*) AS c FROM {table}"
    params: list[Any] = []
    conditions: list[str] = []
    if project_id is not None:
        conditions.append("project_id = ?")
        params.append(project_id)
    if workflow_run_id is not None:
        conditions.append("workflow_run_id = ?")
        params.append(workflow_run_id)
    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    with _LOCK:
        _ensure_schema()
        conn = _connect()
        row = conn.execute(q, params).fetchone()
    return int(row["c"]) if row else 0


def _json_field_path(field: str) -> str:
    """Return a safe top-level SQLite JSON path for an internal aggregate."""
    if not isinstance(field, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", field):
        raise ValueError("invalid JSON field name")
    return f"$.{field}"


def sum_payload_numeric(
    table: str,
    field: str,
    *,
    workflow_run_id: Optional[str] = None,
    created_at_prefix: Optional[str] = None,
    payload_equals: Optional[dict[str, Any]] = None,
) -> float:
    """Sum a numeric payload field without the public list-size cap.

    Budget guards need the complete durable ledger, not merely the latest UI
    page. Aggregating in SQLite is bounded-memory and prevents newer zero-cost
    records from evicting older spend from the calculation.
    """
    _validate_table(table)
    value_path = _json_field_path(field)
    conditions: list[str] = []
    where_params: list[Any] = []
    if workflow_run_id is not None:
        conditions.append("workflow_run_id = ?")
        where_params.append(workflow_run_id)
    if created_at_prefix is not None:
        conditions.append("created_at LIKE ?")
        where_params.append(f"{created_at_prefix}%")
    for key, value in (payload_equals or {}).items():
        conditions.append("json_extract(payload, ?) = ?")
        where_params.extend((_json_field_path(key), value))
    q = (
        "SELECT COALESCE(SUM(CASE WHEN json_valid(payload) "
        "THEN CAST(json_extract(payload, ?) AS REAL) ELSE 0 END), 0) AS total "
        f"FROM {table}"
    )
    if conditions:
        q += " WHERE " + " AND ".join(conditions)
    with _LOCK:
        _ensure_schema()
        row = _connect().execute(q, [value_path, *where_params]).fetchone()
    return float(row["total"] or 0.0) if row else 0.0


def sum_payload_numeric_by_workflow_run(table: str, field: str) -> dict[str, float]:
    """Return complete durable totals grouped by non-empty workflow run id."""
    _validate_table(table)
    value_path = _json_field_path(field)
    q = (
        "SELECT workflow_run_id AS run_id, "
        "COALESCE(SUM(CASE WHEN json_valid(payload) "
        "THEN CAST(json_extract(payload, ?) AS REAL) ELSE 0 END), 0) AS total "
        f"FROM {table} WHERE workflow_run_id IS NOT NULL AND workflow_run_id <> '' "
        "GROUP BY workflow_run_id"
    )
    with _LOCK:
        _ensure_schema()
        rows = _connect().execute(q, (value_path,)).fetchall()
    return {str(row["run_id"]): float(row["total"] or 0.0) for row in rows}


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
        _ensure_schema()
        conn = _connect()
        for table in ENTITIES:
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
