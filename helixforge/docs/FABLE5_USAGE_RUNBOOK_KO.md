# Fable 5 사용 런북 (KO)

> Research decision support only. Fable 5 is optional and never supplies scientific ground truth. No wet-lab protocol, synthesis route, dosage, or medical advice. No hidden chain-of-thought. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**API 키 없이 실행(기본값).** 별도 설정 없이 앱은 결정론적으로 동작합니다. `/api/llm/health`는 `llm_available: false`와 사유를 보고하며, 모든 추론 단계는 결정론적 폴백(`DETERMINISTIC_FALLBACK`)으로 표시됩니다.

**Sonnet 개발 모드.** `ANTHROPIC_API_KEY`, `HELIXFORGE_USE_LLM=true`, `HELIXFORGE_LLM_MODE=HYBRID_LLM_DEV` 설정. 계획/비평은 Sonnet 5, 가설은 개발 모델을 사용합니다. `POST /api/workflow/run-hybrid-agentic-pipeline`(mode: HYBRID_LLM_DEV) 호출.

**최종 Fable 스냅샷.** `HELIXFORGE_LLM_MODE=HYBRID_FABLE_FINAL` 설정. 가설·비평에 Fable 5 사용. `create_hybrid_snapshot: true`로 재생 가능한 스냅샷을 기록합니다.

**소형 라이브 스모크 테스트.** `HELIXFORGE_ENABLE_LIVE_LLM_SMOKE=true` 설정 후 `POST /api/llm/live-smoke`(또는 `/llm` 페이지 버튼). 기본 비활성.

**비용 관리.** `HELIXFORGE_LLM_MAX_COST_PER_RUN_USD`/`..._PER_DAY_USD`. `/llm`에서 비용 원장 확인, 세션별 초기화 가능.

**안전.** 키가 없거나 모델이 안전상 거절하면 항상 결정론적 폴백으로 전환되며, Fable 출력은 절대 위조하지 않습니다. 최종 판단과 책임은 연구자에게 있습니다.
