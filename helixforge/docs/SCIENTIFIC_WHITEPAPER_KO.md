# HelixForge AI — 과학 백서 (Scientific Whitepaper)

## 1. 초록 (Abstract)
HelixForge AI는 문헌·생리활성·임상시험·케모인포매틱스 근거를 융합하여, 초기 표적/분자 선별을 위한 추적 가능하고 출처가 표시된 워크플로를 제공하는 연구 의사결정 보조 시스템입니다. 모든 값에는 출처 유형이 부여되며, 임상·규제·실험(wet-lab) 사실을 주장하지 않습니다.

## 2. 문제 정의 (Problem statement)
초기 신약 탐색은 파편화된 공개 근거로 인해 어렵고, 범용 언어모델은 과대주장(overclaim)을 하기 쉽습니다. 본 시스템은 근거를 정리하면서 각 주장의 강도와 한계를 명시하는 문제를 다룹니다.

## 3. Field 4 융합 근거 (Field 4 fusion rationale)
생의학 문헌, 생리활성 화학, 임상 근거, 기계 추론의 네 분야를 융합합니다. 이들 신호를 개별적으로 쓰기보다 상호 교차검증할 때 선별 품질이 향상되기 때문입니다.

## 4. 시스템 개요 (System overview)
FastAPI 백엔드가 실제 도구, 저장소, 거버넌스를 오케스트레이션합니다. 검색 → 등급화·검토 → 사람이 읽는 요약으로 데이터가 흐르며 모든 단계가 감사 로그로 남습니다.
관측값: 기록된 워크플로 실행 33건.

## 5. 멀티 에이전트 아키텍처 (Multi-agent architecture)
계획·검색·비평·검토 에이전트가 각각 좁고 감사 가능한 역할을 맡습니다. 비평 에이전트는 약한 주장을 능동적으로 반박하고 재등급화를 유도하며, 어떤 에이전트도 안전 린트를 우회하지 못합니다.

## 6. 실제 도구 통합 (Real tool integrations)
실시간 통합: PubMed/NCBI, ChEMBL/EMBL-EBI, ClinicalTrials.gov v2, TDC/PyTDC, RDKit. 각 결과는 REAL_TOOL_OUTPUT(재생 시 RECORDED_REAL_TOOL_OUTPUT)로 표시됩니다. AutoDock Vina (`vina`) and REINVENT4 (`(unset)`) are integrated and health-checked but **CONFIGURED_BUT_NOT_RUN**; no docking or generative run has been executed and neither is reported as a completed real result.

## 7. 근거 및 주장 등급화 (Evidence and claim grading)
모든 주장은 근거 강도에 따라 A–F로 등급화되며, 분석/전산 근거가 임상적 증명으로 표시될 수 없도록 상한이 걸립니다. 실패한 인용과 상충 근거는 등급을 강등시킵니다.
관측값: 21개 주장 등급화, 분포 {'E_UNVERIFIED': 2, 'B_MODERATE': 15, 'C_PRELIMINARY': 4}.

## 8. 표적 생물학 검토 (Target biology review)
후보 표적은 질환 연관성, 성약성 신호, 알려진 위험을 공개 데이터로 검토합니다. 확정된 사실이 아니라 전문가 검토용 가설입니다.

## 9. 분자 후보 파이프라인 (Molecule candidate pipeline)
분자 후보는 ChEMBL에서 가져와 RDKit으로 검증하며, 유효하지 않은 구조는 추천되지 않습니다.
관측값: 분자 4건 검토, RDKit 사용 가능 = True.

## 10. ChEMBL 활성 정규화 (ChEMBL assay normalization)
ChEMBL 활성값(단위, 활성 유형, pChEMBL)을 정규화하여 측정된 역가를 비교 가능하게 하고 계산된 추정값과 명확히 구분합니다.

## 11. 의약화학 검토 (Medicinal chemistry review)
의약화학 검토는 성질·구조 경보(성약성, PAINS류 필터) 우려를 표시합니다. 합성 설계나 용량 안내는 수행하지 않습니다.

## 12. 적용 가능 범위 (Applicability domain)
적용 가능 범위를 강제·표시합니다. 데이터가 풍부한 잘 연구된 표적에서 신뢰도가 가장 높고 희소·신규 표적에서는 낮아지며, 범위를 벗어난 입력은 전문가 검토 대상으로 표시됩니다.

