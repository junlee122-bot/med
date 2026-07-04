"""Benchmark scenario presets.

These are RETRIEVAL / ROBUSTNESS benchmarks, not scientific claims. Each is run
against the real tools (or a replay). If evidence is not found, that is reported
honestly — success is defined only as pipeline robustness + target rediscovery.
"""
from __future__ import annotations

from typing import Any

SCENARIOS: list[dict[str, Any]] = [
    {"id": "egfr-nsclc", "name": "EGFR / NSCLC", "condition": "non-small cell lung cancer",
     "target_query": "EGFR", "expected_target_hint": "EGFR", "modality": "small molecule",
     "benchmark_type": "retrospective_rediscovery", "max_results": 4, "status": "primary",
     "rationale": "Primary retrospective-rediscovery anchor.",
     "safety_notes": "No synthesis routes; screening only."},
    {"id": "braf-melanoma", "name": "BRAF / Melanoma", "condition": "melanoma",
     "target_query": "BRAF", "expected_target_hint": "BRAF", "modality": "small molecule",
     "benchmark_type": "robustness", "max_results": 4, "status": "benchmark",
     "rationale": "Well-studied oncogenic kinase.", "safety_notes": "Screening only."},
    {"id": "jak2-mpn", "name": "JAK2 / MPN", "condition": "myeloproliferative neoplasm",
     "target_query": "JAK2", "expected_target_hint": "JAK2", "modality": "small molecule",
     "benchmark_type": "robustness", "max_results": 4, "status": "benchmark",
     "rationale": "Hematologic driver.", "safety_notes": "Screening only."},
    {"id": "pcsk9-chol", "name": "PCSK9 / Hypercholesterolemia", "condition": "hypercholesterolemia",
     "target_query": "PCSK9", "expected_target_hint": "PCSK9", "modality": "any",
     "benchmark_type": "robustness", "max_results": 4, "status": "benchmark",
     "rationale": "Biologic-dominant target — tests small-molecule tractability honesty.",
     "safety_notes": "Screening only."},
    {"id": "tnf-ra", "name": "TNF / Rheumatoid arthritis", "condition": "rheumatoid arthritis",
     "target_query": "TNF", "expected_target_hint": "TNF", "modality": "biologic",
     "benchmark_type": "robustness", "max_results": 4, "status": "benchmark",
     "rationale": "Biologic target; tests non-small-molecule handling.", "safety_notes": "Screening only."},
    {"id": "alk-nsclc", "name": "ALK / NSCLC", "condition": "non-small cell lung cancer",
     "target_query": "ALK", "expected_target_hint": "ALK", "modality": "small molecule",
     "benchmark_type": "robustness", "max_results": 4, "status": "benchmark",
     "rationale": "Distinct oncogenic subset.", "safety_notes": "Screening only."},
    {"id": "kras-lung", "name": "KRAS / Lung cancer", "condition": "lung cancer",
     "target_query": "KRAS", "expected_target_hint": "KRAS", "modality": "small molecule",
     "benchmark_type": "robustness", "max_results": 4, "status": "benchmark",
     "rationale": "Historically difficult target.", "safety_notes": "Screening only."},
    {"id": "her2-breast", "name": "HER2 / Breast cancer", "condition": "breast cancer",
     "target_query": "ERBB2", "expected_target_hint": "ERBB2", "modality": "any",
     "benchmark_type": "robustness", "max_results": 4, "status": "benchmark",
     "rationale": "HER2/ERBB2 amplified subset.", "safety_notes": "Screening only."},
]

BY_ID = {s["id"]: s for s in SCENARIOS}
