# Compute Cost Guard

Pricing is a **user-configurable snapshot**, never asserted as permanent truth. Every
estimate is labeled "verify in provider console". No paid job runs without an explicit
cost estimate, a max cost, human approval, and passing safety validation.

## Pricing (`compute/cost_guard.py`)
- Default GPU-hour snapshots (A100-40/80GB, H100, L4) are **defaults for illustration**,
  not current market prices.
- Users add their own `PricingProfile` via `POST /api/compute/pricing-profiles`; stored
  profiles are flagged `user_entered`, `verified=false`.
- Sonnet LLM pricing supports a promotional env override (see LLM cost guard), likewise
  labeled non-authoritative.

## Estimation
`estimate_gpu_job_cost(spec, profile)` = gpu_hours × price_per_gpu_hour + small storage
term. Marked `approximate: true`. CPU jobs estimate wall-time only, cost `$0`.

## Budget guard
`check_budget(estimate, job_max)` enforces:
- **per-run cap** = min(`HELIXFORGE_REMOTE_GPU_MAX_JOB_COST_USD`, spec `max_cost_usd`);
- **per-day cap** = `HELIXFORGE_REMOTE_GPU_MAX_DAILY_COST_USD` vs today's recorded actuals.
Over cap ⇒ `BUDGET_BLOCKED` (source type `GPU_BUDGET_BLOCKED`); the job is never submitted.

## Human approval
`create_job` lands in `WAITING_FOR_APPROVAL`. `POST /api/compute/jobs/{id}/approve`
(or `/approve-cost`) marks it approved; in this build session an approved job becomes
`CONFIGURED_NOT_RUN` (live submission is gated behind `HELIXFORGE_ENABLE_LIVE_GPU_TEST`).

## Reporting
`GET /api/compute/costs` returns estimated/actual totals, spent-today, caps, and
`replay_cost_usd: 0.0` (replayed compute has zero live cost). CPU vs GPU tradeoffs:
`compare_cpu_vs_gpu(...)` → `CPU_ONLY` / `REMOTE_GPU_RECOMMENDED` / `NEEDS_BENCHMARK`.
