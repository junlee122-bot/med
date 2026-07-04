# Phase 4 Changelog — Credibility Hardening

Phase 4 did not rebuild the system. It audited HelixForge AI for everything that
could weaken it in a competition review and fixed or honestly disclosed each item.
See `PHASE4_BLIND_SPOT_AUDIT.md` for the severity-ranked findings.

## Repository hygiene
- Archived the early mock SPA into `legacy-demo-spa/` with an "ARCHIVED — not the
  submission" README; rewrote the root `README.md` as a launcher pointing to `helixforge/`.
- Added `scripts/check_repo_hygiene.py` (no committed secrets/db/node_modules/venv/
  user snapshots; core files present; built-in snapshot small). Passes.

## Governance & honesty
- `source_type_governance.py` + `/api/source-types/audit`: blocks replay-as-real,
  `CONFIGURED_BUT_NOT_RUN` overclaims, heuristic-as-official, baseline-as-validated.
- `db.list_records()` now ensures the schema (fixed a fresh-DB crash).

## Health tiers
- `local` / `live` / `deep` health separation; `local` never touches the network
  (config-only for network tools), so offline demos are fast and honest.

## Safety (multilingual)
- Korean forbidden-content + overclaim patterns, KO overclaim rewriter, multilingual
  `lint_report`.
- `_scrub_safe_context()`: the system's own negated safety-policy statements are no
  longer falsely blocked, while genuine actionable content (EN+KO) still blocks.

## Korean proposal & submission
- `proposal_writer.py`: 20-section KO proposal, 1-page peer summary, 16-item judge
  Q&A defense — drawn from the latest real run, all export-safe.
- `hwpx_handoff.py`: paste-ready, export-safe blocks for the official HWPX template.
- Docs: `FULL_PROPOSAL_DRAFT_KO.md`, `PEER_REVIEW_ONE_PAGER_KO.md`,
  `JUDGE_QA_DEFENSE_KO.md`.

## Data rights
- `data_rights.py` + `DATA_RIGHTS_AND_ATTRIBUTION.md`: 8 sources, snapshot
  redistribution policy, `REVIEW_REQUIRED` where upstream terms are unverified.
  Submission bundle embeds the third-party notice.

## Scientific credibility & review tooling
- `rubric_scorecard.py`: transparent weighted self-assessment (labeled HEURISTIC).
- `scientific_plausibility.py`: Lipinski/Veber drug-likeness screen on candidates.
- `red_team.py` + `test_red_team.py`: 18 adversarial probes; 18/18 defended.

## New Run wizard & Peer Review
- `run_config.py`: 8 real target/indication presets + payload validation.
- Frontend pages: `/new-run` (wizard), `/peer-review` (consolidated reviewer view),
  `/proposal-studio` (proposal + HWPX handoff). Routes and nav wired.

## API surface added
`/api/source-types/audit`, `/api/source-types/lint-report`, `/api/proposal/*`,
`/api/data-rights*`, `/api/rubric/scorecard*`, `/api/plausibility/check`,
`/api/hwpx/handoff`, `/api/red-team/run`, `/api/run-configs*`, tiered `/api/tools/health`.

## Validation
- `pytest -m "unit or integration"` green (incl. `test_phase4.py`, `test_red_team.py`).
- `tsc --noEmit` clean; `vite build` passes.
- `check_repo_hygiene.py` passes; red-team 18/18.
