"""ClinicalTrials.gov adapter — real v2 API.

Docs: https://clinicaltrials.gov/data-api/api
Searches by condition + query term, paginates via nextPageToken up to
max_results, and parses the protocolSection modules. Real data only.
"""
from __future__ import annotations

import json
from typing import Any

from app.adapters.base import ToolAdapter
from app.config import get_settings
from app.models.schemas import HealthStatus, SourceType, ToolHealth, ValidationStatus
from app.services.httpclient import fetch_text

API = "https://clinicaltrials.gov/api/v2/studies"


class ClinicalTrialsGovAdapter(ToolAdapter):
    id = "clinicaltrials"
    name = "ClinicalTrials.gov"
    category = "clinical"
    required_config: list[str] = []
    mode = "http"

    def health_check(self) -> ToolHealth:
        s = get_settings()
        res = fetch_text(API, params={"pageSize": 1}, headers={"User-Agent": s.http_user_agent}, timeout=min(12, s.timeout_seconds))
        if res.ok:
            return ToolHealth(
                tool_id=self.id, name=self.name, category=self.category,
                status=HealthStatus.AVAILABLE, mode=self.mode,
                detail=f"v2 API reachable (HTTP {res.status_code} via {res.transport})",
                required_config=self.required_config,
            )
        return ToolHealth(
            tool_id=self.id, name=self.name, category=self.category,
            status=HealthStatus.ERROR, mode=self.mode,
            detail=f"v2 API unreachable: {res.error}", required_config=self.required_config,
        )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        s = get_settings()
        condition = payload.get("condition", "").strip()
        query = payload.get("query", "").strip()
        max_results = int(payload.get("max_results", 10))
        input_summary = f'condition="{condition}", query="{query}", max_results={max_results}'
        headers = {"User-Agent": s.http_user_agent}

        items: list[dict[str, Any]] = []
        page_token = None
        transport = "httpx"
        try:
            while len(items) < max_results:
                params: dict[str, Any] = {
                    "pageSize": min(s.chunk_size, max_results - len(items)),
                    "countTotal": "false",
                }
                if condition:
                    params["query.cond"] = condition
                if query:
                    params["query.term"] = query
                if page_token:
                    params["pageToken"] = page_token
                res = fetch_text(API, params=params, headers=headers, timeout=s.timeout_seconds)
                if not res.ok:
                    if items:
                        break  # partial results already gathered
                    return self._error(input_summary, [f"HTTP {res.status_code}: {res.error}"])
                transport = res.transport
                data = json.loads(res.text)
                studies = data.get("studies", [])
                for st in studies:
                    items.append(self._parse_study(st))
                    if len(items) >= max_results:
                        break
                page_token = data.get("nextPageToken")
                if not page_token or not studies:
                    break
        except Exception as exc:
            if items:
                return self._ok(input_summary, items, transport, warnings=[f"partial: {exc}"])
            return self._error(input_summary, [f"{type(exc).__name__}: {exc}"])

        return self._ok(input_summary, items, transport)

    def _parse_study(self, st: dict[str, Any]) -> dict[str, Any]:
        ps = st.get("protocolSection", {})
        ident = ps.get("identificationModule", {})
        status = ps.get("statusModule", {})
        design = ps.get("designModule", {})
        cond = ps.get("conditionsModule", {})
        arms = ps.get("armsInterventionsModule", {})
        outcomes = ps.get("outcomesModule", {})
        nct = ident.get("nctId", "")
        return {
            "nct_id": nct,
            "brief_title": ident.get("briefTitle", ""),
            "status": status.get("overallStatus", ""),
            "phase": ", ".join(design.get("phases", []) or []) or "N/A",
            "conditions": cond.get("conditions", []) or [],
            "interventions": [i.get("name", "") for i in arms.get("interventions", []) or []],
            "primary_outcomes": [o.get("measure", "") for o in outcomes.get("primaryOutcomes", []) or []],
            "url": f"https://clinicaltrials.gov/study/{nct}" if nct else "",
        }

    def _ok(self, input_summary: str, items: list, transport: str, warnings: list | None = None) -> dict[str, Any]:
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.REAL_TOOL_OUTPUT.value,
            "input_summary": input_summary,
            "output_summary": f"{len(items)} trials retrieved from ClinicalTrials.gov v2 (via {transport}).",
            "validation_status": ValidationStatus.PASSED.value,
            "items": items, "errors": [], "warnings": warnings or [],
        }

    def _error(self, input_summary: str, errors: list[str]) -> dict[str, Any]:
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.TOOL_ERROR.value,
            "input_summary": input_summary,
            "output_summary": "ClinicalTrials.gov query failed; no fabricated data returned.",
            "validation_status": ValidationStatus.FAILED.value,
            "items": [], "errors": errors, "warnings": [],
        }
