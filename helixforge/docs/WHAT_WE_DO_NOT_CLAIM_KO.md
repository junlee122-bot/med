# What We Do NOT Claim

To keep the system honest, we state explicitly what HelixForge AI does not do. We do not claim any of the following:

- We do not claim any **wet-lab** validation of any target or molecule.
- We do not claim clinical efficacy, safety, or therapeutic benefit.
- We do not claim regulatory approval or regulatory compliance of any kind.
- We do not claim binding proof or any experimentally confirmed interaction.
- We do not provide dosing, medical advice, or treatment recommendations.
- We do not provide synthesis routes or reagent/reaction procedures.
- We do not claim statistical significance from our small evaluation samples.

Each of the phrases above appears here only as something we explicitly do **not** claim. Outputs are hypotheses and organized public evidence for expert review — nothing more.

---

### Source-type legend

`REAL_TOOL_OUTPUT · RECORDED_REAL_TOOL_OUTPUT · CONFIGURED_BUT_NOT_RUN · TOOL_ERROR · HEURISTIC_ANALYSIS · ASSUMPTION · BASELINE_MODEL_OUTPUT · SAFETY_REDACTED · HUMAN_INPUT`

Every value the system surfaces is tagged with one of the labels above so a reviewer can never confuse a real tool result with a fallback, a heuristic, or a tool that was configured but not run.

### Human responsibility

> This system is research decision support only. It does not replace expert scientific, clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human research team.

> 본 시스템은 연구 의사결정 보조 도구이며 전문가 검토를 대체하지 않습니다. 최종 판단과 책임은 연구자에게 있습니다.

_Document provenance: HEURISTIC_ANALYSIS — a rule-based synthesis of current system state, not a tool or database result. No wet-lab, clinical, regulatory, or synthesis content is generated._

## Phase 7 — Fable 5 하이브리드 레이어에 대해 주장하지 않는 것

- Fable 5(또는 어떤 LLM)가 과학적 사실을 생성한다고 주장하지 않습니다. 과학적 사실은 오직 PubMed·ChEMBL·ClinicalTrials.gov·RDKit·TDC에서 나옵니다.
- "17개 에이전트가 완전 자율적"이라고 주장하지 않습니다. Fable 5는 동적 계획, 근거 기반 가설 추론, 의미 비평에만 사용됩니다.
- 시스템이 신약을 발견했다거나 효능을 검증했다고 주장하지 않습니다.
- 회고적 재발견이 de novo 발견을 증명한다고 주장하지 않습니다 — 알려진 약물/케모타입 신호의 회복 여부를 평가할 뿐입니다.
- 분자 최적화 루프가 합성·실험 검증이라고 주장하지 않습니다 — in-silico 후보 우선순위화입니다. 합성 경로·반응 조건·투여량을 생성하지 않습니다.
- LLM 출력이 검증 없이 사용된다고 주장하지 않습니다 — 인용 검증·근거 등급·안전 린트·거버넌스 게이트를 모두 거칩니다.
- 숨겨진 사고 과정(chain-of-thought)을 노출하거나 저장하지 않습니다.
- API 키 없이도 전체 기능이 결정론적으로 동작하며, 키가 없으면 그렇게 표시합니다.
