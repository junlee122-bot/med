"""ChEMBL adapter — real ChEMBL web services.

Docs: https://www.ebi.ac.uk/chembl/api/data/docs
Operations (payload["operation"]):
  - "targets"    : target search by query (e.g. EGFR)
  - "molecules"  : molecule search by query
  - "activities" : activities for a target_chembl_id (yields real SMILES)
"""
from __future__ import annotations

import json
from typing import Any

from app.adapters.base import ToolAdapter
from app.config import get_settings
from app.models.schemas import HealthStatus, SourceType, ToolHealth, ValidationStatus

from app.services.httpclient import fetch_text

BASE = "https://www.ebi.ac.uk/chembl/api/data"


class ChEMBLAdapter(ToolAdapter):
    id = "chembl"
    name = "ChEMBL"
    category = "chemistry"
    required_config: list[str] = []
    mode = "http"

    def health_check(self) -> ToolHealth:
        s = get_settings()
        res = fetch_text(f"{BASE}/status.json", headers={"User-Agent": s.http_user_agent}, timeout=min(12, s.timeout_seconds))
        if res.ok:
            return ToolHealth(
                tool_id=self.id, name=self.name, category=self.category,
                status=HealthStatus.AVAILABLE, mode=self.mode,
                detail=f"ChEMBL web services reachable (HTTP {res.status_code} via {res.transport})",
                required_config=self.required_config,
            )
        return ToolHealth(
            tool_id=self.id, name=self.name, category=self.category,
            status=HealthStatus.ERROR, mode=self.mode,
            detail=f"ChEMBL unreachable: {res.error}", required_config=self.required_config,
        )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        op = payload.get("operation", "targets")
        if op == "targets":
            return self._targets(payload)
        if op == "molecules":
            return self._molecules(payload)
        if op == "activities":
            return self._activities(payload)
        return self._error(f"operation={op}", [f"Unknown operation: {op}"])

    # -- operations -------------------------------------------------------
    def _targets(self, payload: dict[str, Any]) -> dict[str, Any]:
        s = get_settings()
        q = payload.get("query", "EGFR").strip()
        limit = int(payload.get("max_results", 10))
        summary = f'target search q="{q}", limit={limit}'
        res = fetch_text(
            f"{BASE}/target/search",
            params={"q": q, "format": "json", "limit": limit},
            headers={"User-Agent": s.http_user_agent}, timeout=s.timeout_seconds,
        )
        if not res.ok:
            return self._error(summary, [f"HTTP {res.status_code}: {res.error}"])
        data = json.loads(res.text)
        items = [
            {
                "target_chembl_id": t.get("target_chembl_id"),
                "pref_name": t.get("pref_name"),
                "organism": t.get("organism"),
                "target_type": t.get("target_type"),
                "score": t.get("score"),
                "components": [
                    c.get("component_description") or c.get("accession")
                    for c in (t.get("target_components") or [])
                ][:3],
            }
            for t in data.get("targets", [])
        ]
        return self._ok(summary, items, res.transport, f"{len(items)} ChEMBL targets")

    def _molecules(self, payload: dict[str, Any]) -> dict[str, Any]:
        s = get_settings()
        q = payload.get("query", "gefitinib").strip()
        limit = int(payload.get("max_results", 10))
        summary = f'molecule search q="{q}", limit={limit}'
        res = fetch_text(
            f"{BASE}/molecule/search",
            params={"q": q, "format": "json", "limit": limit},
            headers={"User-Agent": s.http_user_agent}, timeout=s.timeout_seconds,
        )
        if not res.ok:
            return self._error(summary, [f"HTTP {res.status_code}: {res.error}"])
        data = json.loads(res.text)
        items = []
        for m in data.get("molecules", []):
            structs = m.get("molecule_structures") or {}
            items.append({
                "molecule_chembl_id": m.get("molecule_chembl_id"),
                "pref_name": m.get("pref_name"),
                "canonical_smiles": structs.get("canonical_smiles"),
                "max_phase": m.get("max_phase"),
                "molecule_type": m.get("molecule_type"),
            })
        return self._ok(summary, items, res.transport, f"{len(items)} ChEMBL molecules")

    def _activities(self, payload: dict[str, Any]) -> dict[str, Any]:
        s = get_settings()
        target = payload.get("target_chembl_id", "CHEMBL203")
        act_type = payload.get("activity_type", "IC50")
        limit = int(payload.get("max_results", 50))
        summary = f'activities target={target}, type={act_type}, limit={limit}'
        params = {
            "target_chembl_id": target,
            "standard_type": act_type,
            "format": "json",
            "limit": min(limit, s.chunk_size),
        }
        res = fetch_text(
            f"{BASE}/activity", params=params,
            headers={"User-Agent": s.http_user_agent}, timeout=s.timeout_seconds,
        )
        if not res.ok:
            return self._error(summary, [f"HTTP {res.status_code}: {res.error}"])
        data = json.loads(res.text)
        items = []
        for a in data.get("activities", [])[:limit]:
            items.append({
                "molecule_chembl_id": a.get("molecule_chembl_id"),
                "canonical_smiles": a.get("canonical_smiles"),
                "standard_type": a.get("standard_type"),
                "standard_value": a.get("standard_value"),
                "standard_units": a.get("standard_units"),
                "pchembl_value": a.get("pchembl_value"),
                "target_pref_name": a.get("target_pref_name"),
            })
        with_smiles = sum(1 for i in items if i.get("canonical_smiles"))
        return self._ok(summary, items, res.transport, f"{len(items)} activities ({with_smiles} with structures)")

    # -- envelopes --------------------------------------------------------
    def _ok(self, summary: str, items: list, transport: str, out: str) -> dict[str, Any]:
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.REAL_TOOL_OUTPUT.value,
            "input_summary": summary,
            "output_summary": f"{out} (real ChEMBL via {transport}).",
            "validation_status": ValidationStatus.PASSED.value,
            "items": items, "errors": [], "warnings": [],
        }

    def _error(self, summary: str, errors: list[str]) -> dict[str, Any]:
        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.TOOL_ERROR.value,
            "input_summary": summary,
            "output_summary": "ChEMBL query failed; no fabricated data returned.",
            "validation_status": ValidationStatus.FAILED.value,
            "items": [], "errors": errors, "warnings": [],
        }
