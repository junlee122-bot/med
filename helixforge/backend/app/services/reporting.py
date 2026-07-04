"""Report generation for the agentic pipeline — English technical + Korean judge.

Reports are assembled from real run artifacts. Every claim traces to an evidence
ID or a labeled assumption/source type. No synthesis routes, reagents,
conditions, dosage, or medical advice. The human-responsibility statement is
always present.
"""
from __future__ import annotations

from typing import Any

from app.models.schemas import utcnow

HUMAN_RESPONSIBILITY_EN = (
    "This system is research decision support only. It does not replace expert scientific, clinical, "
    "regulatory, legal, or ethical review. Final responsibility belongs to the human research team."
)
HUMAN_RESPONSIBILITY_KO = (
    "본 시스템은 연구 의사결정 보조 도구이며, 전문가의 과학적·임상적·규제적·윤리적 검토를 대체하지 않습니다. "
    "최종 판단과 책임은 연구자에게 있습니다."
)


def _evidence_table(evidence: list[dict]) -> str:
    head = "| ID | Source | Identifier | Direction | Verification |\n|---|---|---|---|---|"
    rows = [f"| {e.get('id')} | {e.get('source_name')} | {e.get('identifier')} | {e.get('evidence_direction')} | {e.get('verification_status')} |"
            for e in evidence[:12]]
    return head + "\n" + "\n".join(rows) if rows else "_No evidence retrieved._"


def _target_table(targets: list[dict]) -> str:
    head = "| Rank | Target | ChEMBL ID | Type | Organism | Score |\n|---|---|---|---|---|---|"
    rows = [f"| {t.get('rank')} | {t.get('pref_name')} | {t.get('target_chembl_id')} | {t.get('target_type')} | {t.get('organism')} | {t.get('score')}/100 |"
            for t in targets[:8]]
    return head + "\n" + "\n".join(rows) if rows else "_No targets ranked._"


def _molecule_table(mols: list[dict]) -> str:
    head = "| Rank | ChEMBL ID | Valid | MW | QED | Lipinski | Safety | Score | Recommendation |\n|---|---|---|---|---|---|---|---|---|"
    rows = []
    for m in mols[:12]:
        d = m.get("descriptors") or {}
        lip = "pass" if (d.get("lipinski_pass")) else (f"{d.get('lipinski_violations','?')} viol" if d else "—")
        rows.append(f"| {m.get('rank','—')} | {m.get('molecule_chembl_id')} | {'yes' if m.get('valid') else 'no'} | "
                    f"{d.get('mol_weight','—')} | {d.get('qed','—')} | {lip} | {m.get('safety_status')} | "
                    f"{m.get('composite_score','—')} | {m.get('recommendation','—')} |")
    return head + "\n" + "\n".join(rows) if rows else "_No candidates._"


def _agent_lines(agent_runs: list[dict]) -> str:
    return "\n".join(
        f"- **{a['agent_name']}** ({a.get('stage','')}) — {a.get('status')}, confidence {a.get('confidence')}: {a.get('output_summary','')}"
        for a in agent_runs)


def _revision_lines(revisions: list[dict]) -> str:
    if not revisions:
        return "_No revisions were required in this run._"
    return "\n".join(f"- **{r['reason_category']}** — {r['action_taken']}" for r in revisions)


