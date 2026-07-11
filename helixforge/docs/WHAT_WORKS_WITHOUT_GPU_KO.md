# GPU 없이 작동하는 기능 (What Works Without GPU)

> 연구 의사결정 보조 도구입니다. in-silico 단계이며 임상·규제 검증이 아닙니다. GPU가 없어도
> 완전한 과학 모드로 동작하며, GPU 부재는 오류가 아닙니다.

HelixForge는 GPU·LLM 키·외부 GPU 공급자 없이도 다음을 수행합니다.

| 기능 | 모듈 | 출처 유형 | 정직한 한계 |
|---|---|---|---|
| 연산 능력 탐지 | `compute/capability_detector` | — | 로컬 모드는 네트워크 미접근 |
| 데이터셋 큐레이션·품질/누수 검사 | `dataset_curation` | REAL/HUMAN | 소규모 데모 스케일 |
| CPU QSAR 기준 모델 | `cpu_qsar` | `BASELINE_CPU_MODEL_OUTPUT` | 임상 검증 모델 아님; sklearn 선택적 |
| 리간드 기반 스크리닝 | `ligand_screening` | `HEURISTIC_ANALYSIS` | 우선순위 신호일 뿐, 결합 증명 아님 |
| 적용 도메인·불확실성 | `applicability_domain` | REAL | Morgan/Tanimoto 기반 |
| Active-learning 시뮬레이션 | `active_learning` | `BASELINE_CPU_MODEL_OUTPUT` | oracle는 보류 데이터(실험 아님) |
| 다목적/파레토 | `pareto` + `cpu_multiobjective` | `COMPUTE_FALLBACK_OUTPUT` | 단일 "최고 분자" 과장 없음 |
| 최적화 루프(선택/국소 열거) | `optimization_loop` | `LOCAL_HEURISTIC_GENERATED` | 합성 경로 없음 |

## 핵심 원칙
- CPU 예측은 **임상 검증이 아니며** "production-grade"로 부르지 않습니다.
- 리간드 유사도는 **결합 증명이 아니라** 스크리닝 신호입니다.
- 의존성/데이터가 없으면 수치를 지어내지 않고 `CONFIGURED_BUT_NOT_RUN`으로 표기합니다.
- 원클릭 데모: `POST /api/demo/run-cpu-scientific-demo` (또는 Compute Center 버튼).

## 허용 문구
"GPU가 없는 환경에서도 RDKit, TDC, CPU 기반 QSAR, ligand-based screening, active-learning
simulation, multi-objective optimization을 수행한다."

## 금지 문구
"GPU를 연결하면 실제 신약을 발견한다." / "GPU 모델이 결합력과 효능을 증명한다." /
"CPU baseline이 임상 안전성을 예측한다."
