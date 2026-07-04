"""Scientific whitepaper generator (EN / KO).

Assembles a structured, honest whitepaper describing the HelixForge AI system:
its rationale, architecture, real tool integrations, evidence-grading and
governance layers, evaluation protocol, and — prominently — its limitations,
safety controls, and the human-responsibility statement.

The document is deterministic. A handful of real figures are pulled from the
existing services (evidence grading, medchem review, translational readiness,
…) through best-effort probes; where a figure is unavailable the text falls
back to an honest placeholder rather than fabricating a number. No wet-lab,
clinical, regulatory, or synthesis content is ever generated.
"""
from __future__ import annotations

import uuid
from typing import Any, Optional

from app.models.schemas import SourceType, utcnow
from app.storage import db

DISCLAIMER_EN = (
    "This system is research decision support only. It does not replace expert "
    "scientific, clinical, regulatory, legal, or ethical review. Final "
    "responsibility belongs to the human research team."
)
DISCLAIMER_KO = (
    "본 시스템은 연구 의사결정 보조 도구이며 전문가 검토를 대체하지 않습니다. "
    "최종 판단과 책임은 연구자에게 있습니다."
)
SOURCE_TYPE_LEGEND = (
    "REAL_TOOL_OUTPUT · RECORDED_REAL_TOOL_OUTPUT · CONFIGURED_BUT_NOT_RUN · "
    "TOOL_ERROR · HEURISTIC_ANALYSIS · ASSUMPTION · BASELINE_MODEL_OUTPUT · "
    "SAFETY_REDACTED · HUMAN_INPUT"
)

# Canonical 25-section structure (order is contractual).
SECTION_TITLES_EN: list[str] = [
    "Abstract",
    "Problem statement",
    "Field 4 fusion rationale",
    "System overview",
    "Multi-agent architecture",
    "Real tool integrations",
    "Evidence and claim grading",
    "Target biology review",
    "Molecule candidate pipeline",
    "ChEMBL assay normalization",
    "Medicinal chemistry review",
    "Applicability domain",
    "ADMET validation protocol",
    "Docking governance",
    "Multi-objective optimization",
    "Clinical precedent review",
    "Translational readiness",
    "Safety and ethics controls",
    "Evaluation protocol",
    "Record/replay reproducibility",
    "Limitations",
    "Roadmap",
    "Appendices",
    "Source-type legend",
    "Human responsibility statement",
]

SECTION_TITLES_KO: list[str] = [
    "초록 (Abstract)",
    "문제 정의 (Problem statement)",
    "Field 4 융합 근거 (Field 4 fusion rationale)",
    "시스템 개요 (System overview)",
    "멀티 에이전트 아키텍처 (Multi-agent architecture)",
    "실제 도구 통합 (Real tool integrations)",
    "근거 및 주장 등급화 (Evidence and claim grading)",
    "표적 생물학 검토 (Target biology review)",
    "분자 후보 파이프라인 (Molecule candidate pipeline)",
    "ChEMBL 활성 정규화 (ChEMBL assay normalization)",
    "의약화학 검토 (Medicinal chemistry review)",
    "적용 가능 범위 (Applicability domain)",
    "ADMET 검증 프로토콜 (ADMET validation protocol)",
    "도킹 거버넌스 (Docking governance)",
    "다목적 최적화 (Multi-objective optimization)",
    "임상 선례 검토 (Clinical precedent review)",
    "중개연구 준비도 (Translational readiness)",
    "안전 및 윤리 통제 (Safety and ethics controls)",
    "평가 프로토콜 (Evaluation protocol)",
    "기록/재생 재현성 (Record/replay reproducibility)",
    "한계 (Limitations)",
    "로드맵 (Roadmap)",
    "부록 (Appendices)",
    "출처 유형 범례 (Source-type legend)",
    "인간 책임 선언 (Human responsibility statement)",
]


