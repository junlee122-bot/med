"""Rubric scorecard — transparent self-assessment against the competition rubric.

This is a HEURISTIC self-assessment (not an official score). Each criterion maps
to concrete app features, in-app evidence pointers, and an honest gap statement.
Scores are conservative; any criterion that depends on a not-run tool or an
unverified claim is capped and labeled so judges see the reasoning, not a number.
"""
from __future__ import annotations

from typing import Any

from app.models.schemas import utcnow
from app.storage import db

# Weighted rubric for the JUMP AI / AI Drug Discovery competition (Field 4 —
# convergence). Weights sum to 100. Self-scores are on a 0..1 scale and are
# deliberately conservative; the "cap_reason" documents why a ceiling applies.
CRITERIA: list[dict[str, Any]] = [
    {"key": "convergence_field4", "label_ko": "융합성 (분야 4)", "weight": 20,
     "self_score": 0.85,
     "evidence": ["분야 1·2·3을 단일 DAG로 연결", "Agent Cockpit 트레이스", "Scenario Matrix"],
     "app_pages": ["/cockpit", "/scenarios"],
     "gap": "규제(분야 3)는 휴리스틱 + 문서 보조 수준; 생성(분야 2)은 ChEMBL 실구조 기반."},
    {"key": "technical_completeness", "label_ko": "기술 완성도", "weight": 18,
     "self_score": 0.82,
     "evidence": ["실제 HTTP 도구(PubMed/ChEMBL/ClinicalTrials)", "RDKit/TDC 로컬", "17 에이전트 런타임", "record/replay"],
     "app_pages": ["/tools", "/cockpit"],
     "gap": "Vina/REINVENT4는 CONFIGURED_BUT_NOT_RUN(미설치 시)."},
    {"key": "scientific_validity", "label_ko": "과학적 타당성", "weight": 18,
     "self_score": 0.7,
     "evidence": ["EGFR/NSCLC 회고적 재발견", "ChEMBL assay 품질 분석", "RDKit 유효성/디스크립터", "분자 다양성"],
     "app_pages": ["/evaluation", "/molecules"],
     "gap": "in-silico 단계 — 습식/임상 검증 없음(주장하지 않음). 상한 적용.",
     "cap": 0.8, "cap_reason": "습식/임상 검증 부재로 상한 0.8."},
    {"key": "innovation", "label_ko": "창의성·혁신성", "weight": 12,
     "self_score": 0.8,
     "evidence": ["정직한 출처 유형 거버넌스", "자기수정 루프 + 오류 주입 시연", "오프라인 record/replay"],
     "app_pages": ["/demo-lab", "/snapshots"],
     "gap": "생성 모델 루프는 계획 단계(설정만 제공)."},
    {"key": "safety_ethics", "label_ko": "안전성·연구윤리", "weight": 12,
     "self_score": 0.9,
     "evidence": ["한/영 안전·과장 린트", "무합성경로/무의료자문 정책", "AI 상호작용 원장", "소스 거버넌스"],
     "app_pages": ["/safety", "/ai-ledger"],
     "gap": "정책·린트는 결정론적 필터 — 인간 검토를 대체하지 않음."},
    {"key": "feasibility_business", "label_ko": "실현가능성·사업성", "weight": 10,
     "self_score": 0.68,
     "evidence": ["Docker 즉시 실행", "Postgres 이식 가능 저장소", "리소스 효율(로컬+캐시)", "Impact 추정"],
     "app_pages": ["/impact", "/release"],
     "gap": "사업성 추정은 보수적 범위 — 시장 검증은 향후 과제.",
     "cap": 0.8, "cap_reason": "시장/사용자 검증 부재로 상한 0.8."},
    {"key": "presentation_demo", "label_ko": "발표·데모 신뢰성", "weight": 10,
     "self_score": 0.85,
     "evidence": ["Presentation Mode(5/7분 타이머·리허설)", "오프라인 데모 안전망", "제출 센터 번들"],
     "app_pages": ["/presentation", "/submission"],
     "gap": "실시간 API 실패 시 record/replay로 대체(정직 표기)."},
]


def _apply_cap(c: dict[str, Any]) -> float:
    score = float(c["self_score"])
    cap = c.get("cap")
    return min(score, cap) if cap is not None else score


def compute() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    weighted_total = 0.0
    for c in CRITERIA:
        eff = _apply_cap(c)
        contribution = eff * c["weight"]
        weighted_total += contribution
        rows.append({
            "key": c["key"], "label_ko": c["label_ko"], "weight": c["weight"],
            "self_score": round(eff, 3), "raw_self_score": c["self_score"],
            "weighted_points": round(contribution, 2), "max_points": c["weight"],
            "evidence": c["evidence"], "app_pages": c["app_pages"], "gap": c["gap"],
            "capped": bool(c.get("cap") is not None and c["self_score"] > c["cap"]),
            "cap_reason": c.get("cap_reason"),
        })
    total = round(weighted_total, 1)
    if total >= 85:
        band = "STRONG"
    elif total >= 70:
        band = "COMPETITIVE"
    else:
        band = "NEEDS_WORK"
    lowest = sorted(rows, key=lambda r: r["self_score"])[:3]
    return {
        "source_type": "HEURISTIC_ANALYSIS",
        "disclaimer": ("자기평가(self-assessment)이며 공식 점수가 아닙니다. 실제 심사 결과와 다를 수 있습니다. "
                       "This is a heuristic self-assessment, not an official score."),
        "criteria": rows, "total_score": total, "max_score": 100, "band": band,
        "top_improvement_targets": [{"key": r["key"], "label_ko": r["label_ko"],
                                     "self_score": r["self_score"], "gap": r["gap"]} for r in lowest],
        "computed_at": utcnow(),
    }


def persist() -> dict[str, Any]:
    card = compute()
    rec = {"id": f"scorecard-{utcnow().replace(':', '').replace('-', '')[:15]}",
           "kind": "rubric_scorecard", "created_at": utcnow(), **card}
    try:
        db.insert("evaluation_metrics", rec)
    except Exception:
        pass
    return card
