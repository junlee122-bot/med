# GPU 사용 시 기대 향상 (What GPU Would Add)

> 아래는 외부 GPU가 연결될 때의 **기대 확장**입니다. 현재 환경에서는 모두
> `GPU_CONFIGURED_NOT_RUN`(설정만, 미실행)이며, 결과를 지어내지 않습니다.

외부 GPU가 연결되면 사전 검증된 job specification을 통해 다음을 **선택적으로** 확장할 수
있습니다. 모든 유료 작업은 비용 추정 + 예산 확인 + 인간 승인 + 안전 검증을 통과해야 하며,
LLM은 임의 명령을 실행할 수 없습니다.

| GPU 작업 | CPU 대체(현재) | GPU가 추가하는 것 | 주장하지 않는 것 |
|---|---|---|---|
| Chemprop 학습 | RDKit FP + sklearn 기준 | GNN 정확도, 대용량 학습 | 효능 |
| REINVENT4 생성 | 선택 최적화 + 안전 국소 열거 | 학습 기반 de-novo 생성 | 효능 |
| GNINA/Vina-GPU | 리간드 유사도 스크리닝 | 구조 기반 도킹 신호 | 결합 증명 |
| Boltz-2/Chai-1 | 구조 메타데이터 + 리간드 신뢰도 | 공동접힘 구조·신뢰도 | 임상 효능 |
| OpenMM | 프로토콜 준비 기록 | 동역학 정밀화 | 안정성 증명 |
| ESM | 서열 식별 메타데이터 | 단백질 표현 벡터 | 생물학적 주장 |

## 안전·비용 게이트 (요약)
- 이미지·엔트리포인트는 서버 allowlist에서만 결정 — 임의 이미지/명령 불가.
- 리소스 상한(GPU·VRAM·런타임·출력·비용) 강제; 유해 목적어 차단.
- 아티팩트는 checksum·유형·크기·경로 검증; 실패 시 `GPU_ARTIFACT_UNVERIFIED`로 랭킹 제외.
- record/replay로 재현 시 실제 비용 0, 출처는 `RECORDED_GPU_OUTPUT`로 표기.

## 다음 단계
`docs/EXTERNAL_GPU_ARCHITECTURE.md`의 "Connecting a real external GPU" 절 참조. 원클릭
dry-run: `POST /api/demo/run-gpu-readiness-dry-run` (제출 0건, 승인 PENDING).