def _gather() -> dict[str, Any]:
    """Best-effort, deterministic figures pulled from existing services."""
    state: dict[str, Any] = {
        "run_count": 0,
        "graded_claims": "no run yet",
        "grade_distribution": "no run yet",
        "medchem_count": "no run yet",
        "rdkit_available": "unknown",
        "readiness": "no run yet",
        "clinical": "no run yet",
        "governance": "not audited",
        "vina_bin": "",
        "reinvent4_bin": "",
    }
    try:
        state["run_count"] = len(db.list_records("workflow_runs", limit=50))
    except Exception:
        pass
    try:
        from app.config import get_settings

        s = get_settings()
        state["vina_bin"] = s.vina_bin or "(unset)"
        state["reinvent4_bin"] = s.reinvent4_bin or "(unset)"
    except Exception:
        pass
    try:
        from app.services import evidence_grading

        g = evidence_grading.grade_run(None)
        state["graded_claims"] = g.get("total_claims", 0)
        state["grade_distribution"] = g.get("grade_distribution", {})
    except Exception:
        pass
    try:
        from app.services import medchem_review

        m = medchem_review.review_run(None)
        state["medchem_count"] = m.get("count", 0)
        state["rdkit_available"] = m.get("rdkit_available", "unknown")
    except Exception:
        pass
    try:
        from app.services import translational_readiness

        t = translational_readiness.assess_run(None)
        state["readiness"] = t.get("readiness_level", "no run yet")
    except Exception:
        pass
    try:
        from app.services import clinical_precedent_review

        c = clinical_precedent_review.review_run(None)
        state["clinical"] = c.get("summary") or c.get("status") or "reviewed"
    except Exception:
        pass
    try:
        from app.services import source_type_governance

        a = source_type_governance.audit()
        state["governance"] = a.get("status", "audited")
    except Exception:
        pass
    return state


def _tool_status(state: dict[str, Any]) -> str:
    return (
        f"AutoDock Vina (`{state['vina_bin']}`) and REINVENT4 "
        f"(`{state['reinvent4_bin']}`) are integrated and health-checked but "
        "**CONFIGURED_BUT_NOT_RUN**; no docking or generative run has been executed and "
        "neither is reported as a completed real result."
    )


