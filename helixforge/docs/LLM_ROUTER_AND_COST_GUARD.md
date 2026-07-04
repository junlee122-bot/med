# LLM Router and Cost Guard

> Research decision support only. Fable 5 is optional and never supplies scientific ground truth. No wet-lab protocol, synthesis route, dosage, or medical advice. No hidden chain-of-thought. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Modules:** `app/llm/model_router.py`, `app/llm/cost_estimator.py` · **Endpoints:** `/api/llm/{router,router/preview,router/set-mode,costs,cost-ledger,budget/check,pricing}`

**Routing policy.** Fable 5 is reserved for high-value reasoning (hypotheses, critic in final mode). Planner: Sonnet 5 in dev, Fable in final. Report/proposal summaries: Haiku/Sonnet. Formatting/extraction: Haiku or deterministic. Routine work never uses Fable.

**Cost guard.** Estimates cost before every call; blocks (or routes down) when a call would exceed the **per-run** (`HELIXFORGE_LLM_MAX_COST_PER_RUN_USD`, default $2) or **per-day** (`..._PER_DAY_USD`, default $20) budget, recording a budget event. Actual usage is taken from the API response when available. The cost ledger is visible in the UI and resettable per session.

**Pricing.** A configurable SNAPSHOT (USD per million tokens): Fable 5 10/50, Opus 4.8 5/25, Sonnet 5 3/15 (promotional override via env), Haiku 4.5 1/5. Pricing is not immutable truth — verify in the provider console. The cost guard, budget, and cost ledger are shown on the `/llm` page.

**Prompt cache + replay** further reduce cost: identical in-session calls hit the cache (cost 0), and recorded hybrid runs replay with no live calls.
