# HelixForge AI — Integration-First Monorepo

A **real**, integration-first multi-agent AI drug-discovery platform for the
Field 4 competition track: autonomous hypothesis generation, tool-based molecule
analysis, safety/toxicity screening, clinical/regulatory planning, and
transparent audit logging.

> **This is not a mock demo.** The backend connects to **live** scientific APIs
> and runs **real** local tools. Every tool result is labeled with its true
> provenance — `REAL_TOOL_OUTPUT`, `DEMO_FALLBACK`, `CONFIGURED_BUT_NOT_RUN`,
> `TOOL_ERROR`, or `HUMAN_INPUT`. Missing tools are reported honestly; results
> are never fabricated.

> **Research decision support only.** No wet-lab protocols, synthesis routes,
> reagent lists, reaction conditions, dosage, or medical advice are produced.
> Final responsibility belongs to the human research team.

---

## What is real here

| Tool | Type | Status in a clean install |
|---|---|---|
| **PubMed** (NCBI E-utilities) | Live HTTP | `REAL_TOOL_OUTPUT` — real PMIDs, titles, abstracts |
| **ClinicalTrials.gov v2** | Live HTTP | `REAL_TOOL_OUTPUT` — real NCT trials |
| **ChEMBL web services** | Live HTTP | `REAL_TOOL_OUTPUT` — real targets, molecules, activities |
| **RDKit** | Local (pip/conda) | `REAL_TOOL_OUTPUT` — real validation & descriptors |
| **TDC / PyTDC** | Local (pip) | `REAL_TOOL_OUTPUT` — real ADME/Tox datasets (downloads on first use) |
| **AutoDock Vina** | Local binary | `CONFIGURED_BUT_NOT_RUN` until `VINA_BIN` resolves; fixture-based dock |
| **REINVENT4** | External install | `CONFIGURED_BUT_NOT_RUN` until `REINVENT4_PYTHON` is set; real config generation |
| **Safety screen / Report** | Local | Real screening & Markdown/JSON report generation |

Verified in this environment: PubMed, ClinicalTrials.gov, ChEMBL return live
data through the network; RDKit and PyTDC run locally (a real `Caco2_Wang` load
returns 910 rows with train/valid/test splits); the full `run-real-pipeline`
completes end-to-end with partial-failure tolerance.

---

## Agentic layer (Phase 2)

On top of the real adapters sits an explicit, observable **multi-agent runtime**
(deterministic; no LLM key required to run). It shows judges autonomy,
tool-grounded reasoning, and **visible self-correction** — not a chatbot.

- **17 agents** (Orchestrator + 16 specialists) run a 16-stage DAG; each emits
  observable trace only (plan, tool calls, validation, confidence, next action),
  never hidden chain-of-thought. Persisted as `AgentRun` / `AgentPlan`.
- **Self-correction:** a Critic detects invalid SMILES, fabricated citations,
  tool failures, safety hazards, overclaims, and contradictions, and records a
  before/after `RevisionEvent`. Six one-click injection demos prove it.
- **Transparent scoring:** Target Opportunity + Molecule Composite scores with a
  per-input breakdown; conservative defaults + warnings; invalid → 0, blocked →
  do-not-advance.
- **Evaluation Bench:** tool-integration, evidence-integrity, molecule-validity,
  agent-autonomy, resource-efficiency, and EGFR/NSCLC retrospective-rediscovery
  metrics — all computed from observed run state.
- **Reports:** Korean judge report + English technical report, safety-linted
  before export; JSON audit + export bundle + run manifest.

Run it:

```bash
curl -X POST http://localhost:8000/api/workflow/run-agentic-pipeline \
  -H 'Content-Type: application/json' \
  -d '{"condition":"non-small cell lung cancer","target_query":"EGFR","max_results":6,
       "error_injections":{"invalid_smiles":true,"fake_citation":true,"overclaim":true}}'
```

Or in the UI: **Agent Cockpit** (toggle injections → Run) · **Demo Lab**
(self-correction scenarios) · **Evaluation Bench** · **Presentation Mode**.

**Frontend pages:** Overview, Tool Registry, Agent Cockpit, Demo Lab, Evidence
Explorer, Targets, Hypotheses, Molecule Lab, TDC Bench, Docking Lab, REINVENT4
Studio, Clinical & Regulatory, Safety Gate, Evaluation Bench, Impact, Rubric
Alignment, Reports, Presentation Mode, Settings.

