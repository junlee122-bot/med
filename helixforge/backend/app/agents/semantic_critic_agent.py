"""Thin wrapper exposing the Fable-assisted semantic critic as an agent-style entry
point. The rule-based CriticAgent remains and runs alongside this."""
from __future__ import annotations

from typing import Any, Optional

from app.services import semantic_critic


class SemanticCriticAgent:
    name = "Semantic Critic Agent"
    role = ("Adds LLM semantic critique on top of the rule-based critic; every item is "
            "validated deterministically and converted to a revision event.")
    stage = "semantic_critic"

    def review(self, run_id: str, mode: Optional[str] = None, client: Any = None) -> dict[str, Any]:
        return semantic_critic.run_semantic_critic(run_id, mode=mode, client=client)
