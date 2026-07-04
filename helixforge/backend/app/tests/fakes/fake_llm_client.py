"""Deterministic fake LLM client for offline tests. Implements the same `complete()`
contract as AnthropicClient. Canned responses cover every branch: valid/invalid
JSON, fake evidence IDs, overclaims, critic items, budget/safety/timeout paths."""
from __future__ import annotations

import json
from typing import Any

from app.llm.schemas import LLMClientError, LLMSafetyRefusal

VALID_PLAN = {
    "objective": "Prioritize EGFR candidates for NSCLC (in-silico, expert review).",
    "strategy_summary": "Evidence-first, tool-grounded, safety-gated.",
    "mode": "HYBRID_LLM_DEV",
    "selected_stages": [
        {"stage_id": "evidence_mining", "agent": "EvidenceMinerAgent", "purpose": "mine PubMed",
         "required_tools": ["PubMed"], "optional_tools": [], "depends_on": [],
         "success_criteria": ["evidence found"], "failure_recovery": ["retry"],
         "safety_constraints": [], "budget_class": "low", "rationale_summary": "gather public evidence"},
        {"stage_id": "target_selection", "agent": "TargetScoutAgent", "purpose": "select target",
         "required_tools": ["ChEMBL"], "optional_tools": [], "depends_on": ["evidence_mining"],
         "success_criteria": ["target chosen"], "failure_recovery": ["broaden query"],
         "safety_constraints": [], "budget_class": "low", "rationale_summary": "rank targets"},
        {"stage_id": "hypothesis_reasoning", "agent": "HypothesisAgent", "purpose": "hypotheses",
         "required_tools": [], "optional_tools": [], "depends_on": ["evidence_mining", "target_selection"],
         "success_criteria": ["2-4 hypotheses"], "failure_recovery": ["deterministic template"],
         "safety_constraints": ["no efficacy claim"], "budget_class": "medium",
         "rationale_summary": "evidence-grounded hypotheses"},
        {"stage_id": "rdkit_validation", "agent": "CheminformaticsValidatorAgent", "purpose": "validate",
         "required_tools": ["RDKit"], "optional_tools": [], "depends_on": ["target_selection"],
         "success_criteria": ["valid mols"], "failure_recovery": ["reject invalid"],
         "safety_constraints": [], "budget_class": "low", "rationale_summary": "validate structures"},
        {"stage_id": "safety_lint", "agent": "SafetyAuditorAgent", "purpose": "safety",
         "required_tools": [], "optional_tools": [], "depends_on": ["hypothesis_reasoning"],
         "success_criteria": ["no forbidden content"], "failure_recovery": ["redact"],
         "safety_constraints": ["block hazards"], "budget_class": "low", "rationale_summary": "safety gate"},
        {"stage_id": "report_build", "agent": "ReportBuilderAgent", "purpose": "report",
         "required_tools": [], "optional_tools": [], "depends_on": ["safety_lint"],
         "success_criteria": ["report built"], "failure_recovery": ["template"],
         "safety_constraints": [], "budget_class": "low", "rationale_summary": "assemble report"},
    ],
    "skipped_stages": [{"stage_id": "optimization_loop", "reason": "budget"}],
    "replanning_triggers": ["target_not_found", "no_valid_molecules", "tool_failure", "safety_block"],
    "expected_artifacts": ["report"], "risks": ["tool outage"],
    "cost_guard": {"estimated_llm_calls": 2, "estimated_cost_usd": 0.05},
}

VALID_HYPOTHESES = {
    "hypotheses": [
        {"hypothesis_id": "H1", "statement": "An EGFR-directed small molecule is an in-silico hypothesis for expert review in NSCLC, supported by public-data signals.",
         "mechanism_summary": "Modulation of EGFR activity.", "target": "EGFR", "disease_context": "NSCLC",
         "supporting_evidence_ids": ["__EV0__"], "contradictory_evidence_ids": [], "assumptions": ["in-silico only"],
         "uncertainty_reasons": ["limited evidence"], "evidence_grade": "C", "confidence": 0.6,
         "next_validation_needs": ["orthogonal target validation"], "safety_notes": [], "language_risk": "PASS"},
    ],
    "overall_summary": "One conservative EGFR hypothesis for expert review.",
    "limitations": ["in-silico only; requires experimental validation"], "claims_to_avoid": ["cure", "proven"],
}

