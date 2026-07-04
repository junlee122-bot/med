# Phase 7 Changelog — Fable 5 Hybrid Agentic Layer

Phase 7 turned HelixForge from a strong deterministic tool-grounded pipeline into a
**hybrid agentic system**: an optional Fable 5 reasoning layer performs dynamic
planning, evidence-grounded hypothesis reasoning, and semantic critique, while the
deterministic scientific tools validate, score, audit, and constrain everything.
The deterministic backbone is unchanged and remains the default + safe fallback.

> Fable 5 is optional and never supplies scientific ground truth. No wet-lab
> protocol, synthesis route, dosage, or medical advice. No hidden chain-of-thought.
> Final responsibility belongs to the human research team.

## What changed (wording — read this first)
We do **not** claim full agent autonomy, drug discovery, efficacy validation, or
clinical/regulatory validation. Instead we say:
- HelixForge uses a **deterministic scientific validation backbone** and an
  **optional Fable 5 reasoning layer**.
- Fable 5 is used for **dynamic planning, evidence-grounded hypothesis reasoning,
  and semantic critique**.
- All Fable outputs are **validated by deterministic scientific tools and
  governance gates**.
- Retrospective rediscovery evaluates whether **known drug/chemotype signals can be
  recovered** from public data — not de novo discovery.
- Molecule optimization is **in-silico candidate prioritization**, not synthesis or
  experimental validation.

## New (all optional; deterministic fallback always available)
- `app/llm/` — the optional LLM layer: config, schemas, cost estimator, safety
  envelope, output validators, versioned prompt templates (+ 6 prompt files),
  prompt cache, replay store, model router + cost guard, Anthropic adapter, and
  `call_llm()` (the single entry point). `FakeLLMClient` for offline tests.
- `dynamic_planner.py` + `hybrid_planner_agent.py` — LLM plan → deterministic
  validation (dependency + safety rules; rejects synthesis/wet-lab/dosage stages)
  → fixed-plan fallback; replanning on failure.
- `hypothesis_reasoner.py` + `fable_hypothesis_agent.py` — evidence-grounded
  hypotheses; fabricated/failed evidence IDs dropped; language-lint + safe-rewrite;
  evidence-graded; deterministic template fallback.
- `semantic_critic.py` + `semantic_critic_agent.py` — LLM critique on top of the
  rule-based critic; validated items → revision events; deterministic fallback.
- `hybrid_pipeline.py` — `/api/workflow/run-hybrid-agentic-pipeline` orchestrating
  the backbone + Fable reasoning + rediscovery + optimization + critic, with cost /
  safety / evidence / claim summaries and honest status.
- `hybrid_snapshot.py` — hybrid record/replay (no keys/prompts/CoT stored; replay
  makes zero live calls).
- `rediscovery/` — true retrospective chemotype-recovery benchmark (17 RDKit-valid
  comparators; modality-mismatch handling; never overclaims discovery).
- `optimization_loop/` — safe in-silico optimization loop (selection + local
  heuristic generation; REINVENT4 never faked; no synthesis content).
- AI ledger upgraded for LLM_CALL / LLM_REPLAY / router / budget-guard decisions.
- `provenance.redact_secrets` now redacts `sk-ant-`/`sk-` keys + Authorization.
- Release readiness gains 8 non-blocking hybrid categories; rubric mapping mentions
  the Fable layer. A deterministic demo is always supported.

## Frontend
`/llm` (LLM Router: mode, key status, routing, budget guard, cost ledger, health,
prompt templates, live-smoke), `/hybrid` (run the hybrid pipeline), `/rediscovery`,
`/optimization-loop`, plus a ReasoningBadge distinguishing real/recorded/fallback.

## API-key behavior
No key / `USE_LLM=false` (default) → deterministic fallback everywhere, clearly
labeled. With a key + `HYBRID_LLM_DEV`/`HYBRID_FABLE_FINAL`, real calls are possible;
mocked in tests, and a gated `/api/llm/live-smoke` allows one tiny real call.

## Tests
`FakeLLMClient` drives all offline LLM tests (no-key fallback, budget/safety/schema/
tool-error paths, planner validation, evidence-ID rejection, overclaim rewrite,
critic revision events, hybrid snapshot replay, cost guard, config masking).
`live_llm`-marked tests are opt-in and excluded from default CI.

## Final validation
- Backend: `pytest app/tests -q` → **all green** (see final run below).
- Frontend: `tsc --noEmit` clean; `vite build` passes.
- `docker compose config` → OK. `check_repo_hygiene.py` → PASS.
- No `check_api_contract.py` / `final_demo_acceptance.py` / `cold_start_smoke.py`
  in this repo (referenced in the brief but not present); `npm run check:routes`
  is not a defined script.
