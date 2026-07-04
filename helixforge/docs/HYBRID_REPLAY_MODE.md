# Hybrid Replay Mode

> Research decision support only. Fable 5 is optional and never supplies scientific ground truth. No wet-lab protocol, synthesis route, dosage, or medical advice. No hidden chain-of-thought. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Module:** `app/services/hybrid_snapshot.py` · **Endpoints:** `/api/snapshots/{create-hybrid-from-run/{run_id},{id}/replay-hybrid,{id}/llm-ledger,{id}/cost-summary}`

**What it captures.** Deterministic tool outputs (as recorded real data) + LLM call metadata: model, purpose, prompt-template id/hash, input/output hashes, token usage, cost estimate, validation + fallback + safety status, and the reasoning JSON (redacted). It does **not** store API keys, secrets, unsafe content, hidden chain-of-thought, or full prompts (unless explicitly enabled, and then redacted).

**Replay.** `RECORDED_HYBRID_REPLAY` mode and `replay-hybrid` serve recorded LLM outputs labeled `RECORDED_LLM_OUTPUT` and recorded tool data as `RECORDED_REAL_TOOL_OUTPUT`, with **zero live API calls**. This is the offline-safe path for demo recording and judging.
