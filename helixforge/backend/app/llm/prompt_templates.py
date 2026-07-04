"""Versioned prompt template registry. Loads the .md templates, hashes them, and
exposes an assembled system prompt (safety envelope + task template)."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

_PROMPT_DIR = Path(__file__).resolve().parent / "prompts"

# id -> (filename, version, purpose)
TEMPLATES: dict[str, tuple[str, str, str]] = {
    "system_scientific_safety": ("system_scientific_safety.md", "v1", "system_envelope"),
    "dynamic_planner": ("dynamic_planner.md", "v1", "DYNAMIC_PLANNING"),
    "hypothesis_reasoner": ("hypothesis_reasoner.md", "v1", "HYPOTHESIS_REASONING"),
    "semantic_critic": ("semantic_critic.md", "v1", "SEMANTIC_CRITIQUE"),
    "safe_rewrite": ("safe_rewrite.md", "v1", "SAFE_REWRITE"),
    "report_summary": ("report_summary.md", "v1", "REPORT_SUMMARY"),
}


def _read(filename: str) -> str:
    path = _PROMPT_DIR / filename
    return path.read_text(encoding="utf-8") if path.exists() else ""


def template_content(template_id: str) -> str:
    if template_id not in TEMPLATES:
        return ""
    return _read(TEMPLATES[template_id][0])


def template_hash(template_id: str) -> str:
    content = template_content(template_id)
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()[:16]


def system_prompt_for(template_id: str) -> str:
    """Safety envelope + the task-specific template = the full system prompt."""
    envelope = template_content("system_scientific_safety")
    task = template_content(template_id)
    return f"{envelope}\n\n---\n\n{task}".strip()


def combined_hash(template_id: str) -> str:
    content = template_content("system_scientific_safety") + "\n" + template_content(template_id)
    return "sha256:" + hashlib.sha256(content.encode()).hexdigest()[:16]


def registry() -> list[dict[str, Any]]:
    out = []
    for tid, (fname, version, purpose) in TEMPLATES.items():
        out.append({"id": tid, "name": fname, "version": version, "purpose": purpose,
                    "hash": template_hash(tid), "content_path": f"app/llm/prompts/{fname}",
                    "exists": (_PROMPT_DIR / fname).exists()})
    return out
