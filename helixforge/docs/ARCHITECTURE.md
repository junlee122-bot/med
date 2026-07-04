# HelixForge AI — Architecture

## Overview

HelixForge is an **integration-first** backend with a thin, typed React
frontend. The backend is the source of truth: it owns all tool execution,
persistence, auditing, and safety. The frontend never simulates scientific
results — it only renders what the backend returns, including provenance labels.

```
┌──────────────────────────────┐        ┌───────────────────────────────────────────┐
│  Frontend (Vite/React/TS)    │  HTTP  │  Backend (FastAPI, Python 3.11)             │
│  - pages call src/lib/api.ts │ ─────▶ │  api/ routers → adapters/ → services/       │
│  - SourceType badges         │ ◀───── │  every call ⇒ ToolRun + AuditEvent (SQLite) │
└──────────────────────────────┘  JSON  └───────────────────────────────────────────┘
                                              │             │              │
                                        live HTTP APIs  local tools   external installs
                                        PubMed/CT.gov/   RDKit / TDC   Vina / REINVENT4
                                        ChEMBL
```

## Layers

1. **API routers** (`app/api/*`) — one router per tool group plus workflow,
   audit, report, and settings. Thin: validate the request, call an adapter or
   the pipeline service, return a Pydantic response.
2. **Adapters** (`app/adapters/*`) — one class per tool implementing the common
   `ToolAdapter` interface. All external/scientific I/O lives here.
3. **Services** (`app/services/*`) — cross-cutting concerns: `audit` (ToolRun +
   AuditEvent creation), `httpclient` (shared httpx client with retry/timeout),
   `pipeline` (the EGFR/NSCLC orchestration).
4. **Models** (`app/models/schemas.py`) — Pydantic request/response models, the
   `SourceType` and `ValidationStatus` enums, and the `ToolEnvelope` base that
   every tool response extends.
5. **Storage** (`app/storage/db.py`) — SQLite persistence with a narrow function
   API (`init_db`, insert/query helpers) so the store can be swapped for
   Postgres without touching callers.

## The tool contract

Every adapter implements:

```python
class ToolAdapter:
    id: str; name: str; category: str
    def health_check(self) -> ToolHealth: ...
    def run(self, input: dict) -> ToolResult: ...
    def validate_output(self, output: dict) -> ValidationResult: ...
    def fallback(self, input: dict) -> ToolResult: ...
```

Every tool result carries the same envelope fields: `tool_name`, `source`,
`source_type`, `input_summary`, `output_summary`, `retrieved_at`,
`validation_status`, `errors`, `warnings`, `audit_event_id`.

### SourceType — the honesty contract

| Value | Meaning |
|---|---|
| `REAL_TOOL_OUTPUT` | A real tool/API produced this result. |
| `DEMO_FALLBACK` | A clearly-labeled synthetic fallback (used sparingly, never for the live APIs). |
| `CONFIGURED_BUT_NOT_RUN` | The tool is wired but its runtime isn't installed/configured (e.g. Vina, REINVENT4). |
| `TOOL_ERROR` | The tool was attempted and failed; the error is recorded. |
| `HUMAN_INPUT` | A value supplied by a human, not a tool. |

The registry never upgrades a `CONFIGURED_BUT_NOT_RUN`/`TOOL_ERROR` to
`REAL_TOOL_OUTPUT`. This is the core anti-fabrication guarantee.

## Workflow state machine

`run-real-pipeline` executes ordered steps, each producing a `WorkflowStep`
(with its `source_type`) and audit events. A failing step is recorded and the
pipeline continues with partial results — it does not abort. Steps:

```
PubMed → ChEMBL targets → ChEMBL activities → ClinicalTrials.gov
      → extract candidate SMILES → RDKit validate → TDC dataset load
      → (optional) Vina fixture dock → (optional) REINVENT4 config
      → Safety gate → Report build
```

## Persistence & entities

SQLite tables mirror the data model: `Project`, `WorkflowRun`, `ToolRun`,
`AuditEvent`, `EvidenceItem`, `TargetCandidate`, `MoleculeCandidate`,
`DockingJob`, `ReinventJob`, `TdcDatasetRecord`, `SafetyFlag`, `Report`. Every
tool call writes a `ToolRun` and an `AuditEvent`; `/api/audit/events` exposes the
trail.

## Frontend

Vite + React + TypeScript + Tailwind. `src/lib/api.ts` is a fully-typed client
mirroring the backend schemas. Pages are self-contained: they call the API,
render loading/error/empty states, and show a `SourceBadge` for every result. A
dev proxy forwards `/api` to `:8000`; `VITE_API_BASE` overrides for production.

## Extensibility

- **Postgres:** replace the SQLite helpers in `storage/db.py`; callers are
  unaffected.
- **New tool:** add an adapter implementing `ToolAdapter`, register it in
  `adapters/registry.py`, add a router, and (optionally) a page.
- **Background jobs:** Vina/REINVENT jobs already return `job_id` + status; wire
  a queue (RQ/Celery) behind the same endpoints for long runs.
