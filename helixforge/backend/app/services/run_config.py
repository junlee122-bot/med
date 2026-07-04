"""New Run wizard — validated run configuration presets.

Provides curated, scientifically-grounded target/condition presets so a judge can
launch a meaningful run in one click, plus validation of a custom configuration
before it is submitted to the agent engine. Does not run anything itself — it
prepares and validates the payload the existing /api/workflow/run-agentic-pipeline
endpoint consumes.
"""
from __future__ import annotations

from typing import Any

from app.models.schemas import utcnow

# Curated presets — real, well-precedented target/indication pairs used across the
# scenario matrix. Each is a legitimate oncology / cardiometabolic / immunology target.
PRESETS: list[dict[str, Any]] = [
    {"id": "egfr_nsclc", "label": "EGFR — 비소세포폐암 (NSCLC)", "target_query": "EGFR",
     "condition": "non-small cell lung cancer", "rationale": "회고적 재발견 검증에 사용하는 기준 케이스.",
     "recommended": True},
    {"id": "braf_melanoma", "label": "BRAF — 흑색종 (melanoma)", "target_query": "BRAF",
     "condition": "melanoma", "rationale": "V600E 변이 표적치료 선례 풍부."},
    {"id": "jak2_myelofibrosis", "label": "JAK2 — 골수섬유증", "target_query": "JAK2",
     "condition": "myelofibrosis", "rationale": "키나아제 저해제 임상 선례."},
    {"id": "pcsk9_hchol", "label": "PCSK9 — 고콜레스테롤혈증", "target_query": "PCSK9",
     "condition": "hypercholesterolemia", "rationale": "심혈관 대사 타깃 다양성 확보."},
    {"id": "tnf_ra", "label": "TNF — 류마티스 관절염", "target_query": "TNF",
     "condition": "rheumatoid arthritis", "rationale": "면역학 타깃 — 분야 다양성."},
    {"id": "alk_nsclc", "label": "ALK — 비소세포폐암", "target_query": "ALK",
     "condition": "non-small cell lung cancer", "rationale": "융합 유전자 표적."},
    {"id": "kras_crc", "label": "KRAS — 대장암", "target_query": "KRAS",
     "condition": "colorectal cancer", "rationale": "난치성 타깃 — 최신 표적치료."},
    {"id": "her2_breast", "label": "HER2 — 유방암", "target_query": "HER2",
     "condition": "breast cancer", "rationale": "항체·소분자 병용 선례."},
]

MODES = [
    {"id": "retrospective_rediscovery", "label": "회고적 재발견 (권장)",
     "note": "알려진 약물/타깃을 재발견해 과학적 타당성을 검증.", "recommended": True},
    {"id": "prospective_exploration", "label": "전향적 탐색",
     "note": "새 후보 우선순위화 — 결과는 반드시 전문가 검토 필요."},
]

INJECTION_OPTIONS = [
    {"id": "invalid_smiles", "label": "잘못된 SMILES"},
    {"id": "fake_citation", "label": "허위 인용"},
    {"id": "tool_failure", "label": "도구 실패"},
    {"id": "safety_flag", "label": "안전 위험"},
    {"id": "overclaim", "label": "과장 표현"},
    {"id": "contradictory_evidence", "label": "모순 근거"},
]

_VALID_INJECTIONS = {o["id"] for o in INJECTION_OPTIONS}
_VALID_MODES = {m["id"] for m in MODES}


def list_configs() -> dict[str, Any]:
    return {"presets": PRESETS, "modes": MODES, "error_injection_options": INJECTION_OPTIONS,
            "defaults": {"max_results": 8, "evaluation_mode": "retrospective_rediscovery",
                         "create_reinvent_config": True, "run_vina_fixture": False},
            "note": "presets는 실제 타깃/적응증 쌍입니다. 실행은 /api/workflow/run-agentic-pipeline로 전달됩니다.",
            "checked_at": utcnow()}


def validate(cfg: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    tq = (cfg.get("target_query") or "").strip()
    cond = (cfg.get("condition") or "").strip()
    if not tq:
        errors.append("target_query is required.")
    elif len(tq) > 64:
        errors.append("target_query too long (max 64).")
    if not cond:
        warnings.append("condition is empty — a disease/indication improves evidence retrieval.")
    mr = cfg.get("max_results", 8)
    if not isinstance(mr, int) or not (1 <= mr <= 50):
        errors.append("max_results must be an integer in 1..50.")
    mode = cfg.get("evaluation_mode", "retrospective_rediscovery")
    if mode not in _VALID_MODES:
        errors.append(f"evaluation_mode must be one of {sorted(_VALID_MODES)}.")
    injections = cfg.get("error_injections") or {}
    if isinstance(injections, dict):
        bad = [k for k in injections if k not in _VALID_INJECTIONS]
        if bad:
            errors.append(f"unknown error_injections: {bad}")
        if sum(1 for v in injections.values() if v) > 3:
            warnings.append("3개 이하의 오류 주입을 권장합니다(데모 가독성).")
    # Assemble the normalized payload the engine expects.
    payload = {
        "project_id": cfg.get("project_id"),
        "target_query": tq or "EGFR",
        "condition": cond or "non-small cell lung cancer",
        "max_results": mr if isinstance(mr, int) and 1 <= mr <= 50 else 8,
        "evaluation_mode": mode if mode in _VALID_MODES else "retrospective_rediscovery",
        "run_vina_fixture": bool(cfg.get("run_vina_fixture", False)),
        "create_reinvent_config": bool(cfg.get("create_reinvent_config", True)),
        "error_injections": {k: bool(v) for k, v in injections.items() if k in _VALID_INJECTIONS},
    }
    return {"valid": not errors, "errors": errors, "warnings": warnings,
            "normalized_payload": payload, "checked_at": utcnow()}
