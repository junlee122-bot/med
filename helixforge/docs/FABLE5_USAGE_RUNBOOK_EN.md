# Fable 5 Usage Runbook (EN)

> Research decision support only. Fable 5 is optional and never supplies scientific ground truth. No wet-lab protocol, synthesis route, dosage, or medical advice. No hidden chain-of-thought. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Run WITHOUT an API key (default).** Do nothing — the app runs deterministically. `/api/llm/health` reports `llm_available: false` and the reason. Every reasoning step uses a deterministic fallback and is labeled `DETERMINISTIC_FALLBACK`.

**Run with Sonnet dev mode.** Set `ANTHROPIC_API_KEY=...`, `HELIXFORGE_USE_LLM=true`, `HELIXFORGE_LLM_MODE=HYBRID_LLM_DEV`. Planner/critic use Sonnet 5; hypotheses use the dev model. Run `POST /api/workflow/run-hybrid-agentic-pipeline` with `mode: HYBRID_LLM_DEV`.

**Run the final Fable snapshot.** Set `HELIXFORGE_LLM_MODE=HYBRID_FABLE_FINAL`. Fable 5 is used for hypotheses + critic. Enable `create_hybrid_snapshot: true` to capture a replayable snapshot for the demo.

**Tiny live smoke test.** Set `HELIXFORGE_ENABLE_LIVE_LLM_SMOKE=true` and call `POST /api/llm/live-smoke` (or the button on `/llm`). Off by default.

**Cost control.** `HELIXFORGE_LLM_MAX_COST_PER_RUN_USD` / `..._PER_DAY_USD`. Watch the cost ledger on `/llm`; reset per session as needed.

**Safety.** No key or a safety refusal always yields a deterministic fallback — Fable output is never faked. See HYBRID_SAFETY_AND_FALLBACK.md.
