# HelixForge AI — Agentic Drug-Discovery Workbench

> **The official competition system lives in [`helixforge/`](helixforge/).**
> This root is just a launcher. An early front-end-only mock SPA has been
> archived under [`legacy-demo-spa/`](legacy-demo-spa/) and is **not** the
> submission — ignore it.

Field 4 (융합) entry for the AI Drug Discovery competition: a real, tool-using,
self-correcting **multi-agent** system for evidence-grounded target discovery,
molecule analysis, safety screening, and clinical/regulatory planning — with an
observable audit trail and honest source labels. Not a chatbot; not mock-only.

## Quick start

```bash
# 1) Backend (FastAPI)  →  http://localhost:8000  (Swagger at /docs)
cd helixforge/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# 2) Frontend (Vite/React)  →  http://localhost:5174
cd helixforge/frontend
npm ci
npm run dev

# 3) Or everything via Docker
cd helixforge
docker compose up --build     # backend :8000, frontend :8080
```

### Offline-safe judge demo (flaky network)
The system ships a small, committed **recorded real** snapshot. Open
**Snapshots → Replay** (or **Agent Cockpit → Recorded replay**) to reconstruct a
real run with **zero live API calls** — every result is labeled
`RECORDED_REAL_TOOL_OUTPUT`. See
[`helixforge/docs/RECORD_REPLAY_MODE.md`](helixforge/docs/RECORD_REPLAY_MODE.md).

## Competition status

| Capability | Status |
|---|---|
| PubMed / ChEMBL / ClinicalTrials.gov | **Real** (live HTTP) |
| RDKit, TDC / PyTDC | **Real** (local) |
| AutoDock Vina, REINVENT4 | **Configured-not-run** until installed (honest status; never faked) |
| 17-agent runtime, self-correction, evaluation | **Real / implemented** |
| Record/replay, submission center, release readiness | **Implemented** |
| ADMET baseline model, regulatory RAG | **Planned / heuristic** (labeled honestly) |

Every scientific result carries an honest source type
(`REAL_TOOL_OUTPUT` · `RECORDED_REAL_TOOL_OUTPUT` · `CONFIGURED_BUT_NOT_RUN` ·
`TOOL_ERROR` · `HEURISTIC_ANALYSIS` · `ASSUMPTION` · `BASELINE_MODEL_OUTPUT` ·
`SAFETY_REDACTED` · `HUMAN_INPUT`).

## Safety

Research decision support only. **No** wet-lab protocols, synthesis routes,
reaction conditions, reagent lists, dosage, or medical advice — enforced by
English **and** Korean safety linting. Final responsibility belongs to the human
research team.

## Docs

Start at [`helixforge/README.md`](helixforge/README.md). Key docs:
[architecture](helixforge/docs/ARCHITECTURE.md) ·
[agentic workflow](helixforge/docs/AGENTIC_WORKFLOW.md) ·
[record/replay](helixforge/docs/RECORD_REPLAY_MODE.md) ·
[safety policy](helixforge/docs/SAFETY_POLICY.md) ·
[data rights](helixforge/docs/DATA_RIGHTS_AND_ATTRIBUTION.md) ·
[Korean proposal](helixforge/docs/FULL_PROPOSAL_DRAFT_KO.md) ·
[demo runbook (KO)](helixforge/docs/DEMO_RUNBOOK_KO.md) ·
[Phase 4 audit](helixforge/docs/PHASE4_BLIND_SPOT_AUDIT.md).
