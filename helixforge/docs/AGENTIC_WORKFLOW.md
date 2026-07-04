# Agentic Workflow

The agentic layer (`backend/app/agents/`, `backend/app/services/agent_engine.py`)
sits on top of the real tool adapters. It is deterministic — no external LLM key
is required to run — and emits **observable trace only**: plan, task, tool calls,
input/output summary, evidence IDs, validation checks, confidence, warnings,
errors, revision events, and timestamps. It never exposes hidden
chain-of-thought.

## Endpoint

`POST /api/workflow/run-agentic-pipeline`

```json
{
  "condition": "non-small cell lung cancer",
  "target_query": "EGFR",
  "max_results": 8,
  "create_reinvent_config": true,
  "run_vina_fixture": false,
  "evaluation_mode": "retrospective_rediscovery",
  "error_injections": {
    "invalid_smiles": false, "fake_citation": false, "tool_failure": false,
    "safety_flag": false, "overclaim": false, "contradictory_evidence": false
  }
}
```

Returns `run_id`, `plan`, `agent_runs[]`, `steps[]`, `revision_events[]`,
`counts` (by SourceType), `metrics`, `report_id`, `ko_report_id`, `disclaimer`.

## Agents (Orchestrator + 16 specialists)

| # | Agent | Real tools | Output |
|---|---|---|---|
| 0 | Project Orchestrator | Planner | DAG plan, stage assignment |
| 1 | Disease Biology Agent | (query design) | Scope + PubMed query strategy |
| 2 | Evidence Miner | **PubMed** | Evidence items + direction (supports/contradicts) |
| 3 | Citation Verifier | Verifier | VERIFIED/FAILED/UNVERIFIED per identifier |
| 4 | Target Scout | **ChEMBL**, **ClinicalTrials.gov** | Ranked targets (Target Opportunity Score) |
| 5 | Hypothesis Agent | Reasoner | 2–3 conservative, evidence-linked hypotheses |
| 6 | Molecule Design Agent | **ChEMBL**, REINVENT4 (config) | Real candidate structures + config |
| 7 | Cheminformatics Validator | **RDKit**, Safety | SMILES validation + descriptors + per-mol screen |
| 8 | ADMET & Toxicology Agent | **TDC/PyTDC** | Dataset substrate + composite scoring |
| 9 | Binding & Structure Agent | AutoDock Vina | Fixture docking (honest status) |
| 10 | Synthesis Feasibility Agent | — | Feasibility band only (NO routes) |
| 11 | Safety Auditor | Safety | Block/quarantine with non-actionable category |
| 12 | Clinical Strategy Agent | ClinicalTrials.gov (cached) | High-level plan + disclaimer |
| 13 | Regulatory Reviewer | heuristic | Checklist + gaps (honest source labels) |
| 14 | Critic Agent | Verifier | Detects defects → RevisionEvents |
| 15 | Evaluation Agent | EvalHarness | Metrics from observed state |
| 16 | Report Builder | Report | EN technical + KO judge reports (+ safety lint) |

## State machine & tolerance

Stages run in order; each artifact gates the next. A raising agent is recorded
as `FAILED` and the pipeline **continues** (partial-failure tolerant). Status is
`complete`, `warning` (a stage failed or safety blocked something), or `error`.

## Self-correction (RevisionEvents)

The Critic checks a fixed defect taxonomy and records a corrected
`RevisionEvent` for each finding (persisted to `revision_events`, linked to the
original + critic agent runs):

| Injection | Detected by | Correction |
|---|---|---|
| `invalid_smiles` | RDKit (Cheminformatics Validator) | Invalid structure excluded from ranking |
| `fake_citation` | Citation Verifier | Fabricated PMID demoted; hypothesis confidence reduced |
| `overclaim` | Critic (regex) | "validated cure / proven efficacy" → "in-silico hypothesis for expert review" |
| `contradictory_evidence` | Evidence Miner + Critic | Confidence recalculated; uncertainty stated |
| `tool_failure` | Orchestrator | Continue with partial results; limitation recorded (no fabricated result) |
| `safety_flag` | Safety Auditor | Candidate blocked → "Do not advance"; non-actionable category only |

`POST /api/workflow/run-error-injection-demo` runs one scenario and returns the
before/after of the correction it triggered.

## Scoring (transparent)

- **Target Opportunity Score** (`services/scoring.py`): weighted sum of name
  match, target type, organism, ChEMBL confidence, PubMed evidence, clinical
  precedent, activity availability, minus safety/uncertainty penalties →
  0–100. Single-protein human targets are preferred (they carry small-molecule
  bioactivity); protein-protein interactions are penalized.
- **Molecule Composite Score**: QED, Lipinski, activity proxy, druglikeness,
  TDC readiness, provenance, novelty, minus safety + uncertainty penalties.
  Invalid → 0 ("Reject"); BLOCKED → "Do not advance". Every score returns a
  per-input breakdown; missing inputs use conservative defaults **and** emit a
  warning.

## Persistence

New SQLite tables: `agent_runs`, `agent_plans`, `revision_events`, `hypotheses`,
`evaluation_results`, `run_manifests` (JSON-payload rows, Postgres-portable).
Introspection: `/api/workflow/runs/{id}/agents`, `/revisions`, `/manifest`,
`/api/agents`, `/api/agents/runs/{id}`.
