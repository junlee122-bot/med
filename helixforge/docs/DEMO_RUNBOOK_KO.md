# 데모 실행 런북 (한국어)

## 0. 사전 준비
- Python 3.11, Node 22.12 이상. (RDKit·PyTDC는 무거우므로 conda 사용 권장: `conda env create -f backend/environment.yml`)
- 인터넷 연결(PubMed/ChEMBL/ClinicalTrials/TDC 다운로드에 필요). API 키는 선택 사항입니다.

## 1. 백엔드 실행
```bash
cd helixforge/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
- 상태 확인: <http://localhost:8000/api/health>
- API 문서(Swagger): <http://localhost:8000/docs>

## 2. 프런트엔드 실행
```bash
cd helixforge/frontend
npm install
npm run dev          # http://localhost:5174 (/api는 8000으로 프록시)
```

## 3. 5분 라이브 데모 순서
1. **Overview** — 시스템 소개, 도구 상태 요약.
2. **Tool Registry** — 실시간 도구 상태 확인(연결 여부는 백엔드가 확인한 것만 표시).
3. **Agent Cockpit** — 6종 오류 주입을 켠 뒤 **Run agentic pipeline** 실행. 에이전트 실행 카드, 수정(revision) 타임라인, 지표를 시연.
4. **Demo Lab** — `Overclaim correction` 등 개별 자기수정 시나리오 실행 → Before/After 확인.
5. **Targets** — 실제 ChEMBL 타깃 순위와 점수 분해.
6. **Molecule Lab** — SMILES 검증, ChEMBL 구조 로드.
7. **Evaluation Bench** — 회고적 재발견 5/5 및 6개 지표 모듈.
8. **Safety Gate** — 차단/격리 항목, 무합성경로 정책.
9. **Reports** — 한국어 심사 리포트 생성 및 Markdown/JSON 내보내기.
10. **Presentation Mode** — 전체 화면 발표(슬라이드 내 라이브 버튼 포함).

## 4. CLI로 파이프라인 실행(선택)
```bash
curl -X POST http://localhost:8000/api/workflow/run-agentic-pipeline \
  -H 'Content-Type: application/json' \
  -d '{"condition":"non-small cell lung cancer","target_query":"EGFR","max_results":6,
       "error_injections":{"invalid_smiles":true,"fake_citation":true,"overclaim":true}}'
```

## 5. 테스트
```bash
cd helixforge/backend && source .venv/bin/activate
pytest app/tests/test_scoring.py -q        # 오프라인 단위 테스트
pytest app/tests -q                        # 전체(실 API·RDKit 필요)
```

## 6. 문제 해결
- 라우트가 누락되면 `requirements.txt`의 fastapi/starlette 핀을 사용하세요(신규 starlette 1.x는 라우터 등록을 깨뜨립니다).
- TDC 로드가 `TOOL_ERROR`면 네트워크를 확인하고 재시도(데이터셋 목록 조회는 계속 동작).
- Vina/REINVENT4가 `CONFIGURED_BUT_NOT_RUN`인 것은 정상입니다(설정 시 실제 실행). Settings에서 경로 지정.
- 데이터 초기화: 백엔드 중지 후 `backend/data/` 삭제(재시작 시 재생성).
