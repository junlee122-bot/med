# External GPU Architecture

HelixForge is **external-GPU-ready** without depending on a GPU. GPU work is expressed
as a validated, allowlisted job specification submitted to a provider-neutral gateway,
never as arbitrary code. Everything below is disabled by default and configured-not-run
in this environment.

> No live/paid GPU job runs without: provider enabled + cost estimate + max cost +
> human approval + passing safety validation. No fabricated GPU results.

## Layers
1. **Capability detection** (`compute/capability_detector`) → a `ComputeProfile`
   (`CPU_ONLY` … `REMOTE_GPU_ENABLED` / `RECORDED_GPU_REPLAY`).
2. **Compute-aware planner** (`services/compute_aware_planner`) → per-capability
   `ComputeDecision`: CPU substitute, validated GPU spec, or recorded replay.
3. **Job spec + validator** (`compute/job_spec`) → allowlisted job type; image and
   entrypoint come from the server allowlist only; resource ceilings enforced.
4. **Cost guard** (`compute/cost_guard`) → approximate estimate + per-run/day budget.
5. **Job manager** (`compute/job_manager`) → `create → validate → estimate → budget →
   WAITING_FOR_APPROVAL`. Never auto-submits a paid job.
6. **Provider gateway** (`compute/providers`) → `RemoteComputeProvider` interface;
   `LocalCPUProvider`, `RecordedArtifactProvider`, `GenericRESTGPUProvider` (disabled),
   `FakeRemoteGPUProvider` (tests).
7. **Artifact registry** (`compute/artifact_registry`) → checksum/type/size/path
   validation; failing artifacts become `GPU_ARTIFACT_UNVERIFIED` and cannot enter ranking.
8. **Record/replay** (`services/compute_snapshot`) → offline replay, zero cost.

## Generic REST provider contract
`POST /v1/jobs` · `GET /v1/jobs/{id}` · `POST /v1/jobs/{id}/cancel` · `GET /v1/jobs/{id}/artifacts`.
Webhooks are HMAC-SHA256 verified against `HELIXFORGE_REMOTE_GPU_WEBHOOK_SECRET`.

## Configuration (all optional; disabled by default)
```
HELIXFORGE_REMOTE_GPU_ENABLED=false
HELIXFORGE_REMOTE_GPU_PROVIDER=generic_rest
HELIXFORGE_REMOTE_GPU_ENDPOINT=
HELIXFORGE_REMOTE_GPU_API_TOKEN=          # masked in UI; never in payloads/snapshots
HELIXFORGE_REMOTE_GPU_WEBHOOK_SECRET=
HELIXFORGE_REMOTE_GPU_MAX_JOB_COST_USD=10.00
HELIXFORGE_REMOTE_GPU_MAX_DAILY_COST_USD=30.00
HELIXFORGE_REMOTE_GPU_MAX_RUNTIME_MINUTES=240
HELIXFORGE_ENABLE_LIVE_GPU_TEST=false     # gates any live provider call
```

## Connecting a real external GPU (next step)
1. Stand up a control plane implementing the generic REST contract, running only the
   allowlisted worker images.
2. Set the env vars above (endpoint, token, webhook secret) and
   `HELIXFORGE_REMOTE_GPU_ENABLED=true`.
3. Build + validate a job spec (`/api/compute/jobs/dry-run`), approve it, and only then
   enable `HELIXFORGE_ENABLE_LIVE_GPU_TEST=true` for a small smoke job.
4. Validate returned artifacts (checksums, output contract) before any candidate ranking.