See **[docs/AGENTIC_WORKFLOW.md](docs/AGENTIC_WORKFLOW.md)** and
**[docs/EVALUATION_BENCH.md](docs/EVALUATION_BENCH.md)**. Competition materials:
**[proposal (KO)](docs/COMPETITION_PROPOSAL_DRAFT_KO.md)** ·
**[presentation script (KO)](docs/FINAL_PRESENTATION_SCRIPT_KO.md)** ·
**[rubric (KO)](docs/RUBRIC_ALIGNMENT_KO.md)** ·
**[demo runbook (KO)](docs/DEMO_RUNBOOK_KO.md)** ·
**[limitations & roadmap](docs/LIMITATIONS_AND_ROADMAP.md)** ·
**[third-party tools](docs/THIRD_PARTY_TOOLS.md)**.

---

## Submission-grade hardening (Phase 3)

Makes the system survive demo-day networks, peer review, and final packaging —
without weakening any real integration.

- **Record / replay** — capture a real run, replay it offline with no live calls,
  labeled `RECORDED_REAL_TOOL_OUTPUT`; reports disclose original + replay
  timestamps. A small built-in EGFR/NSCLC snapshot ships for out-of-the-box
  offline demo. Cockpit has a **live / recorded-replay** toggle. Page: **Snapshots**.
- **Evidence QA linter** — blocks failed-citation-as-verified, missing
  provenance, invalid-molecule recommendations before export.
- **AI Interaction Ledger** — logs every agent step (deterministic by default,
  no LLM), redacts secrets, never stores chain-of-thought. Page: **AI Ledger**.
- **Release Readiness** — 0–100 score + checklist mapped to the rubric.
- **Submission Center** — one-click Korean proposal / technical appendix / ethics
  appendix / peer-review (KO) / demo script / judge README + JSON bundle.
- **Scientific depth** — ChEMBL assay-quality analysis, RDKit molecule
  diversity/scaffolds, activity-aware scoring, and an 8-scenario robustness matrix.
- **Security self-audit** — verifies secret redaction and `.env` hygiene.

New source labels: `RECORDED_REAL_TOOL_OUTPUT`, `BASELINE_MODEL_OUTPUT`,
`HEURISTIC_ANALYSIS`, `ASSUMPTION`, `SAFETY_REDACTED`.

See **[docs/PHASE3_CHANGELOG.md](docs/PHASE3_CHANGELOG.md)** and
**[docs/RECORD_REPLAY_MODE.md](docs/RECORD_REPLAY_MODE.md)**.

### Offline-safe judge demo
If the network is flaky, open **Snapshots → Replay** (or Cockpit → Recorded
replay) to reconstruct a real run with zero live calls — everything is labeled
`RECORDED_REAL_TOOL_OUTPUT`.

---

## Repository layout

```
helixforge/
  backend/            FastAPI app (Python 3.11)
    app/
      main.py         app factory + router mounting
      config.py       env + runtime settings (secrets masked)
      api/            one router per tool group + workflow/audit/report/settings
      adapters/       ToolAdapter classes (health_check/run/validate_output/fallback)
      services/       audit logging, HTTP client, pipeline orchestration
      models/         Pydantic schemas + SourceType enum
      storage/        SQLite persistence (Postgres-ready abstraction)
      tests/          smoke tests
    fixtures/vina/    sample ligand/receptor for fixture docking
    requirements.txt  environment.yml  Dockerfile
  frontend/           Vite + React + TypeScript + Tailwind
    src/pages/        Overview, ToolRegistry, Cockpit, EvidenceExplorer,
                      MoleculeLab, TDCBench, DockingLab, ReinventStudio,
                      SafetyGate, Reports, Settings
    src/lib/api.ts    typed API client
  docker-compose.yml
  .env.example
  docs/               ARCHITECTURE · TOOL_INTEGRATION · SAFETY_POLICY · RUNBOOK
```

---

## Quick start (local, no Docker)

### 1. Backend

```bash
cd helixforge/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # installs FastAPI, httpx, RDKit, PyTDC…
cp ../.env.example ../.env                # optional; all values are optional
uvicorn app.main:app --reload --port 8000
```

- API: <http://localhost:8000>
- Interactive docs (Swagger): <http://localhost:8000/docs>
- Health: <http://localhost:8000/api/health> · Tool health: `/api/tools/health`

