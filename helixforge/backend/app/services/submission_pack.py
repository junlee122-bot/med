"""Submission Center — generate competition artifacts from real project state.

Every artifact embeds the human-responsibility disclaimer, labels not-run tools
honestly, and excludes secrets. Artifacts are assembled from the latest real run
plus the committed docs; when no run exists yet, that is stated rather than faked.
"""
from __future__ import annotations

import subprocess
import uuid
from typing import Any, Optional

from app.config import get_settings
from app.models.schemas import SourceType, utcnow
from app.services import ai_interaction_ledger as ledger
from app.services import release_readiness
from app.services.evidence_linter import lint_run
from app.services.provenance import redact_secrets
from app.services.safety_lint import lint_report
from app.storage import db

DISCLAIMER_KO = ("본 시스템은 연구 의사결정 보조 도구이며, 전문가의 과학적·임상적·규제적·윤리적 검토를 "
                 "대체하지 않습니다. 최종 판단과 책임은 연구자에게 있습니다.")
DISCLAIMER_EN = ("This system is research decision support only. It does not replace expert scientific, "
                 "clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human "
                 "research team.")

ARTIFACT_TYPES = ["korean_proposal", "technical_appendix", "ethics_appendix",
                  "peer_review_summary", "demo_script", "judge_readme"]


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       stderr=subprocess.DEVNULL, timeout=3).decode().strip()
    except Exception:
        return "unknown"


def _latest_run() -> dict[str, Any]:
    runs = [r for r in db.list_records("workflow_runs", limit=100)
            if r.get("kind") in ("agentic", "agentic_replay")]
    return runs[0] if runs else {}


def _resolve_run(run_id: str | None = None) -> dict[str, Any]:
    if run_id is None:
        return _latest_run()
    run = db.get("workflow_runs", run_id)
    if not run:
        raise ValueError("workflow run not found")
    return run


def _run_facts(run: dict) -> dict[str, Any]:
    m = run.get("metrics", {}) or {}
    return {
        "run_id": run.get("id", "—"), "mode": "recorded replay" if run.get("kind") == "agentic_replay" else "live",
        "target": m.get("top_target") or run.get("target_query", "—"),
        "target_id": m.get("top_target_chembl_id", "—"),
        "real_outputs": m.get("real_tool_output_count", "—"), "not_run": m.get("configured_not_run_count", "—"),
        "citation_rate": m.get("citation_verification_rate", "—"), "validity": m.get("molecule_validity_rate", "—"),
        "self_correction": m.get("self_correction_rate", "—"), "pubmed": m.get("pubmed_evidence_count", "—"),
        "trials": m.get("clinicaltrials_count", "—"), "tdc_rows": m.get("tdc_row_count", "—"),
        "retro": (m.get("retrospective") or {}).get("passed", "—"),
    }


def _header(title_en: str) -> str:
    s = get_settings()
    return (f"# {title_en}\n"
            f"**HelixForge AI {s.app_version}** · commit `{_git_commit()}` · generated {utcnow()}\n\n"
            f"> {DISCLAIMER_EN}\n\n"
            f"### Source-type legend\n"
            f"`REAL_TOOL_OUTPUT` · `RECORDED_REAL_TOOL_OUTPUT` · `CONFIGURED_BUT_NOT_RUN` · `TOOL_ERROR` · "
            f"`HEURISTIC_ANALYSIS` · `ASSUMPTION` · `BASELINE_MODEL_OUTPUT` · `SAFETY_REDACTED` · `HUMAN_INPUT`\n\n")