def _render_en(state: dict[str, Any]) -> str:
    p = [
        "# HelixForge AI — Scientific Whitepaper\n",
        f"## 1. {SECTION_TITLES_EN[0]}\n"
        "HelixForge AI is a research decision-support system that fuses literature, "
        "bioactivity, clinical-trial, and cheminformatics evidence into a traceable, "
        "source-typed workflow for early target and molecule triage. Its defining property "
        "is honesty by construction: every value is provenance-labeled and no output "
        "asserts clinical, regulatory, or wet-lab fact.\n",
        f"## 2. {SECTION_TITLES_EN[1]}\n"
        "Early-stage discovery drowns in fragmented public evidence, and generic language "
        "models readily overclaim. The problem this system addresses is organizing that "
        "evidence while making the strength — and the limits — of every claim explicit.\n",
        f"## 3. {SECTION_TITLES_EN[2]}\n"
        "The system deliberately fuses four fields — biomedical literature, bioactivity "
        "chemistry, clinical evidence, and machine reasoning — because triage quality "
        "improves when these signals are cross-checked rather than used in isolation.\n",
        f"## 4. {SECTION_TITLES_EN[3]}\n"
        "A FastAPI backend orchestrates real tools, persistence, and governance. Data flows "
        "from retrieval, through grading and review, into a human-facing summary, with an "
        "audit trail at every step.\n"
        f"Observed: {state['run_count']} recorded workflow run(s).\n",
        f"## 5. {SECTION_TITLES_EN[4]}\n"
        "Cooperating agents (planner, retriever, critic, reviewer) each hold a narrow, "
        "auditable responsibility. The critic actively challenges weak claims and forces "
        "re-grading; no agent bypasses the safety lint.\n",
        f"## 6. {SECTION_TITLES_EN[5]}\n"
        "Live integrations: PubMed/NCBI, ChEMBL/EMBL-EBI, ClinicalTrials.gov v2, TDC/PyTDC, "
        "and RDKit. Each result is tagged REAL_TOOL_OUTPUT (or RECORDED_REAL_TOOL_OUTPUT on "
        f"replay). {_tool_status(state)}\n",
        f"## 7. {SECTION_TITLES_EN[6]}\n"
        "Every claim is graded A–F by the strength of its supporting evidence, with hard "
        "ceilings so assay or computational evidence can never be presented as clinical "
        "proof. Failed citations and contradictions force downgrades.\n"
        f"Observed: {state['graded_claims']} claim(s) graded; distribution "
        f"{state['grade_distribution']}.\n",
        f"## 8. {SECTION_TITLES_EN[7]}\n"
        "Candidate targets are reviewed for disease association, druggability signals, and "
        "known liabilities from public data — as hypotheses for expert review, not "
        "established fact.\n",
        f"## 9. {SECTION_TITLES_EN[8]}\n"
        "Molecule candidates are imported from ChEMBL and validated with RDKit; invalid "
        "structures are never recommended.\n"
        f"Observed: {state['medchem_count']} molecule(s) reviewed; RDKit available = "
        f"{state['rdkit_available']}.\n",
        f"## 10. {SECTION_TITLES_EN[9]}\n"
        "ChEMBL activities are normalized (units, activity types, pChEMBL) so that measured "
        "potency is comparable and clearly separated from computed estimates.\n",
        f"## 11. {SECTION_TITLES_EN[10]}\n"
        "A medicinal-chemistry review flags property and structural-alert concerns "
        "(druglikeness, PAINS-style filters). It performs no synthesis planning and gives "
        "no dosing guidance.\n",
        f"## 12. {SECTION_TITLES_EN[11]}\n"
        "The applicability domain is enforced and surfaced: reliability is highest for "
        "well-studied targets with abundant data and degrades for sparse or novel targets; "
        "out-of-domain inputs are flagged for expert review.\n",
        f"## 13. {SECTION_TITLES_EN[12]}\n"
        "ADMET signals come from public datasets and models and are labeled as model output "
        "(BASELINE_MODEL_OUTPUT / HEURISTIC_ANALYSIS), never as a safety determination.\n",
        f"## 14. {SECTION_TITLES_EN[13]}\n"
        "Docking is governed rather than assumed: AutoDock Vina is CONFIGURED_BUT_NOT_RUN, "
        "so no docking scores are presented as real results in this deployment.\n",
        f"## 15. {SECTION_TITLES_EN[14]}\n"
        "Candidate ranking uses transparent multi-objective (Pareto) trade-offs across "
        "validity, druglikeness, novelty, and evidence — with weights disclosed, not "
        "hidden.\n",
        f"## 16. {SECTION_TITLES_EN[15]}\n"
        "ClinicalTrials.gov precedent indicates prior interest in a target or modality; it "
        "is precedent, not proof of efficacy, and is graded accordingly.\n"
        f"Observed clinical-precedent status: {state['clinical']}.\n",
        f"## 17. {SECTION_TITLES_EN[16]}\n"
        "Translational readiness is reported on a capped scale (never above "
        "TRL_4_READY_FOR_EXPERIMENTAL_PLANNING) so the system can never imply wet-lab or "
        "clinical success.\n"
        f"Observed readiness: {state['readiness']}.\n",
        f"## 18. {SECTION_TITLES_EN[17]}\n"
        "Safety and ethics controls include a safety lint that blocks forbidden categories "
        "(synthesis routes, reagents, dosing, hazardous content), overclaim detection, and "
        "SAFETY_REDACTED labeling. These guardrails cannot be bypassed by any agent.\n",
        f"## 19. {SECTION_TITLES_EN[18]}\n"
        "Evaluation is descriptive and offline-safe: retrospective rediscovery, citation "
        "integrity, molecule validity, self-correction counts, and governance audits. "
        "Samples are small and support qualitative confidence only.\n"
        f"Observed governance status: {state['governance']}.\n",
        f"## 20. {SECTION_TITLES_EN[19]}\n"
        "A record/replay layer captures real tool outputs as timestamped snapshots "
        "(metadata only where applicable) for reproducible, offline demonstration; replayed "
        "data is labeled RECORDED_REAL_TOOL_OUTPUT and never relabeled as live.\n",
        f"## 21. {SECTION_TITLES_EN[20]}\n"
        "Limitations. No clinical validation and no regulatory approval is claimed; the "
        "system is not a medical device. Computational and assay signals are not "
        "experimental proof and are not proof of efficacy. Small evaluation samples "
        "preclude statistical-significance claims. Coverage depends on upstream public "
        "databases. Configured-but-not-run tools contribute no results.\n",
        f"## 22. {SECTION_TITLES_EN[21]}\n"
        "Roadmap. Broaden target/disease coverage, expand the rediscovery benchmark, and — "
        "only under explicit human control and appropriate safety review — enable the "
        "currently-not-run docking and generative tools.\n",
        f"## 23. {SECTION_TITLES_EN[22]}\n"
        "Appendices. Companion governance artifacts (system/model/data cards, risk "
        "register, traceability matrix, validation protocol, and the "
        "what-we-do-not-claim sheet) accompany this whitepaper.\n",
        f"## 24. {SECTION_TITLES_EN[23]}\n"
        f"`{SOURCE_TYPE_LEGEND}`\n\n"
        "Every surfaced value carries exactly one of these labels; HEURISTIC_ANALYSIS marks "
        "rule-based synthesis and CONFIGURED_BUT_NOT_RUN marks integrated-but-unexecuted "
        "tools.\n",
        f"## 25. {SECTION_TITLES_EN[24]}\n"
        f"> {DISCLAIMER_EN}\n\n"
        f"> {DISCLAIMER_KO}\n",
    ]
    return "\n".join(p)


