"""Agent base classes and shared context.

Every agent produces an ``AgentOutput`` — a structured, observable record. The
engine turns that into a persisted ``AgentRun`` + audit event. No hidden
chain-of-thought is produced or stored.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.models.schemas import SourceType, ValidationStatus


@dataclass
class AgentContext:
    """Mutable shared state threaded through the agentic pipeline."""
    project_id: str
    workflow_run_id: str
    condition: str = "non-small cell lung cancer"
    target_query: str = "EGFR"
    max_results: int = 8
    run_vina_fixture: bool = False
    create_reinvent_config: bool = True
    injections: dict[str, bool] = field(default_factory=dict)
    # Cross-agent artifacts:
    shared: dict[str, Any] = field(default_factory=dict)
    counts: dict[str, int] = field(default_factory=lambda: {
        "REAL_TOOL_OUTPUT": 0, "DEMO_FALLBACK": 0, "CONFIGURED_BUT_NOT_RUN": 0,
        "TOOL_ERROR": 0, "HUMAN_INPUT": 0,
    })
    http_calls: int = 0
    local_calls: int = 0

    def inj(self, key: str) -> bool:
        return bool(self.injections.get(key))

    def bump(self, source_type: str) -> None:
        self.counts[source_type] = self.counts.get(source_type, 0) + 1


@dataclass
class AgentOutput:
    output_summary: str = ""
    rationale: str = ""
    assumptions: list[str] = field(default_factory=list)
    uncertainty_notes: str = ""
    next_action: str = ""
    confidence: float = 0.7
    status: str = "COMPLETE"  # AgentStatus value
    validation_status: ValidationStatus = ValidationStatus.PASSED
    validation_checks: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    molecule_ids: list[str] = field(default_factory=list)
    target_ids: list[str] = field(default_factory=list)
    tool_run_ids: list[str] = field(default_factory=list)
    source_types: list[str] = field(default_factory=list)

    def check(self, name: str, ok: bool, detail: str = "") -> None:
        self.validation_checks.append({"check": name, "ok": bool(ok), "detail": detail})


def track(ctx: "AgentContext", out: "AgentOutput", result: dict[str, Any], network: bool = True) -> dict[str, Any]:
    """Account a real adapter call: bump source-type counts, call counters, and
    thread the audit_event_id / source_type into the agent output."""
    st = result.get("source_type", SourceType.TOOL_ERROR.value)
    ctx.bump(st)
    if network:
        ctx.http_calls += 1
    else:
        ctx.local_calls += 1
    out.source_types.append(st)
    aeid = result.get("audit_event_id")
    if aeid:
        out.tool_run_ids.append(aeid)
    for e in result.get("errors", []) or []:
        if e:
            out.warnings.append(f"{result.get('tool_name', 'tool')}: {e}")
    return result


class BaseAgent:
    """Subclasses set metadata and implement ``run``."""
    name: str = "Agent"
    role: str = ""
    stage: str = ""
    stage_index: int = 0
    allowed_tools: list[str] = []

    def run(self, ctx: AgentContext) -> AgentOutput:  # pragma: no cover - overridden
        raise NotImplementedError

    # Default confidence heuristic: start from a base, reduce for each warning /
    # non-real source, floor at 0.1. Agents may override.
    def compute_confidence(self, base: float, out: AgentOutput) -> float:
        c = base
        c -= 0.05 * len(out.warnings)
        if any(s != SourceType.REAL_TOOL_OUTPUT.value for s in out.source_types):
            c -= 0.05
        if out.errors:
            c -= 0.15
        return max(0.1, min(1.0, round(c, 2)))