## 13. ADMET 검증 프로토콜 (ADMET validation protocol)
ADMET 신호는 공개 데이터셋·모델에서 비롯되며 모델 출력(BASELINE_MODEL_OUTPUT / HEURISTIC_ANALYSIS)으로 표시될 뿐 안전성 판정이 아닙니다.

## 14. 도킹 거버넌스 (Docking governance)
도킹은 가정하지 않고 통제합니다. AutoDock Vina는 CONFIGURED_BUT_NOT_RUN이며, 본 배포에서 도킹 점수를 실제 결과로 제시하지 않습니다.

## 15. 다목적 최적화 (Multi-objective optimization)
후보 순위는 유효성·성약성·신규성·근거에 대한 투명한 다목적(파레토) 절충으로 정하며, 가중치는 숨기지 않고 공개합니다.

## 16. 임상 선례 검토 (Clinical precedent review)
ClinicalTrials.gov 선례는 표적/모달리티에 대한 사전 관심을 나타낼 뿐 효능의 증명이 아니며 그에 맞게 등급화됩니다.
관측된 임상 선례 상태: reviewed.

## 17. 중개연구 준비도 (Translational readiness)
중개연구 준비도는 상한이 걸린 척도(TRL_4_READY_FOR_EXPERIMENTAL_PLANNING을 초과하지 않음)로 보고되어 실험적·임상적 성공을 암시할 수 없습니다.
관측된 준비도: TRL_4_READY_FOR_EXPERIMENTAL_PLANNING.

## 18. 안전 및 윤리 통제 (Safety and ethics controls)
안전 및 윤리 통제에는 금지 범주(합성 경로, 시약, 용량, 위험 콘텐츠)를 차단하는 안전 린트, 과대주장 탐지, SAFETY_REDACTED 표시가 포함됩니다. 이 가드레일은 어떤 에이전트도 우회할 수 없습니다.

## 19. 평가 프로토콜 (Evaluation protocol)
평가는 서술적이며 오프라인에서 안전합니다: 회고적 재발견, 인용 무결성, 분자 유효성, 자기수정 횟수, 거버넌스 감사. 표본이 작아 정성적 신뢰만 뒷받침합니다.
관측된 거버넌스 상태: BLOCKED.

## 20. 기록/재생 재현성 (Record/replay reproducibility)
기록/재생 계층은 실제 도구 출력을 타임스탬프가 있는 스냅샷(해당 시 메타데이터만)으로 캡처하여 재현 가능한 오프라인 시연을 지원합니다. 재생 데이터는 RECORDED_REAL_TOOL_OUTPUT로 표시되며 실시간으로 재표시되지 않습니다.

## 21. 한계 (Limitations)
한계(Limitations). 임상 검증이나 규제 승인을 주장하지 않으며 의료기기가 아닙니다. 전산·분석 신호는 실험적 증명이 아니고 효능의 증명도 아닙니다. 작은 표본으로 통계적 유의성을 주장하지 않습니다. 범위는 상류 공개 데이터베이스에 의존합니다. 실행되지 않은 도구는 결과를 제공하지 않습니다.

## 22. 로드맵 (Roadmap)
로드맵. 표적/질환 범위 확대, 재발견 벤치마크 확장, 그리고 명시적 인간 통제와 적절한 안전 검토 하에서만 현재 실행되지 않은 도킹·생성 도구를 활성화합니다.

## 23. 부록 (Appendices)
부록. 시스템/모델/데이터 카드, 리스크 레지스터, 추적성 매트릭스, 검증 프로토콜, '우리가 주장하지 않는 것' 시트 등 거버넌스 산출물이 본 백서와 함께 제공됩니다.

## 24. 출처 유형 범례 (Source-type legend)
`REAL_TOOL_OUTPUT · RECORDED_REAL_TOOL_OUTPUT · CONFIGURED_BUT_NOT_RUN · TOOL_ERROR · HEURISTIC_ANALYSIS · ASSUMPTION · BASELINE_MODEL_OUTPUT · SAFETY_REDACTED · HUMAN_INPUT`

표시되는 모든 값에는 위 레이블 중 정확히 하나가 부여됩니다. HEURISTIC_ANALYSIS는 규칙 기반 합성을, CONFIGURED_BUT_NOT_RUN은 통합되었으나 실행되지 않은 도구를 나타냅니다.

## 25. 인간 책임 선언 (Human responsibility statement)
> This system is research decision support only. It does not replace expert scientific, clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human research team.

> 본 시스템은 연구 의사결정 보조 도구이며 전문가 검토를 대체하지 않습니다. 최종 판단과 책임은 연구자에게 있습니다.