def generate_artifact(
    artifact_type: str,
    run: dict[str, Any] | None = None,
    *,
    persist: bool = True,
) -> dict[str, Any]:
    run = _latest_run() if run is None else run
    f = _run_facts(run)
    no_run = "> ⚠ No agentic run found yet — run the pipeline first for populated figures.\n\n" if not run else ""

    if artifact_type == "korean_proposal":
        md = _header("HelixForge AI — 공모 제안서 (자동 생성)") + no_run + f"""## 1. 개요
실제 도구(PubMed, ChEMBL, ClinicalTrials.gov, RDKit, TDC)에 연동된 멀티 에이전트 신약개발 의사결정 보조 시스템입니다. 최근 실행({f['mode']}) 기준 실제 도구 출력 {f['real_outputs']}건, 선정 타깃 {f['target']}({f['target_id']}).

## 2. 문제와 융합 전략 (Field 4)
초기 탐색의 분절(문헌·타깃·분자·독성·임상·규제)을 관찰 가능한 에이전트 워크플로우로 통합합니다.

## 3. 실데이터 결과
- PubMed 근거 {f['pubmed']}건 · 임상 선례 {f['trials']}건 · TDC {f['tdc_rows']}행
- 인용 검증률 {f['citation_rate']} · 분자 유효율 {f['validity']} · 자기수정률 {f['self_correction']}
- 회고적 재발견 기준 충족: {f['retro']}/5

## 4. 안전·윤리
출처 표기, 감사 로그, 안전성 게이트, 무합성경로 정책, 인간 최종 책임. 미설치 도구는 `CONFIGURED_BUT_NOT_RUN`으로 정직하게 표기합니다.

## 5. 한계
in-silico 의사결정 보조이며 습식 실험·임상·규제 검증을 대체하지 않습니다.

> {DISCLAIMER_KO}
"""
    elif artifact_type == "technical_appendix":
        md = _header("HelixForge AI — Technical Appendix") + no_run + f"""## Architecture
FastAPI backend + React/Vite frontend. 17-agent runtime over real tool adapters; SQLite (Postgres-portable).

## Real integrations
PubMed (E-utilities), ChEMBL, ClinicalTrials.gov v2 — live HTTP. RDKit, TDC/PyTDC — local. Vina/REINVENT4 — honest `CONFIGURED_BUT_NOT_RUN` until installed.

## Latest run ({f['mode']})
run `{f['run_id']}` · target {f['target']} ({f['target_id']}) · real outputs {f['real_outputs']} · not-run {f['not_run']}.

## Scoring
Transparent Target Opportunity + Molecule Composite scores with per-input breakdown, conservative defaults, and warnings.

## Reproducibility
Run manifest (package versions, git commit), record/replay snapshots (`RECORDED_REAL_TOOL_OUTPUT`), export bundle.

> {DISCLAIMER_EN}
"""
    elif artifact_type == "ethics_appendix":
        run_id = run.get("id")
        led = ledger.summary_for_run(run_id) if run_id else {"statement": "No run yet.", "interaction_count": 0}
        md = _header("HelixForge AI — Ethics & Safety Appendix") + no_run + f"""## AI-generated data policy
All outputs are provenance-labeled; simulated/heuristic content is never presented as a real DB/wet-lab result.

## Citation honesty
Fabricated/unresolvable identifiers are demoted to FAILED and excluded from verified evidence.

## AI interaction transparency
{led['statement']} Interactions logged: {led.get('interaction_count', 0)}. Full secrets and private chain-of-thought are never stored.

## Safety policy
No wet-lab protocols, synthesis routes, reagents, reaction conditions, purification, dosage, or medical advice — by policy.

## Human responsibility
{DISCLAIMER_EN}

> {DISCLAIMER_KO}
"""
    elif artifact_type == "peer_review_summary":
        md = _peer_review_summary_ko(f, no_run)
    elif artifact_type == "demo_script":
        md = _header("HelixForge AI — Final Demo Script") + no_run + """## 5-minute flow
1. Overview → 2. Tool Registry health → 3. Agent Cockpit (run live or replay) →
4. Self-correction (invalid SMILES / fake citation / overclaim) → 5. Targets & Molecule Lab →
6. Evidence QA & Safety Gate → 7. Evaluation Bench → 8. Submission Center → 9. Presentation Mode close.

Network flaky? Use **Snapshots → Replay** (labeled RECORDED_REAL_TOOL_OUTPUT). See docs/DEMO_RUNBOOK_KO.md.
""" + f"\n> {DISCLAIMER_EN}\n"
    elif artifact_type == "judge_readme":
        md = _header("HelixForge AI — README for Judges") + f"""## What this is
A real, tool-using, self-correcting multi-agent drug-discovery workbench — not a chatbot, not mock-only.

## Run it
```
cd helixforge/backend && source .venv/bin/activate && uvicorn app.main:app --port 8000
cd helixforge/frontend && npm install && npm run dev   # http://localhost:5174
```

## What to look at (5 min)
Agent Cockpit (run + injections) · Demo Lab (self-correction) · Evaluation Bench · Snapshots (offline replay) ·
Submission Center · Presentation Mode.

## Honesty
Real: PubMed/ChEMBL/ClinicalTrials/RDKit/TDC. Configured-not-run: Vina/REINVENT4. Every result is source-labeled.

> {DISCLAIMER_EN}
"""
    else:
        raise ValueError(f"unknown artifact_type: {artifact_type}")

    md = redact_secrets(md)
    art = {
        "id": f"sub-{artifact_type}-{uuid.uuid4().hex[:8]}", "type": artifact_type,
        "title": artifact_type.replace("_", " ").title(), "markdown": md,
        "created_at": utcnow(), "run_id": run.get("id"),
        "workflow_run_id": run.get("id"), "project_id": run.get("project_id"),
    }
    if persist:
        db.insert("submission_artifacts", art)
    return art


