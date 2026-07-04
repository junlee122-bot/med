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