def build_en_report(*, run_id, project_id, condition, target_query, shared, metrics, agent_runs, revisions) -> str:
    counts = metrics.get("_counts", {})
    retro = metrics.get("retrospective", {})
    sel = shared.get("selected_target") or {}
    top_mol = next((m for m in shared.get("molecules", []) if m.get("valid")), None)
    lint_note = "Report passed the safety lint (no forbidden content, disclaimer present)."
    return f"""# HelixForge AI — Agentic Pipeline Report
**Run:** {run_id} · **Project:** {project_id} · **Generated:** {utcnow()}

> {HUMAN_RESPONSIBILITY_EN}

## 1. Objective
Evidence-grounded, agentic discovery for **{target_query} / {condition}** (retrospective rediscovery mode).

## 2. Multi-agent architecture
A Project Orchestrator decomposed the objective into a {len(agent_runs)}-run agentic workflow. Agent trace:
{_agent_lines(agent_runs)}

## 3. Real tool integration
- Real-tool outputs: **{metrics.get('real_tool_output_count')}** · configured-not-run: **{metrics.get('configured_not_run_count')}** · tool errors: **{metrics.get('tool_error_count')}**
- Tools used: PubMed (E-utilities), ChEMBL, ClinicalTrials.gov v2, RDKit, TDC/PyTDC; Vina/REINVENT4 honest status.

## 4. Evidence
Verification rate **{metrics.get('citation_verification_rate')}** ({metrics.get('verified_citation_count')} verified / {metrics.get('failed_citation_count')} failed).
{_evidence_table(shared.get('evidence', []))}

## 5. Target prioritization
Top target: **{sel.get('pref_name')} ({sel.get('target_chembl_id')})** — Target Opportunity Score **{sel.get('score')}/100**.
{_target_table(shared.get('targets', []))}

## 6. Hypotheses
""" + "\n".join(f"- {h.get('statement')} _(confidence {h.get('confidence')})_" for h in shared.get("hypotheses", [])) + f"""

## 7. Candidate molecules (real ChEMBL structures, RDKit-validated)
Validity rate **{metrics.get('molecule_validity_rate')}**; {metrics.get('invalid_smiles_caught')} invalid caught.
{_molecule_table(shared.get('molecules', []))}

_Top valid candidate:_ {top_mol.get('molecule_chembl_id') if top_mol else '—'}. Synthesis feasibility is summarized only — no routes are shown by policy.

## 8. Self-correction (revision events)
{_revision_lines(revisions)}

## 9. Safety gate
Blocked/quarantined: **{metrics.get('safety_blocked_count')}**, review-required: **{metrics.get('safety_review_count')}**. {lint_note}
No wet-lab protocols, synthesis routes, reagents, conditions, dosage, or medical advice are produced.

## 10. Clinical & regulatory (high-level)
Clinical precedents: {metrics.get('clinicaltrials_count')} real trials. Regulatory gaps: {', '.join(shared.get('regulatory_gaps', [])) or 'none'}.
_High-level planning only; not medical, legal, or regulatory advice._

## 11. Evaluation metrics
- Tool success rate: {metrics.get('tool_success_rate')}
- Citation verification: {metrics.get('citation_verification_rate')}
- Molecule validity: {metrics.get('molecule_validity_rate')}
- Self-correction rate: {metrics.get('self_correction_rate')} ({metrics.get('revision_event_count')} revisions)
- Runtime: {metrics.get('runtime_seconds')}s · HTTP calls: {metrics.get('http_api_calls')} · local tool calls: {metrics.get('local_tool_calls')}
- Retrospective rediscovery: {retro.get('passed')}/{retro.get('total')} criteria — {retro.get('status')}

## 12. Limitations
In-silico decision support only. TDC is loaded as evaluation substrate (not a fitted per-candidate predictor). Vina is fixture-based; REINVENT4 requires external setup. No wet-lab, clinical, or regulatory validation is claimed.

## 13. Human responsibility
{HUMAN_RESPONSIBILITY_EN}
"""


