# Evaluation Bench

All metrics are computed from **observed pipeline state** (`services/evaluation.py`)
and persisted as `evaluation_results`. Nothing is fabricated. Endpoints:
`GET /api/evaluation/summary`, `GET /api/evaluation/runs/{run_id}`,
`POST /api/evaluation/run-retrospective`.

## Modules

**A. Real Tool Integration** — real_tool_output_count, configured_not_run_count,
tool_error_count, tool_success_rate, source_labeling_completeness.

**B. Evidence Integrity** — evidence_count, verified/failed citation counts,
citation_verification_rate, fake_citation_catch_rate,
evidence_to_hypothesis_coverage.

**C. Molecule Validity** — candidate_count, valid/invalid SMILES counts,
molecule_validity_rate, safety pass/review/blocked counts.

**D. Agent Autonomy** — agent_run_count, revision_event_count,
self_correction_rate, human_intervention_count.

**E. Resource Efficiency** — runtime_seconds, http_api_calls, local_tool_calls,
estimated_api_calls, cost_class (no LLM tokens billed).

**F. Retrospective Rediscovery (EGFR/NSCLC)** — a pipeline-sanity + evidence-
retrieval benchmark (NOT a wet-lab validation). Criteria:

1. `target_ranks_top` — a druggable single human protein from the queried family
   is selected (ChEMBL descriptive names rarely contain the gene symbol, so we
   check target type + organism rather than a substring).
2. `pubmed_evidence_exists` — ≥1 real PubMed record.
3. `clinical_precedent_exists` — ≥1 real ClinicalTrials.gov trial.
4. `valid_molecule_exists` — ≥1 RDKit-valid candidate from ChEMBL activities.
5. `report_generated`.

A clean EGFR run scores 5/5 with EGFR (CHEMBL203) selected and 6/6 valid
molecules.

## Interpretation notes

- ADMET metrics: the TDC dataset is loaded as an **evaluation/training
  substrate** (real splits + size). Per-candidate ADMET numbers are **not**
  claimed unless a trained model is wired in.
- Docking/REINVENT metrics reflect honest tool status
  (`CONFIGURED_BUT_NOT_RUN` until those engines are installed).
- Self-correction, citation-verification, molecule-validity, and safety-block
  metrics reflect **actual in-app behavior** of the agentic loop.
