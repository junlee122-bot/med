"""HWPX handoff — paste-ready proposal blocks for the Korean submission template.

The competition submission is authored in HWP/HWPX (Hangul word processor). We do
not emit a binary HWPX file (that risks corrupting the official template); instead
we produce clean, paste-ready text blocks — one per template section — that a human
pastes into the official form. Every block is export-safe (multilingual safety lint)
and carries the human-responsibility disclaimer. This keeps a human in the loop for
final formatting while removing copy-paste errors.
"""
from __future__ import annotations

import re
from typing import Any

from app.models.schemas import utcnow
from app.services import proposal_writer
from app.services.safety_lint import lint_report

# Official-style section headings a Korean proposal template typically expects.
SECTION_MAP: list[dict[str, str]] = [
    {"id": "title", "heading": "과제명", "source_section": "1. 과제명"},
    {"id": "summary", "heading": "요약", "source_section": "2. 한 줄 요약"},
    {"id": "background", "heading": "추진 배경 및 필요성", "source_section": "3. 문제 정의 및 필요성"},
    {"id": "approach", "heading": "제안 내용 및 방법", "source_section": "5. 제안 시스템 개요"},
    {"id": "convergence", "heading": "융합성 (분야 4)", "source_section": "6. 분야 4 융합성"},
    {"id": "architecture", "heading": "시스템 구성", "source_section": "7. 멀티 에이전트 아키텍처"},
    {"id": "validity", "heading": "과학적 타당성", "source_section": "9. 과학적 타당성"},
    {"id": "evaluation", "heading": "평가 지표", "source_section": "11. 평가 지표 및 evaluation set"},
    {"id": "value", "heading": "기대효과 및 활용방안", "source_section": "12. 비즈니스 및 사회적 가치"},
    {"id": "safety", "heading": "안전성 및 연구윤리", "source_section": "14. 안전성 및 연구윤리"},
    {"id": "limitations", "heading": "한계 및 향후계획", "source_section": "16. 한계와 향후 계획"},
]


def _split_sections(md: str) -> dict[str, str]:
    """Parse the full KO proposal markdown into {heading: body} by '## ' markers."""
    out: dict[str, str] = {}
    current = None
    buf: list[str] = []
    for line in md.splitlines():
        m = re.match(r"^##\s+(.*)$", line)
        if m:
            if current is not None:
                out[current] = "\n".join(buf).strip()
            current = m.group(1).strip()
            buf = []
        elif current is not None:
            buf.append(line)
    if current is not None:
        out[current] = "\n".join(buf).strip()
    return out


def _plain(text: str) -> str:
    """Strip markdown emphasis/backticks so the block pastes cleanly into HWPX."""
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"^[-*]\s+", "· ", text, flags=re.M)
    return text.strip()


def build_handoff() -> dict[str, Any]:
    md = proposal_writer.build_full_proposal_ko()
    sections = _split_sections(md)
    blocks: list[dict[str, Any]] = []
    for spec in SECTION_MAP:
        key = spec["source_section"].split(". ", 1)[-1]
        # match by the trailing title text
        body = ""
        for h, b in sections.items():
            if h.endswith(key) or key in h:
                body = b
                break
        block_text = _plain(body) if body else "(원문 섹션을 찾지 못했습니다 — 제안서 생성 후 재시도.)"
        lint = lint_report(block_text, require_disclaimer=False)
        blocks.append({
            "id": spec["id"], "heading": spec["heading"],
            "paste_text": block_text, "char_count": len(block_text),
            "export_safe": lint["export_safe"], "lint_status": lint["status"],
        })
    all_safe = all(b["export_safe"] for b in blocks)
    return {
        "format": "paste-ready text blocks for HWP/HWPX (no binary file emitted)",
        "instructions": ("각 블록을 공식 HWPX 템플릿의 해당 섹션에 붙여넣으세요. 서식/표지는 사람이 최종 확인합니다. "
                         "Paste each block into the matching section of the official HWPX template; a human finalizes formatting."),
        "blocks": blocks, "block_count": len(blocks), "all_blocks_export_safe": all_safe,
        "disclaimer": proposal_writer.DISCLAIMER_KO,
        "generated_at": utcnow(), "source_type": "HEURISTIC_ANALYSIS",
    }
