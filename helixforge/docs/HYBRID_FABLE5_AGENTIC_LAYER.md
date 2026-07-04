# Hybrid Fable 5 Agentic Layer

HelixForge is a **deterministic scientific validation backbone** with an **optional
Fable 5 reasoning layer**. Fable 5 is used for three high-value reasoning steps —
dynamic planning, evidence-grounded hypothesis reasoning, and semantic critique —
while deterministic scientific tools validate, score, audit, and constrain every
output. The app runs fully **without any API key**: every reasoning step degrades
to a deterministic fallback and says so.

> Research decision support only. Fable 5 never supplies scientific ground truth —
> scientific facts come only from PubMed, ChEMBL, ClinicalTrials.gov, RDKit, TDC.
> No wet-lab protocol, synthesis route, reaction condition, reagent list,
> purification, dosage, or medical advice. No hidden chain-of-thought. Final
> responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

## What Fable 5 does (and does not)
- **Dynamic planning** — proposes which pipeline stages to run and in what order.
  A deterministic validator enforces dependency + safety rules and rejects any
  wet-lab/synthesis/dosage stage; the fixed stage list is the fallback.
- **Evidence-grounded hypothesis reasoning** — proposes conservative, testable
  hypotheses citing ONLY provided evidence IDs. Fabricated/failed citations are
  dropped, every statement passes the language lint (with one safe-rewrite
  attempt), and each hypothesis is evidence-graded.
- **Semantic critique** — flags subtle overclaim / evidence-gap / source-confusion
  / clinical-overreach issues the rule-based critic may miss; every item is
  validated (cited IDs exist, no chain-of-thought, safe rewrites lint-clean) and
  converted into a revision event.

Fable is **not** used to compute activity, generate scientific data, or make a
clinical/regulatory determination. It does not run all "17 agents" — those remain
deterministic role modules; Fable augments planning, hypotheses, and critique.

## Four modes (`HELIXFORGE_LLM_MODE`)
| Mode | Live calls | Use |
|---|---|---|
| `DETERMINISTIC_ONLY` (default) | none | current behavior; safe fallback |
| `HYBRID_LLM_DEV` | cheaper model (Sonnet 5) | development / iteration |
| `HYBRID_FABLE_FINAL` | Fable 5 for reasoning only | final snapshot / demo recording |
| `RECORDED_HYBRID_REPLAY` | none | replays a captured hybrid run |

## Reasoning source types (separate from scientific source_type)
`REAL_LLM_OUTPUT`, `RECORDED_LLM_OUTPUT`, `DETERMINISTIC_FALLBACK`,
`LLM_TOOL_ERROR`, `LLM_BUDGET_BLOCKED`, `LLM_SAFETY_BLOCKED`, `LLM_OUTPUT_INVALID`.
Scientific facts keep their own labels (`REAL_TOOL_OUTPUT`, etc.). The two are
never mixed.

## The single entry point: `app.llm.call_llm()`
Every reasoning call goes through one function that handles: no-key/deterministic
fallback, model routing, per-run/day cost guard, prompt cache, replay lookup,
safety-refusal detection (no retry-around), a coarse hazardous-content output
screen, JSON schema validation with one repair, the AI-interaction ledger, and the
LLM-calls store. It ALWAYS returns an `LLMResult` and never raises — when the
result is not usable, the caller uses its deterministic fallback.

## Every Fable output is gated by
citation verification · evidence grading · source-type governance · safety lint ·
scientific language lint · claim inventory · human/expert review.

## Endpoints
`/api/llm/*` (config/health/router/costs/ledger/pricing/prompt-templates/replay/
live-smoke), `/api/workflow/plan-hybrid`, `/api/hypotheses/generate-hybrid`,
`/api/critic/semantic/run/{run_id}`, `/api/workflow/run-hybrid-agentic-pipeline`.

## Frontend
`/llm` (LLM Router), `/hybrid` (run the hybrid pipeline), plus badges throughout
distinguishing REAL_LLM_OUTPUT / RECORDED_LLM_OUTPUT / DETERMINISTIC_FALLBACK.
