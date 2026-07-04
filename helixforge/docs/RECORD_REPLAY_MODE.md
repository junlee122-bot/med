# Record / Replay Mode

**Status: Implemented.** The demo-day safety net for flaky networks.

## Why
Live APIs (PubMed/ChEMBL/ClinicalTrials.gov) can fail or be slow during a
competition demo. Record/replay lets you prove the system uses **real** data
while staying demo-safe — without ever faking results.

## How it works
1. Run a real agentic pipeline (Agent Cockpit or `POST /api/workflow/run-agentic-pipeline`).
2. Capture it: `POST /api/snapshots/create-from-run/{run_id}` (Snapshots page →
   "Run pipeline + capture snapshot"). The snapshot is sanitized (secrets
   redacted), checksummed, and written to `backend/data/snapshots/`.
3. Replay it: `POST /api/snapshots/{id}/replay` (or Cockpit → "Recorded replay").
   **No live external call is made.**

## Honesty guarantees
- Replayed artifacts are labeled `RECORDED_REAL_TOOL_OUTPUT` — the data was
  really retrieved at capture time; only the retrieval is replayed.
- On replay, any `REAL_TOOL_OUTPUT` source type is flipped to
  `RECORDED_REAL_TOOL_OUTPUT` (verified by test: real must not survive as-is).
- Replayed reports **disclose replay mode** and show both the original retrieval
  timestamp and the replay timestamp.
- `test_replay_does_not_call_live_api` asserts no live call happens during replay.

## Built-in snapshot
A small (~130KB), sanitized `builtin-egfr-nsclc.json` is committed so the app can
replay offline out of the box (dataset **metadata only**, `max_results=3`). It is
auto-registered on first `GET /api/snapshots`. Regenerate locally:

```bash
cd helixforge/backend && source .venv/bin/activate
python -m app.scripts.make_builtin_snapshot
```

## Endpoints
`POST /api/snapshots/create-from-run/{run_id}` · `GET /api/snapshots` ·
`GET /api/snapshots/{id}` · `POST /api/snapshots/{id}/replay` ·
`DELETE /api/snapshots/{id}` · `GET /api/snapshots/{id}/manifest` ·
`GET /api/snapshots/{id}/export`.
