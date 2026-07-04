# 심사 기준 정합성 (Rubric Alignment)

앱 내 **Rubric Alignment**(`/#/rubric`) 페이지와 동일한 내용입니다. 준비도 배지: **Strong(강점) / Partial(부분) / Needs work(보완 필요)**.

## 예선 평가 대응

| 기준 | 준비도 | 근거 |
|---|---|---|
| 필요성과 배경 | Strong | NSCLC/EGFR 문제 정의, 초기 탐색 단계 분절 문제를 Overview·리포트에 문서화 |
| 에이전트 설계 독창성·창의성 | Strong | 17개 에이전트 DAG, Critic 루프, 6종 오류 주입 자기수정 시연, 관찰 가능 추적 |
| 기술적 실현 가능성 | Strong | 실제 PubMed/ChEMBL/ClinicalTrials/RDKit/TDC 연동, Vina/REINVENT4 어댑터, Docker 구성 |
| 에이전트 평가 적절성 | Strong | 평가 벤치(회고적 재발견, 분자 유효성, 인용 검증, 자기수정 지표) |
| 비즈니스·사회적 가치 | Partial | Impact 페이지의 시간/비용 절감 모델(보수적 범위, 현장 검증 전) |
| 연구 윤리·완성도 | Strong | 출처 표기, 감사 로그, 안전 게이트, 무합성경로 정책, 인간 책임 명시 |

## 본선 평가 대응

| 기준 | 준비도 | 근거 |
|---|---|---|
| 과학적 타당성·혁신성 | Strong | 근거 기반 가설, ChEMBL 유래 RDKit 검증 후보, 투명 점수, 불확실성 표현 |
| 에이전트 자율성·지능 | Strong | 자율 단계 분해, Critic 기반 수정, 오류 주입 자기수정(데모 자기수정률 1.0) |
| 도구 활용·통합 능력 | Strong | 실시간 도구 상태 매트릭스 + 호출별 ToolRun/감사, 정직한 SourceType |
| 리소스 활용 효율성 | Partial | 로컬 결정론적 도구 + 공개 API, 리소스 지표 추적, LLM 토큰 비용 없음. 라우터 증류 계획 |
| 시연·완성도 | Strong | Agent Cockpit, Demo Lab, Presentation Mode, 한국어 심사 리포트, JSON 내보내기 |

## 정직성 원칙
Partial 항목(사업 가치 검증, 리소스 라우터 증류)은 로드맵으로 명시하며 과장하지 않습니다. 이 정직성 자체가 연구 윤리·완성도 항목의 근거입니다.