def _render_ko(state: dict[str, Any]) -> str:
    t = SECTION_TITLES_KO
    p = [
        "# HelixForge AI — 과학 백서 (Scientific Whitepaper)\n",
        f"## 1. {t[0]}\n"
        "HelixForge AI는 문헌·생리활성·임상시험·케모인포매틱스 근거를 융합하여, 초기 표적/분자 "
        "선별을 위한 추적 가능하고 출처가 표시된 워크플로를 제공하는 연구 의사결정 보조 시스템입니다. "
        "모든 값에는 출처 유형이 부여되며, 임상·규제·실험(wet-lab) 사실을 주장하지 않습니다.\n",
        f"## 2. {t[1]}\n"
        "초기 신약 탐색은 파편화된 공개 근거로 인해 어렵고, 범용 언어모델은 과대주장(overclaim)을 "
        "하기 쉽습니다. 본 시스템은 근거를 정리하면서 각 주장의 강도와 한계를 명시하는 문제를 다룹니다.\n",
        f"## 3. {t[2]}\n"
        "생의학 문헌, 생리활성 화학, 임상 근거, 기계 추론의 네 분야를 융합합니다. 이들 신호를 "
        "개별적으로 쓰기보다 상호 교차검증할 때 선별 품질이 향상되기 때문입니다.\n",
        f"## 4. {t[3]}\n"
        "FastAPI 백엔드가 실제 도구, 저장소, 거버넌스를 오케스트레이션합니다. 검색 → 등급화·검토 → "
        "사람이 읽는 요약으로 데이터가 흐르며 모든 단계가 감사 로그로 남습니다.\n"
        f"관측값: 기록된 워크플로 실행 {state['run_count']}건.\n",
        f"## 5. {t[4]}\n"
        "계획·검색·비평·검토 에이전트가 각각 좁고 감사 가능한 역할을 맡습니다. 비평 에이전트는 약한 "
        "주장을 능동적으로 반박하고 재등급화를 유도하며, 어떤 에이전트도 안전 린트를 우회하지 못합니다.\n",
        f"## 6. {t[5]}\n"
        "실시간 통합: PubMed/NCBI, ChEMBL/EMBL-EBI, ClinicalTrials.gov v2, TDC/PyTDC, RDKit. "
        "각 결과는 REAL_TOOL_OUTPUT(재생 시 RECORDED_REAL_TOOL_OUTPUT)로 표시됩니다. "
        f"{_tool_status(state)}\n",
        f"## 7. {t[6]}\n"
        "모든 주장은 근거 강도에 따라 A–F로 등급화되며, 분석/전산 근거가 임상적 증명으로 표시될 수 "
        "없도록 상한이 걸립니다. 실패한 인용과 상충 근거는 등급을 강등시킵니다.\n"
        f"관측값: {state['graded_claims']}개 주장 등급화, 분포 {state['grade_distribution']}.\n",
        f"## 8. {t[7]}\n"
        "후보 표적은 질환 연관성, 성약성 신호, 알려진 위험을 공개 데이터로 검토합니다. 확정된 사실이 "
        "아니라 전문가 검토용 가설입니다.\n",
        f"## 9. {t[8]}\n"
        "분자 후보는 ChEMBL에서 가져와 RDKit으로 검증하며, 유효하지 않은 구조는 추천되지 않습니다.\n"
        f"관측값: 분자 {state['medchem_count']}건 검토, RDKit 사용 가능 = {state['rdkit_available']}.\n",
        f"## 10. {t[9]}\n"
        "ChEMBL 활성값(단위, 활성 유형, pChEMBL)을 정규화하여 측정된 역가를 비교 가능하게 하고 "
        "계산된 추정값과 명확히 구분합니다.\n",
        f"## 11. {t[10]}\n"
        "의약화학 검토는 성질·구조 경보(성약성, PAINS류 필터) 우려를 표시합니다. 합성 설계나 용량 "
        "안내는 수행하지 않습니다.\n",
        f"## 12. {t[11]}\n"
        "적용 가능 범위를 강제·표시합니다. 데이터가 풍부한 잘 연구된 표적에서 신뢰도가 가장 높고 "
        "희소·신규 표적에서는 낮아지며, 범위를 벗어난 입력은 전문가 검토 대상으로 표시됩니다.\n",
        f"## 13. {t[12]}\n"
        "ADMET 신호는 공개 데이터셋·모델에서 비롯되며 모델 출력(BASELINE_MODEL_OUTPUT / "
        "HEURISTIC_ANALYSIS)으로 표시될 뿐 안전성 판정이 아닙니다.\n",
        f"## 14. {t[13]}\n"
        "도킹은 가정하지 않고 통제합니다. AutoDock Vina는 CONFIGURED_BUT_NOT_RUN이며, 본 배포에서 "
        "도킹 점수를 실제 결과로 제시하지 않습니다.\n",
        f"## 15. {t[14]}\n"
        "후보 순위는 유효성·성약성·신규성·근거에 대한 투명한 다목적(파레토) 절충으로 정하며, 가중치는 "
        "숨기지 않고 공개합니다.\n",
        f"## 16. {t[15]}\n"
        "ClinicalTrials.gov 선례는 표적/모달리티에 대한 사전 관심을 나타낼 뿐 효능의 증명이 아니며 "
        "그에 맞게 등급화됩니다.\n"
        f"관측된 임상 선례 상태: {state['clinical']}.\n",
        f"## 17. {t[16]}\n"
        "중개연구 준비도는 상한이 걸린 척도(TRL_4_READY_FOR_EXPERIMENTAL_PLANNING을 초과하지 않음)로 "
        "보고되어 실험적·임상적 성공을 암시할 수 없습니다.\n"
        f"관측된 준비도: {state['readiness']}.\n",
        f"## 18. {t[17]}\n"
        "안전 및 윤리 통제에는 금지 범주(합성 경로, 시약, 용량, 위험 콘텐츠)를 차단하는 안전 린트, "
        "과대주장 탐지, SAFETY_REDACTED 표시가 포함됩니다. 이 가드레일은 어떤 에이전트도 우회할 수 "
        "없습니다.\n",
        f"## 19. {t[18]}\n"
        "평가는 서술적이며 오프라인에서 안전합니다: 회고적 재발견, 인용 무결성, 분자 유효성, 자기수정 "
        "횟수, 거버넌스 감사. 표본이 작아 정성적 신뢰만 뒷받침합니다.\n"
        f"관측된 거버넌스 상태: {state['governance']}.\n",
        f"## 20. {t[19]}\n"
        "기록/재생 계층은 실제 도구 출력을 타임스탬프가 있는 스냅샷(해당 시 메타데이터만)으로 캡처하여 "
        "재현 가능한 오프라인 시연을 지원합니다. 재생 데이터는 RECORDED_REAL_TOOL_OUTPUT로 표시되며 "
        "실시간으로 재표시되지 않습니다.\n",
        f"## 21. {t[20]}\n"
        "한계(Limitations). 임상 검증이나 규제 승인을 주장하지 않으며 의료기기가 아닙니다. 전산·분석 "
        "신호는 실험적 증명이 아니고 효능의 증명도 아닙니다. 작은 표본으로 통계적 유의성을 주장하지 "
        "않습니다. 범위는 상류 공개 데이터베이스에 의존합니다. 실행되지 않은 도구는 결과를 제공하지 "
        "않습니다.\n",
        f"## 22. {t[21]}\n"
        "로드맵. 표적/질환 범위 확대, 재발견 벤치마크 확장, 그리고 명시적 인간 통제와 적절한 안전 검토 "
        "하에서만 현재 실행되지 않은 도킹·생성 도구를 활성화합니다.\n",
        f"## 23. {t[22]}\n"
        "부록. 시스템/모델/데이터 카드, 리스크 레지스터, 추적성 매트릭스, 검증 프로토콜, "
        "'우리가 주장하지 않는 것' 시트 등 거버넌스 산출물이 본 백서와 함께 제공됩니다.\n",
        f"## 24. {t[23]}\n"
        f"`{SOURCE_TYPE_LEGEND}`\n\n"
        "표시되는 모든 값에는 위 레이블 중 정확히 하나가 부여됩니다. HEURISTIC_ANALYSIS는 규칙 기반 "
        "합성을, CONFIGURED_BUT_NOT_RUN은 통합되었으나 실행되지 않은 도구를 나타냅니다.\n",
        f"## 25. {t[24]}\n"
        f"> {DISCLAIMER_EN}\n\n"
        f"> {DISCLAIMER_KO}\n",
    ]
    return "\n".join(p)


