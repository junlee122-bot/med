# Real vs Replay vs Not-Run

A single, unambiguous three-way classification of where every result comes from.

| Class | Meaning | Tools / sources | Source type |
|---|---|---|---|
| REAL (live) | Executed now against the live source | PubMed, ChEMBL, ClinicalTrials.gov, RDKit, TDC | REAL_TOOL_OUTPUT |
| RECORDED replay | Replayed from a captured real snapshot (metadata only) | Snapshotted PubMed/ChEMBL/ClinicalTrials/TDC records | RECORDED_REAL_TOOL_OUTPUT |
| CONFIGURED_BUT_NOT_RUN | Integrated and health-checked, but not executed | AutoDock Vina, REINVENT4 | CONFIGURED_BUT_NOT_RUN |

RECORDED replay data is clearly distinguished from live REAL results and is never relabeled as REAL. CONFIGURED_BUT_NOT_RUN tools are never described as having produced results.

AutoDock Vina (`vina_bin=vina`) and REINVENT4 (`reinvent4_bin=(unset)`) are **CONFIGURED_BUT_NOT_RUN** in this deployment: their adapters and honest health checks exist, but no docking or generative run has been executed. They are never reported as completed real results.

---

### Source-type legend

`REAL_TOOL_OUTPUT · RECORDED_REAL_TOOL_OUTPUT · CONFIGURED_BUT_NOT_RUN · TOOL_ERROR · HEURISTIC_ANALYSIS · ASSUMPTION · BASELINE_MODEL_OUTPUT · SAFETY_REDACTED · HUMAN_INPUT`

Every value the system surfaces is tagged with one of the labels above so a reviewer can never confuse a real tool result with a fallback, a heuristic, or a tool that was configured but not run.

### Human responsibility

> This system is research decision support only. It does not replace expert scientific, clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human research team.

> 본 시스템은 연구 의사결정 보조 도구이며 전문가 검토를 대체하지 않습니다. 최종 판단과 책임은 연구자에게 있습니다.

_Document provenance: HEURISTIC_ANALYSIS — a rule-based synthesis of current system state, not a tool or database result. No wet-lab, clinical, regulatory, or synthesis content is generated._
