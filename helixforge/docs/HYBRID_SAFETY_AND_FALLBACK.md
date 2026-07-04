# Hybrid Safety and Fallback

> Research decision support only. Fable 5 is optional and never supplies scientific ground truth. No wet-lab protocol, synthesis route, dosage, or medical advice. No hidden chain-of-thought. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `app/llm/safety.py` + `app/llm/llm_adapter.py`

**Safe envelope.** Every system prompt carries a biomedical safety envelope: research decision support only; no protocol/synthesis/dosage; no toxic optimization; no invented citations; observable summaries only (no hidden chain-of-thought); use only provided evidence IDs; state uncertainty; label assumptions.

**Fallback contract.** No key / `USE_LLM=false` → `DETERMINISTIC_FALLBACK`. Budget exceeded → `LLM_BUDGET_BLOCKED` + fallback. API error → `LLM_TOOL_ERROR` + fallback. Model refusal/safety block → `LLM_SAFETY_BLOCKED` + fallback, **with no retry-around the safety boundary**. Invalid schema → one repair attempt within budget, else `LLM_OUTPUT_INVALID` + fallback.

**Output handling.** A coarse hazardous-content screen blocks genuinely unsafe output (synthesis/dosage). Per-field overclaim handling (with a safe-rewrite path) is done by the reasoner services. Chain-of-thought is stripped defensively and never stored. Fallbacks and safety blocks are recorded in the AI ledger and reports.
