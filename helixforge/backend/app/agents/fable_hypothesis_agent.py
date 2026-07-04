"""Thin wrapper exposing the evidence-grounded hybrid hypothesis reasoner as an
agent-style entry point. Deterministic HypothesisAgent remains the fallback."""
from __future__ import annotations

from typing import Any, Optional

from app.services import hypothesis_reasoner


class FableHypothesisAgent:
    name = "Fable Hypothesis Agent"
    role = ("Generates conservative, evidence-grounded hypotheses with the LLM when enabled; "
            "every cited evidence ID is validated and every statement passes the language lint.")
    stage = "hypothesis_reasoning"

    def generate(self, run_id: Optional[str] = None, mode: Optional[str] = None,
                 client: Any = None) -> dict[str, Any]:
        return hypothesis_reasoner.generate_hybrid(run_id=run_id, mode=mode, client=client)
