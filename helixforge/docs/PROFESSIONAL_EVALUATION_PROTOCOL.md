# Professional Evaluation Protocol

> Research decision support only. In-silico/assay evidence is not clinical efficacy, safety, or regulatory validation. No synthesis route, dosage, or medical advice. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Modules:** `professional_release.py` (16-category scorecard), `red_team_pro.py` (24 scientific adversarial probes), plus existing `evaluation.py` studies.

**Studies covered.** retrospective rediscovery, tool-integration smoke, citation integrity, molecule validity, self-correction red-team, scenario robustness, ADMET baseline validation, docking protocol readiness, report safety lint, source-type governance.

**Rigor.** Exact counts; small samples are stated as too small for significance — statistical significance is never fabricated. Reproducibility via record/replay + run manifest.

**Status.** PARTIALLY_IMPLEMENTED — a dedicated per-study runner with bootstrap CIs is roadmapped; current coverage is the release scorecard + red-team + existing evaluation bench.
