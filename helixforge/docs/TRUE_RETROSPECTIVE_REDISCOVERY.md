# True Retrospective Rediscovery

> Research decision support only. Fable 5 is optional and never supplies scientific ground truth. No wet-lab protocol, synthesis route, dosage, or medical advice. No hidden chain-of-thought. Final responsibility belongs to the human research team. / 최종 판단과 책임은 연구자에게 있습니다.

**Package:** `app/services/rediscovery/` · **Endpoints:** `/api/rediscovery/{run,run/{id},comparators,scenarios,run/{id}/report}`

**What it is.** A retrospective chemotype-recovery benchmark: can the pipeline's candidates recover known approved drug classes from public data? It is a **sanity check against known drug classes** — it **does not prove de novo discovery** and **does not imply clinical efficacy**.

**Comparator library.** RDKit-validated public reference structures for approved drugs across small-molecule scenarios (EGFR, BRAF, ALK, JAK2, HER2). Biologic-heavy targets (PCSK9, TNF) are marked `NOT_APPLICABLE_MODALITY_MISMATCH` — small-molecule rediscovery is not forced.

**Metrics.** Exact recovery (canonical SMILES / InChIKey), Tanimoto similarity (best, top-k, hit@k), Bemis-Murcko scaffold recovery, enrichment factor (with a sample-size warning under 10), MRR / recall@k.

**Conclusions.** STRONG_CHEMOTYPE_RECOVERY / PARTIAL_CHEMOTYPE_RECOVERY / EVIDENCE_RETRIEVAL_ONLY / NOT_APPLICABLE_MODALITY_MISMATCH / INSUFFICIENT_DATA.

**Limitations.** Retrospective recovery only; does not prove de novo discovery; does not imply clinical efficacy; comparator SMILES are public reference structures for benchmarking, not for synthesis.