FAKE_EVIDENCE_HYPOTHESES = {
    "hypotheses": [
        {"hypothesis_id": "H1", "statement": "EGFR hypothesis.", "mechanism_summary": "x", "target": "EGFR",
         "disease_context": "NSCLC", "supporting_evidence_ids": ["ev-DOES-NOT-EXIST-999"],
         "contradictory_evidence_ids": [], "assumptions": [], "uncertainty_reasons": [], "evidence_grade": "C",
         "confidence": 0.6, "next_validation_needs": ["expert review"], "safety_notes": [], "language_risk": "PASS"},
    ],
    "overall_summary": "x", "limitations": ["in-silico"], "claims_to_avoid": [],
}

OVERCLAIM_HYPOTHESES = {
    "hypotheses": [
        {"hypothesis_id": "H1", "statement": "This EGFR inhibitor is a validated cure with proven clinical efficacy.",
         "mechanism_summary": "x", "target": "EGFR", "disease_context": "NSCLC",
         "supporting_evidence_ids": ["__EV0__"], "contradictory_evidence_ids": [], "assumptions": [],
         "uncertainty_reasons": [], "evidence_grade": "A", "confidence": 0.95,
         "next_validation_needs": [], "safety_notes": [], "language_risk": "PASS"},
    ],
    "overall_summary": "x", "limitations": [], "claims_to_avoid": [],
}

CRITIC_ITEMS = {
    "critique_items": [
        {"id": "C1", "severity": "REVIEW_REQUIRED", "category": "OVERCLAIM", "affected_entity_type": "hypothesis",
         "affected_entity_id": "H1", "issue_summary": "Statement implies proven efficacy.",
         "supporting_evidence_ids": [], "reasoning_summary": "Language exceeds evidence grade.",
         "recommended_fix": "Soften to in-silico hypothesis.", "safe_rewrite": "An in-silico hypothesis for expert review.",
         "requires_human_review": True},
    ],
    "overall_risk": "REVIEW_REQUIRED", "must_fix_before_submission": ["C1"], "safe_summary": "One overclaim to soften.",
}

SAFE_REWRITE = {"rewritten": "An in-silico hypothesis for expert review; requires experimental validation.",
                "changed": True, "removed_terms": ["cure", "proven"], "note": "softened"}


class FakeLLMClient:
    """Configurable fake. `response` selects a canned payload; `mode` triggers
    error/refusal/timeout branches. `evidence_ids` substitutes real IDs into __EV0__."""

    def __init__(self, response: str = "plan", *, evidence_ids: list[str] | None = None,
                 raise_error: bool = False, safety_refuse: bool = False, timeout: bool = False,
                 invalid_json: bool = False, tokens_in: int = 400, tokens_out: int = 300):
        self.response = response
        self.evidence_ids = evidence_ids or []
        self.raise_error = raise_error
        self.safety_refuse = safety_refuse
        self.timeout = timeout
        self.invalid_json = invalid_json
        self.tokens_in = tokens_in
        self.tokens_out = tokens_out
        self.calls: list[dict[str, Any]] = []

    def _payload(self) -> Any:
        p = {"plan": VALID_PLAN, "hypotheses": VALID_HYPOTHESES,
             "fake_evidence": FAKE_EVIDENCE_HYPOTHESES, "overclaim": OVERCLAIM_HYPOTHESES,
             "critic": CRITIC_ITEMS, "rewrite": SAFE_REWRITE}.get(self.response, VALID_PLAN)
        # Substitute the first real evidence id into placeholders.
        text = json.dumps(p)
        if self.evidence_ids:
            text = text.replace("__EV0__", self.evidence_ids[0])
        else:
            text = text.replace("__EV0__", "ev-none")
        return text

    def complete(self, *, model: str, system: str, prompt: str, max_tokens: int,
                 temperature: float = 0.2) -> dict[str, Any]:
        self.calls.append({"model": model, "max_tokens": max_tokens, "temperature": temperature})
        if self.timeout:
            raise LLMClientError("Request timed out after 90s")
        if self.raise_error:
            raise LLMClientError("simulated API 500")
        if self.safety_refuse:
            raise LLMSafetyRefusal("I can't help with that request.")
        text = "this is not json {broken" if self.invalid_json else self._payload()
        return {"text": text, "tokens_in": self.tokens_in, "tokens_out": self.tokens_out,
                "stop_reason": "end_turn", "model": model}
