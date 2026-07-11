# GPU Job Security Policy

An LLM (or any caller) can **never** write a free-form command, choose an image, or
inject code. GPU work is an allowlisted, validated specification only.

## Enforced controls (`compute/security.py`, `compute/job_spec.py`, `compute/schemas.py`)
1. **Image allowlist** — immutable digests per job type; no arbitrary image.
2. **Entrypoint allowlist** — fixed per job type; no user command override.
3. **Forbidden fields** — `command`, `cmd`, `entrypoint`, `image`, `script`, `run`,
   `pip_install`, `download_url`, `mount`, `privileged`, `secret`, `token`, … present
   anywhere in a spec ⇒ hard reject.
4. **Injection scan** — shell metacharacters (`; & | \` $ > <`, `$(`, `sudo`, `rm -rf`,
   `curl`, `wget`) in any string value ⇒ reject.
5. **Resource caps** — gpu_count ≤ 8, VRAM ≤ 80 GB, runtime ≤ 240 min, output ≤ 4096 MB,
   cost ≤ $50 ceiling (per-provider caps may be lower).
6. **Harmful objectives** — objective text referencing toxicity/lethality/pathogen/
   weapon/explosive/evasion ⇒ reject.
7. **Secret management** — tokens from env only; masked in the config endpoint; redacted
   from logs, snapshots, and exports; never in a job payload.
8. **Artifact security** — allowed types/media only; size cap; SHA-256 checksum; path
   traversal & absolute paths blocked; unsafe archive members rejected. Unverified
   artifacts → `GPU_ARTIFACT_UNVERIFIED`, excluded from ranking.
9. **Network policy** — no arbitrary egress; approved sources only (documented where a
   provider cannot enforce it).
10. **Human approval** — required for paid/remote jobs and jobs with uploaded data.
11. **Kill switch** — cancel a job, disable a provider, daily-budget stop.
12. **Audit** — creator, approver, provider, cost, image digest, input/output hashes,
    timestamps.

## Self-audit
`POST /api/compute/security/audit` runs redaction, path-traversal, forbidden-field, and
provider-gating checks. `GET /api/compute/security/policies` returns the enforced set.

## Tests
`test_compute_layer.py` covers: arbitrary shell rejected, unapproved job type/image,
excessive cost/runtime, harmful objective, secret redaction, path traversal, missing
approval, fake-provider malformed-artifact and checksum-mismatch, webhook signature.
