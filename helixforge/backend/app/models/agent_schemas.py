"""Phase 2 — agentic layer Pydantic schemas.

Kept in a separate module from the tool-envelope schemas so the integration
contract stays stable. Everything here is observable-trace only: plans, agent
runs, revision events, evaluation metrics — never hidden chain-of-thought.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.schemas import SourceType, ValidationStatus, utcnow


class AgentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    WARNING = "WARNING"
    FAILED = "FAILED"
    REVISING = "REVISING"
    BLOCKED = "BLOCKED"


class AgentRunModel(BaseModel):
    id: str
    project_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    agent_name: str
    agent_role: str = ""
    stage: str = ""
    stage_index: int = 0
    status: AgentStatus = AgentStatus.COMPLETE
    started_at: str = Field(default_factory=utcnow)
    completed_at: Optional[str] = None
    input_summary: str = ""
    output_summary: str = ""
    rationale: str = ""
    assumptions: list[str] = Field(default_factory=list)
    uncertainty_notes: str = ""
    next_action: str = ""
    tool_run_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    molecule_ids: list[str] = Field(default_factory=list)
    target_ids: list[str] = Field(default_factory=list)
    validation_status: ValidationStatus = ValidationStatus.SKIPPED
    validation_checks: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.7
    source_types: list[SourceType] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    revision_of: Optional[str] = None
    revision_reason: str = ""
    is_revision: bool = False


class AgentPlanModel(BaseModel):
    id: str
    workflow_run_id: Optional[str] = None
    project_id: Optional[str] = None
    objective: str = ""
    stages: list[dict[str, Any]] = Field(default_factory=list)
    assigned_agents: list[str] = Field(default_factory=list)
    dependencies: list[dict[str, str]] = Field(default_factory=list)
    created_at: str = Field(default_factory=utcnow)
    status: str = "created"


class RevisionEventModel(BaseModel):
    id: str
    project_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    original_agent_run_id: Optional[str] = None
    critic_agent_run_id: Optional[str] = None
    reason_category: str = ""
    issue_summary: str = ""
    action_taken: str = ""
    before_summary: str = ""
    after_summary: str = ""
    confidence_delta: float = 0.0
    created_at: str = Field(default_factory=utcnow)


class ErrorInjectionToggles(BaseModel):
    invalid_smiles: bool = False
    fake_citation: bool = False
    tool_failure: bool = False
    safety_flag: bool = False
    overclaim: bool = False
    contradictory_evidence: bool = False


class AgenticPipelineRequest(BaseModel):
    project_id: Optional[str] = None
    condition: str = Field(default="non-small cell lung cancer")
    target_query: str = Field(default="EGFR")
    max_results: int = Field(default=8, ge=1, le=50)
    run_vina_fixture: bool = False
    create_reinvent_config: bool = True
    evaluation_mode: str = Field(default="retrospective_rediscovery")
    error_injections: ErrorInjectionToggles = Field(default_factory=ErrorInjectionToggles)


class ErrorInjectionDemoRequest(BaseModel):
    scenario: str = Field(default="invalid_smiles")
    condition: str = Field(default="non-small cell lung cancer")
    target_query: str = Field(default="EGFR")


class EvaluationMetricModel(BaseModel):
    id: str
    project_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    module: str = ""
    metric_name: str = ""
    value: Any = None
    unit: str = ""
    target: Optional[float] = None
    status: str = "info"  # pass | warn | fail | info
    interpretation: str = ""
    created_at: str = Field(default_factory=utcnow)


class AgenticPipelineResponse(BaseModel):
    run_id: str
    project_id: str
    status: str
    agent_runs: list[dict[str, Any]] = Field(default_factory=list)
    plan: Optional[dict[str, Any]] = None
    steps: list[dict[str, Any]] = Field(default_factory=list)
    revision_events: list[dict[str, Any]] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    report_id: Optional[str] = None
    ko_report_id: Optional[str] = None
    disclaimer: str = ""


class SafetyLintRequest(BaseModel):
    markdown: Optional[str] = None
    report_id: Optional[str] = None


class SafetyLintResponse(BaseModel):
    status: str  # PASS | REVIEW_REQUIRED | BLOCKED
    export_safe: bool = True
    findings: list[dict[str, Any]] = Field(default_factory=list)
    checked_at: str = Field(default_factory=utcnow)


class EvidenceVerifyRequest(BaseModel):
    source_name: str = ""
    identifier: str = ""
    identifier_type: str = ""
    url: str = ""