> RDKit and PyTDC are heavy. If a wheel is unavailable on your platform, use the
> conda environment instead: `conda env create -f environment.yml`.

### 2. Frontend

```bash
cd helixforge/frontend
npm install
npm run dev            # http://localhost:5174 ; /api is proxied to :8000
```

For a production build pointed at a remote backend:
`VITE_API_BASE=https://your-host npm run build`.

### 3. Run the tests

```bash
cd helixforge/backend && source .venv/bin/activate
pytest app/tests -v
```

The smoke suite exercises real endpoints (PubMed / ClinicalTrials / ChEMBL /
RDKit / TDC) and the honest-degradation paths (Vina / REINVENT4).

---

## Run with Docker Compose

```bash
cd helixforge
cp .env.example .env       # optional
docker compose up --build
# backend  -> http://localhost:8000  (Swagger at /docs)
# frontend -> http://localhost:8080  (nginx serves the SPA and proxies /api → backend)
```

---

## Run the EGFR / NSCLC pipeline

The flagship integration path. It searches PubMed, ChEMBL targets + activities,
and ClinicalTrials.gov; extracts candidate SMILES from ChEMBL structures;
validates them with RDKit; loads a TDC ADME dataset; optionally runs Vina fixture
docking and creates a REINVENT4 config; runs the safety gate; and builds a
report. It continues with partial results if any tool fails.

```bash
curl -X POST http://localhost:8000/api/workflow/run-real-pipeline \
  -H 'Content-Type: application/json' \
  -d '{"condition":"non-small cell lung cancer","target_query":"EGFR","max_results":5}'
```

Or from the UI: **Agent Cockpit → Run full real pipeline**, then **Reports** to
export Markdown / JSON.

---

## Configure tools

Set values in `.env` (defaults) or at runtime via **Settings** (stored
server-side; the NCBI key is masked and never logged):

- `NCBI_API_KEY`, `NCBI_EMAIL` — raise PubMed rate limits / identify per NCBI policy
- `VINA_BIN` — enable real AutoDock Vina docking
- `REINVENT4_PYTHON` / `REINVENT4_BIN` — enable real REINVENT4 runs
- `CHUNK_SIZE`, `TIMEOUT_SECONDS` — external API pagination & timeout

See **[docs/TOOL_INTEGRATION.md](docs/TOOL_INTEGRATION.md)** for per-tool setup,
and **[docs/RUNBOOK.md](docs/RUNBOOK.md)** for operations & troubleshooting.

---

## Safety

Enforced in code (`app/adapters/safety_adapter.py`) and documented in
**[docs/SAFETY_POLICY.md](docs/SAFETY_POLICY.md)**. The system refuses wet-lab
protocols, synthesis routes, reagent/condition lists, dosage, and any
toxicity-enhancement request; it screens outputs, quarantines hazardous content,
and attaches the human-responsibility statement to every report.

---

## Phase 5 — Professional scientific validation layer

A deterministic, testable review layer for expert reviewers (computational /
medicinal chemists, bioinformaticians, translational & clinical reviewers,
regulatory & AI/ML reviewers). Highlights:

- **Evidence grading** — 9-level evidence hierarchy → A–F claim grades (assay ≠
  efficacy; precedent ≠ proof; failed citation → E; contradiction → F).
- **Chemistry rigor** — ChEMBL activity normalization (conservative units,
  endpoint comparability, assay-confidence reliability), medicinal-chemistry
  review (Lipinski/Veber/lead-likeness + PAINS), and applicability domain.
- **Model / docking rigor** — leakage-aware ADMET baseline protocol (real metrics
  or honest skip), governed docking protocol records (never binding proof).
- **Translational & clinical** — TRL readiness capped at TRL_4 (no wet-lab);
  clinical precedent as precedent, not efficacy.
- **Governance & docs** — 16-category professional release scorecard, role-based
  expert review board, model/data/risk/validation/traceability docs, a 25-section
  KO/EN scientific whitepaper, and a "What We Do NOT Claim" sheet.

Expert UI: `/evidence-grading`, `/molecule-qa`, `/professional-review`,
`/expert-review`, `/professional-docs`. See **docs/PHASE5_PROFESSIONALISM_AUDIT.md**
and **docs/PHASE5_CHANGELOG.md**.
