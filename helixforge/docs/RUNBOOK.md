# Runbook — Operations & Troubleshooting

## Start / stop

### Local
```bash
# backend
cd helixforge/backend && source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
# frontend (separate shell)
cd helixforge/frontend && npm run dev
```

### Docker
```bash
cd helixforge && docker compose up --build      # -d to detach
docker compose down                              # stop
```

## Health & smoke checks

When `HELIXFORGE_API_TOKEN` is configured, only `/api/health` is public. Add
`-H "Authorization: Bearer $HELIXFORGE_API_TOKEN"` to every other API request.

```bash
curl http://localhost:8000/api/health            # service liveness
curl http://localhost:8000/api/tools/health      # per-tool status matrix
cd helixforge/backend && pytest app/tests -v     # full smoke suite
```

Expected on a clean install: PubMed / ClinicalTrials / ChEMBL / RDKit / TDC →
`AVAILABLE` + `REAL_TOOL_OUTPUT`; Vina / REINVENT4 → `NOT_CONFIGURED` +
`CONFIGURED_BUT_NOT_RUN`.

## Run the flagship pipeline

```bash
curl -X POST http://localhost:8000/api/workflow/run-real-pipeline \
  -H 'Content-Type: application/json' \
  -d '{"condition":"non-small cell lung cancer","target_query":"EGFR","max_results":5}'
```
Then `GET /api/report/{report_id}` (id is in the response) or use the Reports page.

## Configuration

- `.env` (copy from `.env.example`) supplies defaults.
- Runtime overrides via `POST /api/settings` or the Settings page — stored
  server-side under `backend/data/runtime_settings.json`. The NCBI key is masked
  in every response (only the last 4 chars ever shown) and never logged.

## Common issues

Security-sensitive executable paths (`VINA_BIN`, `REINVENT4_BIN`, and
`REINVENT4_PYTHON`) are deployment-only and cannot be changed through the HTTP
Settings API. Production requires both `ENVIRONMENT=production` and a strong
`HELIXFORGE_API_TOKEN`.

| Symptom | Cause | Fix |
|---|---|---|
| Routes missing / `include_router` adds 1 route | Incompatible `starlette` (1.x) pulled in | Use pinned `requirements.txt` (`fastapi==0.115.6`, `starlette>=0.40,<0.42`). |
| `ModuleNotFoundError: rdkit` | RDKit not installed | `pip install rdkit`, or use `conda env create -f environment.yml`. |
| TDC load returns `TOOL_ERROR` | First-use dataset download blocked/offline | Ensure outbound HTTPS; retry. Metadata endpoints still list datasets. |
| PubMed 429 / slow | Rate limited | Set `NCBI_API_KEY` and `NCBI_EMAIL`; lower `max_results`. |
| Vina `CONFIGURED_BUT_NOT_RUN` | `VINA_BIN` unresolved | Install Vina and set `VINA_BIN`. This is expected, not an error. |
| REINVENT4 `CONFIGURED_BUT_NOT_RUN` | No runtime configured | Install REINVENT4 and set `REINVENT4_PYTHON`. Config generation still works. |
| Frontend can't reach API | Wrong base / CORS | Dev proxy targets `:8000`; for prod set `VITE_API_BASE` and add the origin to `CORS_ORIGINS`. |
| CORS blocked | Origin not allowed | Add it to `CORS_ORIGINS` in `.env` (localhost/127.0.0.1 are allowed by regex). |

## Data & reset

- SQLite DB, tool cache, and job outputs live under `backend/data/` (gitignored).
- To reset: stop the backend and delete `backend/data/`. It is recreated on
  startup (`db.init_db()`).

## Logs

- Backend logs go to stdout (uvicorn). Secrets are never logged.
- Per-call provenance and errors are persisted as `AuditEvent`s; query
  `/api/audit/events?limit=200`.

## Deployment notes

- Backend: any ASGI host (`uvicorn`/`gunicorn -k uvicorn.workers.UvicornWorker`).
- Frontend: `npm run build` → static `dist/` behind any web server (a
  multi-stage `Dockerfile` + `nginx.conf` are included).
- Scale-out: swap SQLite for Postgres in `storage/db.py`; move Vina/REINVENT jobs
  behind a task queue using the existing `job_id` + status endpoints.
