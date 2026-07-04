# Phase 4 — Blind-Spot Audit

A self-critical review of everything that could weaken HelixForge AI in a competition
review, with the fix (or the honest limitation) for each. Severity labels:
**BLOCKER** (submission credibility at risk), **HIGH**, **MEDIUM**, **LOW**,
**INTENTIONAL_LIMITATION** (a scoped decision we stand behind and disclose).

> This system is research decision support only. It does not replace expert
> scientific, clinical, regulatory, legal, or ethical review. Final responsibility
> belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

## Findings & resolutions

| # | Severity | Blind spot | Resolution | Status |
|---|---|---|---|---|
| 1 | BLOCKER | An early mock SPA at the repo root could be mistaken for the submission, and the root README didn't point to the real app. | `git mv` the mock into `legacy-demo-spa/` with an "ARCHIVED — not the submission" README; rewrote the root README as a launcher pointing to `helixforge/`. Added `scripts/check_repo_hygiene.py` (passes). | FIXED |
| 2 | BLOCKER | Source types could be mislabeled (e.g. a replay run tagged `REAL_TOOL_OUTPUT`, or `CONFIGURED_BUT_NOT_RUN` described as a real result) and nothing caught it. | `source_type_governance.py` audits all scientific tables and blocks replay-as-real, not-run overclaims, heuristic-as-official, baseline-as-validated. Endpoint `/api/source-types/audit`. | FIXED |
| 3 | HIGH | The Tool Registry "health check" probed the network even in local/offline mode — slow and misleading during an offline demo. | Split health into `local` / `live` / `deep` tiers; `local` never touches the network (config-only for network tools). Verified ~0.01s, `network_used=false`. | FIXED |
| 4 | HIGH | Safety/overclaim linting was English-only; the Korean submission could carry forbidden content or overclaims unchecked. | Added Korean forbidden + overclaim patterns, a KO overclaim rewriter, and a multilingual `lint_report`. | FIXED |
| 5 | HIGH | The safety lint blocked the system's **own** negated safety-policy statements (e.g. "무합성경로 정책", "no synthesis routes … by policy"), so every honest safety section failed export. | Added `_scrub_safe_context()` that neutralizes negated/policy contexts before forbidden matching; genuine actionable content (EN+KO) still blocks. Covered by red-team `rt-10`/`rt-11` and unit tests. | FIXED |
| 6 | HIGH | `db.list_records()` didn't ensure the schema, so governance crashed on a fresh DB with "no such table: tool_runs". | `list_records()` now calls `_ensure_schema()` like insert/get/count. | FIXED |
| 7 | HIGH | No full Korean proposal — judges would see fragments, not a submission-shaped document. | `proposal_writer.py` builds a 20-section KO proposal, a 1-page peer summary, and a 16-item judge Q&A defense from the latest real run; all export-safe. | FIXED |
| 8 | HIGH | Third-party data rights were undocumented — a redistribution/attribution risk for PubMed/ChEMBL/ClinicalTrials/TDC. | `data_rights.py` + `DATA_RIGHTS_AND_ATTRIBUTION.md`: 8 sources, snapshot redistribution policy, `REVIEW_REQUIRED` where upstream terms are unverified. Bundle embeds the notice. | FIXED |
| 9 | MEDIUM | No adversarial self-test of the safety/honesty gates — reviewers couldn't see the defenses actually hold. | `red_team.py`: 18 probes (synthesis/dosage/toxicity/weapon block, overclaim rewrite, provenance & governance catches, own-policy false-positive guard). 18/18 defended, exposed at `/api/red-team/run`. | FIXED |
| 10 | MEDIUM | Molecule candidates weren't sanity-checked — an absurd descriptor could pass silently. | `scientific_plausibility.py`: Lipinski/Veber screen; flags `IMPLAUSIBLE`/`OUTSIDE_DRUGLIKE` without claiming activity. | FIXED |
| 11 | MEDIUM | No transparent rubric self-assessment; the rubric mapping wasn't scored or honest about gaps. | `rubric_scorecard.py`: 7 weighted criteria (sum 100), evidence pointers, honest gaps, ceilings where wet-lab validation is absent. Clearly labeled `HEURISTIC_ANALYSIS`, not an official score. | FIXED |
| 12 | MEDIUM | Launching a run required knowing the API shape; a judge couldn't start a meaningful run easily. | New Run wizard: 8 real target/indication presets + payload validation (`run_config.py`), and a one-click `/new-run` page. | FIXED |
| 13 | MEDIUM | The official submission is HWP/HWPX; copying from markdown risks formatting/paste errors. | `hwpx_handoff.py`: paste-ready, export-safe plain-text blocks per template section (no binary file emitted — a human finalizes formatting). | FIXED |
| 14 | LOW | Large single JS bundle (~1.1 MB) triggers a Vite chunk-size warning. | Acknowledged; app is an internal decision-support tool, not a public high-traffic site. Code-splitting is a possible future optimization. | INTENTIONAL_LIMITATION |
| 15 | INTENTIONAL_LIMITATION | AutoDock Vina and REINVENT4 are `CONFIGURED_BUT_NOT_RUN` unless installed. | This is disclosed everywhere rather than faked. Docking uses a fixture; generation ships a real config. Field 2 is evidenced via ChEMBL real structures + RDKit validation. | DISCLOSED |
| 16 | INTENTIONAL_LIMITATION | Regulatory analysis (Field 3) is heuristic + document-assist, not certified compliance. | Disclosed in the proposal, Q&A sheet, and limitations doc; RAG over regulatory corpora is roadmapped. No compliance is claimed. | DISCLOSED |
| 17 | INTENTIONAL_LIMITATION | All results are in-silico; no wet-lab, clinical, or regulatory validation. | Stated in every artifact, capped in the scorecard, and enforced by the overclaim linters. | DISCLOSED |

## Verification

- Backend: `pytest -m "unit or integration"` green, including `test_phase4.py` and `test_red_team.py`.
- Frontend: `tsc --noEmit` clean; `vite build` passes.
- Repo hygiene: `python scripts/check_repo_hygiene.py` passes (0 problems).
- Red-team: 18/18 scenarios defended.
