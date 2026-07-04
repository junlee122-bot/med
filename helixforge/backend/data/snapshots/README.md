# Run Snapshots (record / replay)

This directory stores **recorded real runs** as sanitized JSON files.

- `builtin-*.json` — small, sanitized, committed built-in snapshots (e.g. a
  limited EGFR/NSCLC run). Safe to commit: secrets redacted, dataset **metadata
  only** (not full rows), small `max_results`.
- `snap-*.json` — user-created snapshots (gitignored; may be large).

## Provenance

Replaying a snapshot recreates the run's artifacts labeled
`RECORDED_REAL_TOOL_OUTPUT` — the data was really retrieved from live tools at
capture time; **no live API call happens during replay**. Reports generated from
a replay disclose both the original retrieval timestamp and the replay timestamp.

## Regenerate the built-in snapshot locally

```bash
cd helixforge/backend && source .venv/bin/activate
python -m app.scripts.make_builtin_snapshot   # writes builtin-egfr-nsclc.json
```

See `docs/RECORD_REPLAY_MODE.md`.
