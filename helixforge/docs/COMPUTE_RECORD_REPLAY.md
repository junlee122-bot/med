# Compute Record / Replay

Captures a run's compute state for offline replay (`services/compute_snapshot.py`).
**Replay makes no provider call and incurs no cost.**

## Snapshot contents
Compute profile, compute decisions, CPU model metadata (id/task/metrics/checksum/
validation), GPU job specs (type/status/hash), recorded GPU outputs, artifact metadata +
checksums + validation statuses, cost events, original timestamps.

## Never included
Credentials, API tokens, raw large checkpoints, trajectories, unredacted logs, arbitrary
binaries. `redact_secrets()` runs over the whole snapshot as a belt-and-suspenders pass.

## Replay labels
Recorded GPU outputs are labeled `RECORDED_GPU_OUTPUT` with the original capture
timestamp and the replay timestamp. Replay reports `provider_call_made: false`,
`cost_usd: 0.0`, and a limitation banner.

## Endpoints
`POST /api/snapshots/create-compute-from-run/{run_id}` ·
`POST /api/snapshots/{id}/replay-compute` ·
`GET /api/snapshots/{id}/compute-manifest` ·
`GET /api/snapshots/{id}/compute-cost-summary`.

The compute manifest confirms `contains_credentials: false`.
