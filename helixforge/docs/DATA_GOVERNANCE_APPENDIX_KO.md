# Data Governance Appendix

- **Sources and rights.** See the Data Card; unverified licenses are marked REVIEW_REQUIRED, and attribution is retained per record.
- **Minimization.** No patient-level or personal data; snapshots store metadata only.
- **Retention.** Records are timestamped and source-typed for auditability.
- **Redistribution.** Verify upstream terms before any public redistribution.

---

### Source-type legend

`REAL_TOOL_OUTPUT · RECORDED_REAL_TOOL_OUTPUT · CONFIGURED_BUT_NOT_RUN · TOOL_ERROR · HEURISTIC_ANALYSIS · ASSUMPTION · BASELINE_MODEL_OUTPUT · SAFETY_REDACTED · HUMAN_INPUT`

Every value the system surfaces is tagged with one of the labels above so a reviewer can never confuse a real tool result with a fallback, a heuristic, or a tool that was configured but not run.

### Human responsibility

> This system is research decision support only. It does not replace expert scientific, clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human research team.

> 본 시스템은 연구 의사결정 보조 도구이며 전문가 검토를 대체하지 않습니다. 최종 판단과 책임은 연구자에게 있습니다.

_Document provenance: HEURISTIC_ANALYSIS — a rule-based synthesis of current system state, not a tool or database result. No wet-lab, clinical, regulatory, or synthesis content is generated._
