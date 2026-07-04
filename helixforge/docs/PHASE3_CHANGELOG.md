# Phase 3 Changelog — Submission-grade hardening

Status labels: **Implemented (real tool)** · **Implemented (recorded replay)** ·
**Implemented (heuristic)** · **Configured-not-run** · **Planned**.

## Record / Replay — Implemented (recorded replay)
Capture a real run as a sanitized snapshot; replay with no live calls, labeled
`RECORDED_REAL_TOOL_OUTPUT`; reports disclose original + replay timestamps.
Committed built-in EGFR/NSCLC snapshot. See `RECORD_REPLAY_MODE.md`.

## Evidence QA linter — Implemented
`services/evidence_linter.py`, `POST /api/evidence/lint-report`. Blocks
failed-citation-as-verified, missing source_type, invalid-molecule-recommended;
warns on unbacked hypotheses / missing timestamps. Reports gate on this before
final export. Frontend: Reports / Safety Gate surface the status.

## AI Interaction Ledger — Implemented
`services/ai_interaction_ledger.py`, `GET /api/ai-ledger*`. Records every
deterministic agent step (default runtime is LLM-free, logged honestly), redacts
secrets, never stores private chain-of-thought. Page: **AI Ledger**.

## Release Readiness — Implemented
`services/release_readiness.py`, `GET /api/release-readiness`. Tool/agent/
evidence/molecule/report/safety/demo checks → 0–100 score + status
(NOT_READY … SUBMISSION_READY) + rubric mapping. Page: **Release Readiness**.

## Submission Center — Implemented
`services/submission_pack.py`, `POST /api/submission/generate`,
`GET /api/submission/bundle`, `POST /api/submission/check`. Generates Korean
proposal, technical appendix, ethics appendix, peer-review summary (KO), demo
script, judge README, and a full JSON bundle — disclaimers embedded, not-run
tools labeled, secrets excluded. Page: **Submission Center**.

## Scientific depth
- **ChEMBL assay analysis — Implemented (real tool):** `chembl_analysis.py`,
  `GET /api/chembl/assay-summary`. Standard type/unit counts, pChEMBL
  availability, relation distribution, suspicious values, median-by-type.
- **Molecule diversity — Implemented (real tool / RDKit):**
  `molecule_diversity.py`, `POST /api/molecules/analyze-diversity`. Morgan
  fingerprints, Tanimoto, exact + near-duplicates, Bemis-Murcko scaffolds,
  diversity score. Degrades to Configured-not-run without RDKit.
- **Activity proxy:** pChEMBL → `REAL_TOOL_OUTPUT`; nM/uM/mM conversion →
  `HEURISTIC_ANALYSIS`; otherwise `ASSUMPTION` + warning.

## Scenario Matrix — Implemented (real tool)
8 disease/target presets (`data/scenarios.py`), `POST /api/scenarios/run-matrix`.
Retrieval/robustness benchmark, partial-failure tolerant, honest "no claim when
target not found". Page: **Scenario Matrix**.

## Security / privacy — Implemented
`services/security_audit.py`, `GET /api/security/audit`. Verifies `.env`
ignored, no secret leakage into audit/reports/cache, CORS/debug/large-file
warnings. `GET /api/cache/stats`, `POST /api/cache/clear`. Secret redaction is
applied to logs, audit events, reports, cache metadata, and export bundles.

## New source-type labels
`RECORDED_REAL_TOOL_OUTPUT`, `BASELINE_MODEL_OUTPUT`, `HEURISTIC_ANALYSIS`,
`ASSUMPTION`, `SAFETY_REDACTED` (in addition to the Phase 1/2 set).

## Not done / Planned (honest)
- **ADMET baseline model** — Planned. TDC remains an evaluation/training
  substrate; no fitted per-candidate predictor ships by default.
- **Regulatory local-document RAG** — Planned; checklist is heuristic
  (`HEURISTIC_ANALYSIS` / `ASSUMPTION`).
- **UniProt / PubChem / PDB adapters** — Planned (low-risk future additions).
- **Presentation Mode timer/rehearsal split** — base Presentation Mode ships;
  the rehearsal timer is a future polish item.

## Tests
`app/tests/test_phase3.py`, `test_science.py`, `test_security.py` (plus Phase 1/2
suites). Offline unit/integration tests run in CI; live_api + slow tests run
locally. Frontend `npm run build` passes; `docker compose config` valid.
