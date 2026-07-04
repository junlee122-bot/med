"""Base tool adapter contract.

Every adapter implements health_check / run / validate_output / fallback and
labels its output with a SourceType. Adapters MUST NOT fabricate a real result:
if a dependency or configuration is missing, they return CONFIGURED_BUT_NOT_RUN
or TOOL_ERROR (never REAL_TOOL_OUTPUT). Demo fallbacks are always labeled
DEMO_FALLBACK.
"""
from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, Optional

from app.models.schemas import (
    HealthStatus,
    SourceType,
    ToolHealth,
    ValidationResult,
    ValidationStatus,
)
from app.services import audit


class ToolAdapter(ABC):
    id: str = "tool"
    name: str = "Tool"
    category: str = "generic"
    required_config: list[str] = []
    mode: str = "real"

    # -- lifecycle --------------------------------------------------------
    @abstractmethod
    def health_check(self) -> ToolHealth:
        ...

    @abstractmethod
    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...

    def validate_output(self, output: dict[str, Any]) -> ValidationResult:
        # Default: consider it passed if there are no errors and a source_type present.
        errors = output.get("errors") or []
        if output.get("source_type") == SourceType.TOOL_ERROR.value:
            return ValidationResult(status=ValidationStatus.FAILED, messages=errors or ["tool error"])
        if errors:
            return ValidationResult(status=ValidationStatus.WARNING, messages=errors)
        return ValidationResult(status=ValidationStatus.PASSED, checks=["envelope present"])

    def fallback(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Default fallback: honest CONFIGURED_BUT_NOT_RUN with no fabricated data."""
        return {
            "tool_name": self.name,
            "source": self.name,
            "source_type": SourceType.CONFIGURED_BUT_NOT_RUN.value,
            "input_summary": self._summarize_input(payload),
            "output_summary": "Tool not available in this environment; no result produced.",
            "errors": [],
            "warnings": [f"{self.name} not available — returned CONFIGURED_BUT_NOT_RUN (no fabricated data)."],
        }

    # -- helpers ----------------------------------------------------------
    def _summarize_input(self, payload: dict[str, Any]) -> str:
        keys = [k for k in payload.keys() if k != "project_id"]
        parts = []
        for k in keys[:4]:
            v = payload[k]
            if isinstance(v, (list, dict)):
                v = f"<{type(v).__name__}:{len(v)}>"
            parts.append(f"{k}={v}")
        return ", ".join(parts)

    def health(self) -> ToolHealth:
        """Timed health check wrapper."""
        t0 = time.perf_counter()
        try:
            h = self.health_check()
        except Exception as exc:  # never let a health check crash the app
            h = ToolHealth(
                tool_id=self.id,
                name=self.name,
                category=self.category,
                status=HealthStatus.ERROR,
                mode=self.mode,
                detail=f"health check raised: {exc}",
                required_config=self.required_config,
            )
        if h.latency_ms is None:
            h.latency_ms = round((time.perf_counter() - t0) * 1000, 1)
        return h

    def execute(
        self,
        payload: dict[str, Any],
        *,
        project_id: Optional[str] = None,
        workflow_run_id: Optional[str] = None,
        agent_name: str = "",
    ) -> dict[str, Any]:
        """Run + validate + audit in one call. Guarantees a labeled envelope."""
        t0 = time.perf_counter()
        try:
            output = self.run(payload)
        except Exception as exc:
            output = {
                "tool_name": self.name,
                "source": self.name,
                "source_type": SourceType.TOOL_ERROR.value,
                "input_summary": self._summarize_input(payload),
                "output_summary": "Unhandled tool error.",
                "errors": [f"{type(exc).__name__}: {exc}"],
                "warnings": [],
            }
        latency = round((time.perf_counter() - t0) * 1000, 1)

        validation = self.validate_output(output)
        output.setdefault("validation_status", validation.status.value)

        audit_id = audit.record_tool_run(
            tool_name=self.name,
            tool_category=self.category,
            source_type=SourceType(output.get("source_type", SourceType.TOOL_ERROR.value)),
            input_summary=output.get("input_summary", self._summarize_input(payload)),
            output_summary=output.get("output_summary", ""),
            validation_status=ValidationStatus(output.get("validation_status", ValidationStatus.SKIPPED.value)),
            project_id=project_id or payload.get("project_id"),
            workflow_run_id=workflow_run_id,
            agent_name=agent_name,
            latency_ms=latency,
            raw_output_ref=output.get("raw_output_ref"),
            errors=output.get("errors"),
            warnings=output.get("warnings"),
        )
        output["audit_event_id"] = audit_id
        return output
