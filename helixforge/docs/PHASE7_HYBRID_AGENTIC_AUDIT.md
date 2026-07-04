# Phase 7 — Hybrid Agentic Layer Audit

Phase 7 adds an **optional** Fable 5 / LLM reasoning layer on top of the existing
deterministic, tool-grounded backbone. The deterministic pipeline remains the
default and the safe fallback. Labels:
**IMPLEMENTED · PARTIALLY_IMPLEMENTED · FALLBACK_ONLY · CONFIGURED_BUT_NOT_RUN · INTENTIONAL_LIMITATION · NEEDS_REVIEW**.

> Research decision support only. Fable 5 is used for planning, evidence-grounded
> hypothesis reasoning, and semantic critique — never as scientific ground truth.
> Scientific facts come only from PubMed, ChEMBL, ClinicalTrials.gov, RDKit, TDC.
> No wet-lab protocol, synthesis route, reaction condition, reagent list,
> purification, dosage, or medical advice. No hidden chain-of-thought. Final
> responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

## 0. Baseline validation (before Phase 7)
- **Backend:** `pytest app/tests -q` → **186 passed**.
- **Frontend:** `tsc --noEmit` clean; `vite build` passes (one non-blocking Vite chunk-size warning). `npm run check:routes` — **no such script** (does not exist in this repo; noted, not a regression).
- **Docker:** `docker compose config` → OK.
- **Hygiene:** `python scripts/check_repo_hygiene.py` → PASS. (Other scripts referenced in the brief — `check_api_contract.py`, `final_demo_acceptance.py`, `cold_start_smoke.py` — do not exist in this repo.)

## Current deterministic limitations (the weakness Phase 7 addresses)
- The Orchestrator uses a fixed stage list (`AGENT_SEQUENCE`); no dynamic planning.
- Hypothesis generation (`hypothesis_agent.py`) is templated string composition.
- The critic (`critic_agent.py`) is a fixed defect-taxonomy rule engine.
- "Retrospective rediscovery" is a pipeline sanity check, not true known-drug recovery.
- No molecule optimization *loop* — candidates are imported and scored once.

## Architecture: the LLM layer is optional and governed
Four modes (`LLMMode`): `DETERMINISTIC_ONLY` (default, no external calls),
`HYBRID_LLM_DEV` (cheaper model for iteration), `HYBRID_FABLE_FINAL` (Fable 5 for
the highest-value steps only), `RECORDED_HYBRID_REPLAY` (replays a captured hybrid
run, no live calls). Every LLM output flows through the existing gates: citation
verification, evidence grading, source-type governance, safety lint, scientific
language lint, claim inventory, and human/expert review. Scientific `source_type`
and LLM `reasoning_source_type` are kept strictly separate.

## API-key & fallback behavior (contract)
- `HELIXFORGE_USE_LLM=false` (default) → `DETERMINISTIC_FALLBACK`.
- `ANTHROPIC_API_KEY` missing → `DETERMINISTIC_FALLBACK` + warning.
- Cost budget exceeded → `LLM_BUDGET_BLOCKED` + deterministic fallback.
- API error → `LLM_TOOL_ERROR` + fallback. Safety refusal → `LLM_SAFETY_BLOCKED` + fallback (no retry-around).
- Invalid schema → one repair attempt within budget, else `LLM_OUTPUT_INVALID` + fallback.

## Implementation status (updated as modules land)
1. LLM adapter + config + no-key fallback + safety envelope — **IMPLEMENTED**
2. Model router + cost guard + cost estimator — **IMPLEMENTED**
3. AI ledger upgrade for LLM_CALL — **IMPLEMENTED**
4. Hybrid dynamic planner + replanning — **IMPLEMENTED**
5. Evidence-grounded hypothesis reasoner — **IMPLEMENTED**
6. Semantic critic (Fable-assisted) — **IMPLEMENTED**
7. Hybrid pipeline endpoint — **IMPLEMENTED**
8. Hybrid snapshot + replay — **IMPLEMENTED**
9. True retrospective rediscovery — **IMPLEMENTED**
10. Safe molecule optimization loop — **IMPLEMENTED**
11. Frontend (LLM Router, Hybrid Cockpit, Rediscovery, Optimization) — **IMPLEMENTED**
12. Docs + proposal wording — **IMPLEMENTED**
13. Release readiness + rubric — **IMPLEMENTED**

Live Fable/Sonnet calls: **CONFIGURED_BUT_NOT_RUN** by default (no key in this
environment) — exercised via a deterministic FakeLLMClient in tests; a gated
`/api/llm/live-smoke` endpoint allows a tiny real call when a key + opt-in env are set.

## Final validation
See `PHASE7_CHANGELOG.md` for the final test/build/compose results.
