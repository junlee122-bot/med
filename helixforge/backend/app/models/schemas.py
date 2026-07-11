"""Pydantic schemas: the shared tool-output envelope, health/validation models,
and per-endpoint request/response contracts.

Every tool result is labeled with a SourceType so the UI can never confuse a
real result with a fallback or an unrun tool.
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Provenance / status enums
# ---------------------------------------------------------------------------
class SourceType(str, Enum):
    REAL_TOOL_OUTPUT = "REAL_TOOL_OUTPUT"
    RECORDED_REAL_TOOL_OUTPUT = "RECORDED_REAL_TOOL_OUTPUT"  # replayed captured real data
    DEMO_FALLBACK = "DEMO_FALLBACK"
    CONFIGURED_BUT_NOT_RUN = "CONFIGURED_BUT_NOT_RUN"
    TOOL_ERROR = "TOOL_ERROR"
    HUMAN_INPUT = "HUMAN_INPUT"
    BASELINE_MODEL_OUTPUT = "BASELINE_MODEL_OUTPUT"  # a locally-trained baseline model
    HEURISTIC_ANALYSIS = "HEURISTIC_ANALYSIS"        # rule-based, not a tool/DB result
    ASSUMPTION = "ASSUMPTION"                        # explicitly-labeled assumption
    SAFETY_REDACTED = "SAFETY_REDACTED"              # content withheld by policy
    # --- Phase 8: compute / model output source types ---
    REAL_CPU_MODEL_OUTPUT = "REAL_CPU_MODEL_OUTPUT"          # a CPU model that actually trained + predicted
    BASELINE_CPU_MODEL_OUTPUT = "BASELINE_CPU_MODEL_OUTPUT"  # a CPU baseline model output
    RECORDED_CPU_MODEL_OUTPUT = "RECORDED_CPU_MODEL_OUTPUT"  # replayed CPU model output
    REAL_REMOTE_GPU_OUTPUT = "REAL_REMOTE_GPU_OUTPUT"        # a remote GPU job that actually ran + validated
    RECORDED_GPU_OUTPUT = "RECORDED_GPU_OUTPUT"              # replayed captured GPU output
    GPU_CONFIGURED_NOT_RUN = "GPU_CONFIGURED_NOT_RUN"        # GPU tool configured/spec'd but not executed
    GPU_JOB_ERROR = "GPU_JOB_ERROR"                          # GPU job failed
    GPU_BUDGET_BLOCKED = "GPU_BUDGET_BLOCKED"                # GPU job blocked by budget guard
    GPU_SAFETY_BLOCKED = "GPU_SAFETY_BLOCKED"                # GPU job blocked by safety gate
    GPU_ARTIFACT_UNVERIFIED = "GPU_ARTIFACT_UNVERIFIED"      # GPU ran but artifacts failed validation
    COMPUTE_FALLBACK_OUTPUT = "COMPUTE_FALLBACK_OUTPUT"      # CPU substitute used in place of GPU
    LOCAL_HEURISTIC_GENERATED = "LOCAL_HEURISTIC_GENERATED"  # in-silico heuristic-generated structure


class ValidationStatus(str, Enum):
    PASSED = "PASSED"
    FAILED = "FAILED"
    WARNING = "WARNING"
    SKIPPED = "SKIPPED"


class HealthStatus(str, Enum):
    AVAILABLE = "AVAILABLE"            # dependency present + reachable
    MISSING_DEPENDENCY = "MISSING_DEPENDENCY"  # python pkg / binary absent
    NOT_CONFIGURED = "NOT_CONFIGURED"  # needs env/config to run
    DEGRADED = "DEGRADED"              # reachable but limited
    ERROR = "ERROR"


# ---------------------------------------------------------------------------
# Common envelope
# ---------------------------------------------------------------------------
class ToolHealth(BaseModel):
    tool_id: str
    name: str
    category: str
    status: HealthStatus
    mode: str = "real"  # real | fixture | subprocess | http
    detail: str = ""
    required_config: list[str] = Field(default_factory=list)
    checked_at: str = Field(default_factory=utcnow)
    latency_ms: Optional[float] = None


class ValidationResult(BaseModel):
    status: ValidationStatus
    checks: list[str] = Field(default_factory=list)
    messages: list[str] = Field(default_factory=list)


class ToolEnvelope(BaseModel):
    """Common fields every tool response carries."""
    tool_name: str
    source: str
    source_type: SourceType
    input_summary: str = ""
    output_summary: str = ""
    raw_output_ref: Optional[str] = None
    retrieved_at: str = Field(default_factory=utcnow)
    validation_status: ValidationStatus = ValidationStatus.SKIPPED
    audit_event_id: Optional[str] = None
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# PubMed
# ---------------------------------------------------------------------------
class PubMedSearchRequest(BaseModel):
    query: str = Field(..., examples=["EGFR non-small cell lung cancer resistance"])
    max_results: int = Field(default=10, ge=1, le=100)
    project_id: Optional[str] = None


class PubMedItem(BaseModel):
    pmid: str
    title: str
    abstract: str = ""
    journal: str = ""
    year: str = ""
    authors: list[str] = Field(default_factory=list)
    url: str = ""
    retrieved_at: str = Field(default_factory=utcnow)


class PubMedResponse(ToolEnvelope):
    items: list[PubMedItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ClinicalTrials.gov
# ---------------------------------------------------------------------------
class ClinicalTrialsRequest(BaseModel):
    condition: str = Field(default="non-small cell lung cancer")
    query: str = Field(default="EGFR")
    max_results: int = Field(default=10, ge=1, le=100)
    project_id: Optional[str] = None


class ClinicalTrialItem(BaseModel):
    nct_id: str
    brief_title: str = ""
    status: str = ""
    phase: str = ""
    conditions: list[str] = Field(default_factory=list)
    interventions: list[str] = Field(default_factory=list)
    primary_outcomes: list[str] = Field(default_factory=list)
    url: str = ""


class ClinicalTrialsResponse(ToolEnvelope):
    items: list[ClinicalTrialItem] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# ChEMBL
# ---------------------------------------------------------------------------
class ChemblSearchRequest(BaseModel):
    query: str = Field(default="EGFR")
    max_results: int = Field(default=10, ge=1, le=100)
    project_id: Optional[str] = None


class ChemblActivitiesRequest(BaseModel):
    target_chembl_id: str = Field(default="CHEMBL203")
    activity_type: str = Field(default="IC50")
    max_results: int = Field(default=50, ge=1, le=200)
    project_id: Optional[str] = None


class ChemblResponse(ToolEnvelope):
    items: list[dict[str, Any]] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# RDKit
# ---------------------------------------------------------------------------
class RDKitSmilesRequest(BaseModel):
    smiles: str = Field(..., examples=["CCO"])
    project_id: Optional[str] = None


class RDKitSimilarityRequest(BaseModel):
    smiles: str
    reference_smiles: str
    project_id: Optional[str] = None


class RDKitDescriptors(BaseModel):
    mol_weight: float = 0
    logp: float = 0
    hbd: int = 0
    hba: int = 0
    tpsa: float = 0
    rotatable_bonds: int = 0
    ring_count: int = 0
    qed: float = 0
    lipinski_pass: bool = True
    lipinski_violations: int = 0


class RDKitResponse(ToolEnvelope):
    valid: bool = False
    canonical_smiles: str = ""
    descriptors: Optional[RDKitDescriptors] = None
    similarity: Optional[float] = None
    fingerprint_bits: Optional[int] = None


# ---------------------------------------------------------------------------
# TDC
# ---------------------------------------------------------------------------
class TDCLoadRequest(BaseModel):
    task: str = Field(default="ADME")
    dataset: str = Field(default="Caco2_Wang")
    project_id: Optional[str] = None


class TDCDatasetInfo(BaseModel):
    name: str
    task: str
    group: str
    endpoint: str
    description: str = ""


class TDCResponse(ToolEnvelope):
    dataset_name: str = ""
    task: str = ""
    row_count: int = 0
    columns: list[str] = Field(default_factory=list)
    split_summary: dict[str, int] = Field(default_factory=dict)
    preview: list[dict[str, Any]] = Field(default_factory=list)


class TDCDatasetsResponse(BaseModel):
    source: str = "TDC/PyTDC"
    source_type: SourceType = SourceType.REAL_TOOL_OUTPUT
    installed: bool = False
    datasets: list[TDCDatasetInfo] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# AutoDock Vina
# ---------------------------------------------------------------------------
class VinaDockRequest(BaseModel):
    receptor_fixture: str = Field(default="sample_receptor.pdbqt")
    ligand_fixture: str = Field(default="sample_ligand.pdbqt")
    center: list[float] = Field(default_factory=lambda: [0.0, 0.0, 0.0])
    box_size: list[float] = Field(default_factory=lambda: [20.0, 20.0, 20.0])
    exhaustiveness: int = Field(default=8, ge=1, le=32)
    project_id: Optional[str] = None


class VinaResponse(ToolEnvelope):
    job_id: str = ""
    status: str = "queued"  # queued/running/complete/error
    scores: list[float] = Field(default_factory=list)
    output_files: list[str] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# REINVENT4
# ---------------------------------------------------------------------------
class ReinventScoringWeights(BaseModel):
    qed: float = 0.2
    rdkit_validity: float = 0.2
    admet: float = 0.2
    novelty: float = 0.2
    safety_penalty: float = 0.2


class ReinventConfigRequest(BaseModel):
    target_name: str = Field(default="EGFR")
    objective: str = Field(default="optimize small molecule candidates")
    scoring_weights: ReinventScoringWeights = Field(default_factory=ReinventScoringWeights)
    max_molecules: int = Field(default=100, ge=1, le=10000)
    project_id: Optional[str] = None


class ReinventRunRequest(BaseModel):
    config_path: str
    project_id: Optional[str] = None


class ReinventResponse(ToolEnvelope):
    config_path: str = ""
    job_id: str = ""
    status: str = ""
    generated_smiles: list[str] = Field(default_factory=list)
    valid_count: Optional[int] = None
    logs: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------
class SafetyScreenRequest(BaseModel):
    text: Optional[str] = None
    smiles: Optional[str] = None
    label: Optional[str] = None
    project_id: Optional[str] = None


class SafetyResponse(ToolEnvelope):
    status: str = "PASS"  # PASS/REVIEW_REQUIRED/BLOCKED
    categories: list[str] = Field(default_factory=list)
    redacted_summary: str = ""
    safe_alternative: str = ""


# ---------------------------------------------------------------------------
# Workflow / audit / report
# ---------------------------------------------------------------------------
class PipelineRequest(BaseModel):
    project_id: Optional[str] = None
    condition: str = Field(default="non-small cell lung cancer")
    target_query: str = Field(default="EGFR")
    max_results: int = Field(default=8, ge=1, le=50)
    run_vina_fixture: bool = False
    create_reinvent_config: bool = True


class WorkflowStepResult(BaseModel):
    step: str
    tool_name: str
    source_type: SourceType
    status: str
    summary: str
    audit_event_id: Optional[str] = None
    errors: list[str] = Field(default_factory=list)


class WorkflowRunResponse(BaseModel):
    run_id: str
    project_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    steps: list[WorkflowStepResult] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    report_id: Optional[str] = None
    disclaimer: str = ""


class AuditEventModel(BaseModel):
    id: str
    timestamp: str
    project_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    agent_name: str = ""
    tool_name: str = ""
    event_type: str = ""
    source_type: SourceType
    input_summary: str = ""
    output_summary: str = ""
    validation_status: ValidationStatus = ValidationStatus.SKIPPED
    confidence: Optional[float] = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)


class ReportGenerateRequest(BaseModel):
    project_id: Optional[str] = None
    workflow_run_id: Optional[str] = None
    title: str = Field(default="HelixForge AI — Integration Report")


class ReportResponse(BaseModel):
    report_id: str
    title: str
    created_at: str
    markdown: str
    json_audit: dict[str, Any]
    format: str = "markdown"
