"""Safety adapter — defensive screening of text and molecule records.

Blocks/quarantines hazardous or dual-use content, redacts unsafe detail, and
ensures no synthesis routes are emitted. This is screening only: it never
optimizes toxicity and never produces actionable hazardous instructions.
"""
from __future__ import annotations

import re
import hashlib
from typing import Any

from app.adapters.base import ToolAdapter
from app.config import get_settings
from app.models.schemas import HealthStatus, SourceType, ToolHealth, ValidationStatus
from app.storage import db
from app.models.schemas import utcnow

# Phrases that indicate a request for actionable hazardous / wet-lab / synthesis
# content, or overclaims. Screening is intentionally coarse and conservative.
HAZARD_PATTERNS = [
    (r"synthesi[sz]e?\s+(route|steps|procedure|protocol)", "synthesis_route"),
    (r"reaction\s+(conditions|scheme)", "reaction_conditions"),
    (r"reagent\s+list", "reagent_list"),
    (r"purification\s+(procedure|steps)", "purification"),
    (r"\b(nerve agent|explosive|chemical weapon|bioweapon)\b", "controlled_hazard"),
    (r"increase\s+(toxicity|lethality|infectivity|potency of harm)", "toxicity_enhancement"),
    (r"\bdosage\b|\bdose\b\s+(instructions|advice)", "dosage_advice"),
]
OVERCLAIM_PATTERNS = [
    (r"validated cure", '"validated cure"'),
    (r"proven efficacy", '"proven efficacy"'),
    (r"guaranteed", '"guaranteed"'),
    (r"100% (safe|effective)", '"100% safe/effective"'),
]


class SafetyAdapter(ToolAdapter):
    id = "safety"
    name = "Safety"
    category = "safety"
    required_config: list[str] = []
    mode = "local"

    def health_check(self) -> ToolHealth:
        return ToolHealth(
            tool_id=self.id, name=self.name, category=self.category,
            status=HealthStatus.AVAILABLE, mode=self.mode,
            detail=f"Safety screen active ({len(HAZARD_PATTERNS)} hazard patterns, "
                   f"{len(OVERCLAIM_PATTERNS)} overclaim patterns). Policy {get_settings().app_version}.",
            required_config=self.required_config,
        )

    def run(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = (payload.get("text") or "").lower()
        smiles = payload.get("smiles")
        label = payload.get("label") or (smiles or "text")
        categories: list[str] = []

        for pat, cat in HAZARD_PATTERNS:
            if re.search(pat, text):
                categories.append(cat)
        overclaims = [lbl for pat, lbl in OVERCLAIM_PATTERNS if re.search(pat, text)]

        if categories:
            status = "BLOCKED"
            redacted = ("Content matched a restricted category and was blocked. "
                        "Details withheld by policy; no actionable hazardous content is produced.")
            safe_alt = ("Reframe as high-level, non-actionable research decision support. "
                        "Property/risk summaries only — never synthesis routes or hazardous procedures.")
            validation = ValidationStatus.WARNING
        elif overclaims:
            status = "REVIEW_REQUIRED"
            redacted = f"Overclaim(s) detected: {', '.join(overclaims)}. Rephrase to in-silico hypothesis for expert review."
            safe_alt = "Replace with calibrated, uncertainty-aware language."
            validation = ValidationStatus.WARNING
        else:
            status = "PASS"
            redacted = ""
            safe_alt = ""
            validation = ValidationStatus.PASSED

        if status != "PASS":
            workflow_run_id = payload.get("workflow_run_id")
            identity = f"{workflow_run_id or 'unscoped'}|{payload.get('project_id')}|{label}|{status}"
            digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:12]
            db.insert("safety_flags", {
                "id": f"sf-{workflow_run_id or 'unscoped'}-{digest}",
                "project_id": payload.get("project_id"), "workflow_run_id": workflow_run_id,
                "created_at": utcnow(), "entity_label": label, "status": status,
                "categories": categories or ["overclaim"], "redacted_summary": redacted,
            })

        return {
            "tool_name": self.name, "source": self.name,
            "source_type": SourceType.REAL_TOOL_OUTPUT.value,
            "input_summary": f"screen label={label}",
            "output_summary": f"Safety status: {status}" + (f" ({', '.join(categories or overclaims)})" if status != 'PASS' else ""),
            "validation_status": validation.value,
            "status": status, "categories": categories or overclaims,
            "redacted_summary": redacted, "safe_alternative": safe_alt,
            "errors": [], "warnings": [redacted] if status == "BLOCKED" else [],
        }
