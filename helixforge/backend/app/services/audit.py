"""Audit + ToolRun logging.

Every tool invocation creates a ToolRun record and an AuditEvent. This is the
transparent, replayable trail the UI renders. No hidden chain-of-thought is
stored — only observable process metadata (agent, tool, summaries, provenance,
validation, timestamps).
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.models.schemas import SourceType, ValidationStatus, utcnow
from app.storage import db


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def record_tool_run(
    *,
    tool_name: str,
    tool_category: str,
    source_type: SourceType,
    input_summary: str,
    output_summary: str,
    validation_status: ValidationStatus = ValidationStatus.SKIPPED,
    project_id: Optional[str] = None,
    workflow_run_id: Optional[str] = None,
    agent_name: str = "",
    latency_ms: Optional[float] = None,
    raw_output_ref: Optional[str] = None,
    errors: Optional[list[str]] = None,
    warnings: Optional[list[str]] = None,
    confidence: Optional[float] = None,
) -> str:
    """Persist a ToolRun and a paired AuditEvent. Returns the audit_event_id."""
    ts = utcnow()
    tool_run_id = new_id("tr")
    audit_id = new_id("ae")

    db.insert(
        "tool_runs",
        {
            "id": tool_run_id,
            "project_id": project_id,
            "created_at": ts,
            "workflow_run_id": workflow_run_id,
            "tool_name": tool_name,
            "tool_category": tool_category,
            "source_type": source_type.value if isinstance(source_type, SourceType) else str(source_type),
            "input_summary": input_summary,
            "output_summary": output_summary,
            "validation_status": validation_status.value if isinstance(validation_status, ValidationStatus) else str(validation_status),
            "latency_ms": latency_ms,
            "raw_output_ref": raw_output_ref,
            "errors": errors or [],
            "warnings": warnings or [],
            "audit_event_id": audit_id,
        },
    )

    db.insert(
        "audit_events",
        {
            "id": audit_id,
            "project_id": project_id,
            "created_at": ts,
            "timestamp": ts,
            "workflow_run_id": workflow_run_id,
            "agent_name": agent_name or _agent_for_tool(tool_name),
            "tool_name": tool_name,
            "event_type": "tool_call",
            "source_type": source_type.value if isinstance(source_type, SourceType) else str(source_type),
            "input_summary": input_summary,
            "output_summary": output_summary,
            "validation_status": validation_status.value if isinstance(validation_status, ValidationStatus) else str(validation_status),
            "confidence": confidence,
            "warnings": warnings or [],
            "errors": errors or [],
        },
    )
    return audit_id


def record_event(
    *,
    event_type: str,
    agent_name: str,
    source_type: SourceType,
    input_summary: str = "",
    output_summary: str = "",
    tool_name: str = "",
    project_id: Optional[str] = None,
    workflow_run_id: Optional[str] = None,
    validation_status: ValidationStatus = ValidationStatus.SKIPPED,
    confidence: Optional[float] = None,
    warnings: Optional[list[str]] = None,
    errors: Optional[list[str]] = None,
) -> str:
    ts = utcnow()
    audit_id = new_id("ae")
    db.insert(
        "audit_events",
        {
            "id": audit_id,
            "project_id": project_id,
            "created_at": ts,
            "timestamp": ts,
            "workflow_run_id": workflow_run_id,
            "agent_name": agent_name,
            "tool_name": tool_name,
            "event_type": event_type,
            "source_type": source_type.value if isinstance(source_type, SourceType) else str(source_type),
            "input_summary": input_summary,
            "output_summary": output_summary,
            "validation_status": validation_status.value if isinstance(validation_status, ValidationStatus) else str(validation_status),
            "confidence": confidence,
            "warnings": warnings or [],
            "errors": errors or [],
        },
    )
    return audit_id


def list_events(project_id: Optional[str] = None, limit: int = 200) -> list[dict[str, Any]]:
    return db.list_records("audit_events", project_id=project_id, limit=limit, order="DESC")


_AGENT_BY_TOOL = {
    "PubMed": "Evidence Miner",
    "ClinicalTrials.gov": "Clinical Strategy Agent",
    "ChEMBL": "Target Scout",
    "RDKit": "Cheminformatics Validator",
    "TDC/PyTDC": "ADMET & Toxicology Agent",
    "AutoDock Vina": "Binding & Structure Agent",
    "REINVENT4": "Molecular Design Agent",
    "Safety": "Safety Auditor",
    "Report": "Report Builder",
}


def _agent_for_tool(tool_name: str) -> str:
    return _AGENT_BY_TOOL.get(tool_name, "Project Orchestrator")