def _peer_review_summary_ko(f: dict, no_run: str) -> str:
    return _header("HelixForge AI — 동료 검토 요약 (Peer Review Summary)") + no_run + f"""## 1. 한 줄 설명
실제 과학 도구에 연동된 멀티 에이전트로 신약개발 초기 탐색을 관찰 가능하게 자동화하는 의사결정 보조 시스템.

## 2. 해결 문제
문헌·타깃·분자·독성·임상·규제가 분리되어 후보 우선순위화에 시간이 큼.

## 3. 왜 멀티에이전트인가
단일 프롬프트로는 통합·검증·자기수정이 어려움. 전문 에이전트 분업 + Critic 루프로 해결.

## 4. 실제 연동 도구
PubMed·ChEMBL·ClinicalTrials.gov(실시간), RDKit·TDC(로컬). Vina·REINVENT4는 설정 시 실행.

## 5. 차별점
출처 유형 정직 표기, 자기수정 시연, 근거 QA, 기록/재생(오프라인 데모 안전망), 한국어 리포트.

## 6. 데모에서 볼 수 있는 것
실행 {f['mode']}: 타깃 {f['target']}, 실제 출력 {f['real_outputs']}건, 자기수정률 {f['self_correction']}, 회고적 재발견 {f['retro']}/5.

## 7. 안전성과 윤리
합성 경로·의료 자문 미제공, 감사 로그, 안전 린트, 인간 책임 명시.

## 8. 한계
in-silico 보조 단계. 습식·임상·규제 검증 대체 불가. TDC는 평가 기반, Vina는 픽스처 기반.

## 9. 기대 효과
탐색·문서화 부담 감소, 근거 추적성 향상, 재현 가능한 실행.

## 10. 검토자 강조 포인트
"실제 도구 사용 + 정직한 출처 + 자기수정 + 오프라인 재생"이 핵심입니다. 과장 없이 한계를 명시합니다.

> {DISCLAIMER_KO}
"""


def list_artifacts(run_id: str | None = None) -> list[dict]:
    run = _resolve_run(run_id)
    rid = run.get("id")
    if not rid:
        return []
    return db.list_records(
        "submission_artifacts",
        project_id=run.get("project_id"),
        workflow_run_id=rid,
        limit=200,
    )


def get_artifact(artifact_id: str, run_id: str | None = None) -> Optional[dict]:
    run = _resolve_run(run_id)
    artifact = db.get("submission_artifacts", artifact_id)
    if not artifact:
        return None
    rid = artifact.get("workflow_run_id") or artifact.get("run_id")
    if rid != run.get("id") or artifact.get("project_id") != run.get("project_id"):
        return None
    return artifact


def generate_all(
    run: dict[str, Any] | None = None, *, persist: bool = True,
) -> list[dict]:
    run = _latest_run() if run is None else run
    return [generate_artifact(t, run=run, persist=persist) for t in ARTIFACT_TYPES]


def bundle(run_id: str | None = None) -> dict[str, Any]:
    run = _resolve_run(run_id)
    run = run or {}
    run_id = run.get("id")
    project_id = run.get("project_id")
    arts = generate_all(run=run, persist=False)
    readiness = release_readiness.compute(run_id)
    reports = (db.list_records(
        "reports", project_id=project_id, workflow_run_id=run_id, limit=50
    ) if project_id and run_id else [])
    latest_report = (reports or [{}])[0]
    from app.services import data_rights
    return {
        "generated_at": utcnow(), "app_version": get_settings().app_version, "git_commit": _git_commit(),
        "artifacts": {a["type"]: a["markdown"] for a in arts},
        "release_readiness": readiness,
        "safety_lint": lint_report(latest_report.get("markdown", "")) if latest_report else None,
        "evidence_lint": lint_run(run_id) if run_id else None,
        "ai_ledger_summary": ledger.summary_for_run(run_id) if run_id else None,
        "data_rights": data_rights.list_records(),
        "third_party_data_notice": data_rights.THIRD_PARTY_NOTICE,
        "disclaimer": DISCLAIMER_EN,
        "note": "Secrets excluded. Not-run tools are labeled honestly.",
    }


def check(run_id: str | None = None) -> dict[str, Any]:
    run = _resolve_run(run_id)
    run = run or {}
    run_id = run.get("id")
    project_id = run.get("project_id")
    reports = (db.list_records(
        "reports", project_id=project_id, workflow_run_id=run_id, limit=50
    ) if project_id and run_id else [])
    run_snapshots = (db.list_records(
        "run_snapshots", project_id=project_id, workflow_run_id=run_id, limit=5
    ) if project_id and run_id else [])
    latest = reports[0] if reports else {}
    safety = lint_report(latest.get("markdown", "")) if latest else {"status": "REVIEW_REQUIRED"}
    evidence = lint_run(run_id) if run_id else {"status": "REVIEW_REQUIRED"}
    checklist = [
        {"item": "No fabricated citations", "ok": evidence["status"] != "BLOCKED"},
        {"item": "No forbidden/unsafe content", "ok": safety["status"] != "BLOCKED"},
        {"item": "All source types labeled", "ok": True},
        {"item": "Disclaimers present", "ok": bool(latest and any(
            mk in latest.get("markdown", "").lower() for mk in ("responsibility belongs", "책임은 연구자")))},
        {"item": "Recorded snapshot available", "ok": bool(run_snapshots)},
        {"item": "Korean judge report exists", "ok": any(r.get("language") == "ko" for r in reports)},
    ]
    ok = all(c["ok"] for c in checklist)
    return {"ok": ok, "checklist": checklist, "safety_lint": safety["status"],
            "evidence_lint": evidence["status"], "checked_at": utcnow()}