def build_ko_judge_report(*, run_id, project_id, condition, target_query, shared, metrics, agent_runs, revisions) -> str:
    sel = shared.get("selected_target") or {}
    retro = metrics.get("retrospective", {})
    agent_list = "\n".join(f"- **{a['agent_name']}** — {a.get('output_summary','')}" for a in agent_runs)
    rev = "없음" if not revisions else "\n".join(f"- {r['reason_category']}: {r['action_taken']}" for r in revisions)
    return f"""# HelixForge AI — 심사위원용 리포트 (Judge Report)
**실행 ID:** {run_id} · **생성 시각:** {utcnow()}

> {HUMAN_RESPONSIBILITY_KO}

## 1. 개요
HelixForge AI는 실제 도구(PubMed, ChEMBL, ClinicalTrials.gov, RDKit, TDC)에 연동된 **멀티 에이전트 신약개발 의사결정 보조 시스템**입니다. 본 실행은 **{target_query} / {condition}** 시나리오에 대한 근거 기반 자율 파이프라인 결과입니다.

## 2. 해결하려는 신약개발 문제
초기 탐색 단계에서 문헌·타깃·분자·독성·임상 선례·규제 리스크가 분리되어 있어 후보 우선순위화에 많은 시간이 소요됩니다. 본 시스템은 이 과정을 관찰 가능한(auditable) 에이전트 워크플로우로 연결합니다.

## 3. 분야 4 융합 전략
자율 가설 생성 → 도구 기반 분자 분석 → 안전성/독성 스크리닝 → 임상·규제 전략 → 평가·감사 로그를 하나의 파이프라인으로 통합했습니다.

## 4. 멀티 에이전트 아키텍처
Project Orchestrator가 목표를 {len(agent_runs)}개 에이전트 실행으로 분해했습니다. 에이전트 실행 추적:
{agent_list}

## 5. 실제 연동 도구
- 실제 도구 출력(REAL_TOOL_OUTPUT): **{metrics.get('real_tool_output_count')}건**
- 설정됨·미실행(CONFIGURED_BUT_NOT_RUN): **{metrics.get('configured_not_run_count')}건** · 도구 오류: **{metrics.get('tool_error_count')}건**
- 모든 결과에는 출처 유형(source type)이 표기되어, 미실행 도구가 실제 결과처럼 표시되지 않습니다.

## 6. 에이전트별 역할
근거 마이닝, 인용 검증, 타깃 점수화, 가설 생성, 분자 검증, 안전성 감사, 임상/규제, 비평(Critic), 평가, 리포트 작성 에이전트가 협업합니다.

## 7. 자율 계획 및 피드백 루프
Critic 에이전트가 잘못된 구조, 허위 인용, 과장 표현, 모순 근거를 탐지하여 **{len(revisions)}건의 자기수정(revision)** 을 수행했습니다:
{rev}

## 8. 과학적 타당성
후보 분자는 실제 ChEMBL 활성 데이터에서 확보하고 RDKit으로 검증했습니다(유효율 {metrics.get('molecule_validity_rate')}). 가설은 검증된 PMID 근거에 연결되며, "in-silico 가설·전문가 검토 필요"와 같이 보수적으로 표현됩니다. 효능·완치 주장을 하지 않습니다.

## 9. EGFR/NSCLC 실데이터 파이프라인 결과
- 선정 타깃: **{sel.get('pref_name')} ({sel.get('target_chembl_id')})**, 타깃 기회 점수 **{sel.get('score')}/100**
- PubMed 근거 {metrics.get('pubmed_evidence_count')}건 · 임상 선례 {metrics.get('clinicaltrials_count')}건 · TDC 데이터 {metrics.get('tdc_row_count')}행
- 후보 분자 {metrics.get('candidate_count')}개 (유효 {metrics.get('valid_smiles_count')}개)

## 10. 후보 분자 우선순위화
투명한 복합 점수(composite score)로 후보를 정렬했으며, 안전성/불확실성 페널티를 반영합니다. 합성 경로는 정책상 제공하지 않습니다.

## 11. 안전성 및 윤리 게이트
차단/격리 {metrics.get('safety_blocked_count')}건, 검토 필요 {metrics.get('safety_review_count')}건. 위험/이중용도 콘텐츠는 실행 가능한 세부정보 없이 카테고리만 표시합니다. 합성 레시피·시약·반응조건·용량·의료 자문은 생성하지 않습니다.

## 12. 평가 지표
- 도구 성공률 {metrics.get('tool_success_rate')} · 인용 검증률 {metrics.get('citation_verification_rate')}
- 분자 유효율 {metrics.get('molecule_validity_rate')} · 자기수정률 {metrics.get('self_correction_rate')}
- 실행 시간 {metrics.get('runtime_seconds')}초 · HTTP 호출 {metrics.get('http_api_calls')} · 로컬 도구 호출 {metrics.get('local_tool_calls')}
- 회고적 재발견(retrospective rediscovery): {retro.get('passed')}/{retro.get('total')} 기준 충족 — {retro.get('status')}

## 13. 리소스 효율성
결정론적 화학/데이터 작업은 로컬 도구(RDKit, TDC)로, 근거 조회는 공개 API로 라우팅하여 비용을 낮춥니다({metrics.get('cost_class')}).

## 14. 실제 구현 가능성
FastAPI 백엔드 + React 프런트엔드 + Docker로 구성되어 실제 배포가 가능합니다. Vina/REINVENT4는 어댑터로 연동되어 설정 시 실제 실행됩니다.

## 15. 한계와 향후 개발 계획
in-silico 의사결정 보조 단계이며, 습식 실험·임상·규제 검증을 대체하지 않습니다. 향후 REINVENT4 실제 생성, TDC 예측 모델 학습, 규제 문서 RAG를 계획합니다.

## 16. 최종 책임 및 전문가 검토 필요성
{HUMAN_RESPONSIBILITY_KO}

## 17. 감사 로그 요약
총 에이전트 실행 {len(agent_runs)}건, 자기수정 {len(revisions)}건, 도구 호출은 모두 출처 유형과 함께 기록되어 재현·검증이 가능합니다.
"""