def generate(lang: str = "en") -> dict[str, Any]:
    """Generate the scientific whitepaper in the requested language.

    Args:
        lang: ``"en"`` or ``"ko"`` (anything else falls back to English).

    Returns:
        A dict with ``id``, ``lang``, ``title``, ``markdown``, ``sections``,
        ``source_type`` (``HEURISTIC_ANALYSIS``), and ``created_at``. Best-effort
        persisted to the ``whitepapers`` table.
    """
    lang = "ko" if str(lang).lower().startswith("ko") else "en"
    state = _gather()
    if lang == "ko":
        markdown = _render_ko(state)
        sections = list(SECTION_TITLES_KO)
        title = "HelixForge AI — 과학 백서"
    else:
        markdown = _render_en(state)
        sections = list(SECTION_TITLES_EN)
        title = "HelixForge AI — Scientific Whitepaper"

    record: dict[str, Any] = {
        "id": f"wp-{uuid.uuid4().hex[:8]}",
        "lang": lang,
        "language": lang,
        "title": title,
        "markdown": markdown,
        "sections": sections,
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
        "created_at": utcnow(),
    }
    try:
        db.insert("whitepapers", record)
    except Exception:
        pass
    return record


def latest(lang: str = "en") -> Optional[dict[str, Any]]:
    """Return the most recently persisted whitepaper for ``lang``, or ``None``."""
    lang = "ko" if str(lang).lower().startswith("ko") else "en"
    try:
        for rec in db.list_records("whitepapers", limit=200):
            if rec.get("lang") == lang or rec.get("language") == lang:
                return rec
    except Exception:
        return None
    return None


def export() -> dict[str, Any]:
    """Generate both language editions and return their markdown together."""
    en = generate("en")
    ko = generate("ko")
    return {
        "generated_at": utcnow(),
        "en": en["markdown"],
        "ko": ko["markdown"],
        "disclaimer": f"{DISCLAIMER_EN}\n\n{DISCLAIMER_KO}",
        "source_type": SourceType.HEURISTIC_ANALYSIS.value,
    }
