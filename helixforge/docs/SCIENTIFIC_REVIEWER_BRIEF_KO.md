# Scientific Reviewer Brief

For the scientific reviewer, in one page:

- **Scope.** Early target/molecule triage from public evidence; a decision-support aid, not a discovery engine.
- **Trust model.** Every claim is graded (A–F) by evidence strength; assay and computational signals are capped below clinical grades.
- **What to check first.** Applicability domain (is the target well-studied?), citation integrity, and any out-of-domain flags.
- **Honesty rails.** Source-type governance, safety lint, and translational readiness capped at TRL_4 (no wet-lab implied).

Observed: evidence — 21 claims graded; distribution={'E_UNVERIFIED': 2, 'B_MODERATE': 15, 'C_PRELIMINARY': 4}; readiness — TRL_4_READY_FOR_EXPERIMENTAL_PLANNING; clinical precedent — reviewed.

---

### Source-type legend

`REAL_TOOL_OUTPUT · RECORDED_REAL_TOOL_OUTPUT · CONFIGURED_BUT_NOT_RUN · TOOL_ERROR · HEURISTIC_ANALYSIS · ASSUMPTION · BASELINE_MODEL_OUTPUT · SAFETY_REDACTED · HUMAN_INPUT`

Every value the system surfaces is tagged with one of the labels above so a reviewer can never confuse a real tool result with a fallback, a heuristic, or a tool that was configured but not run.

### Human responsibility

> This system is research decision support only. It does not replace expert scientific, clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human research team.

> 본 시스템은 연구 의사결정 보조 도구이며 전문가 검토를 대체하지 않습니다. 최종 판단과 책임은 연구자에게 있습니다.

_Document provenance: HEURISTIC_ANALYSIS — a rule-based synthesis of current system state, not a tool or database result. No wet-lab, clinical, regulatory, or synthesis content is generated._
