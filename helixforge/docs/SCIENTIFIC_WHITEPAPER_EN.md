# HelixForge AI — Scientific Whitepaper

## 1. Abstract
HelixForge AI is a research decision-support system that fuses literature, bioactivity, clinical-trial, and cheminformatics evidence into a traceable, source-typed workflow for early target and molecule triage. Its defining property is honesty by construction: every value is provenance-labeled and no output asserts clinical, regulatory, or wet-lab fact.

## 2. Problem statement
Early-stage discovery drowns in fragmented public evidence, and generic language models readily overclaim. The problem this system addresses is organizing that evidence while making the strength — and the limits — of every claim explicit.

## 3. Field 4 fusion rationale
The system deliberately fuses four fields — biomedical literature, bioactivity chemistry, clinical evidence, and machine reasoning — because triage quality improves when these signals are cross-checked rather than used in isolation.

## 4. System overview
A FastAPI backend orchestrates real tools, persistence, and governance. Data flows from retrieval, through grading and review, into a human-facing summary, with an audit trail at every step.
Observed: 33 recorded workflow run(s).

## 5. Multi-agent architecture
Cooperating agents (planner, retriever, critic, reviewer) each hold a narrow, auditable responsibility. The critic actively challenges weak claims and forces re-grading; no agent bypasses the safety lint.

## 6. Real tool integrations
Live integrations: PubMed/NCBI, ChEMBL/EMBL-EBI, ClinicalTrials.gov v2, TDC/PyTDC, and RDKit. Each result is tagged REAL_TOOL_OUTPUT (or RECORDED_REAL_TOOL_OUTPUT on replay). AutoDock Vina (`vina`) and REINVENT4 (`(unset)`) are integrated and health-checked but **CONFIGURED_BUT_NOT_RUN**; no docking or generative run has been executed and neither is reported as a completed real result.

## 7. Evidence and claim grading
Every claim is graded A–F by the strength of its supporting evidence, with hard ceilings so assay or computational evidence can never be presented as clinical proof. Failed citations and contradictions force downgrades.
Observed: 21 claim(s) graded; distribution {'E_UNVERIFIED': 2, 'B_MODERATE': 15, 'C_PRELIMINARY': 4}.

## 8. Target biology review
Candidate targets are reviewed for disease association, druggability signals, and known liabilities from public data — as hypotheses for expert review, not established fact.

## 9. Molecule candidate pipeline
Molecule candidates are imported from ChEMBL and validated with RDKit; invalid structures are never recommended.
Observed: 4 molecule(s) reviewed; RDKit available = True.

## 10. ChEMBL assay normalization
ChEMBL activities are normalized (units, activity types, pChEMBL) so that measured potency is comparable and clearly separated from computed estimates.

## 11. Medicinal chemistry review
A medicinal-chemistry review flags property and structural-alert concerns (druglikeness, PAINS-style filters). It performs no synthesis planning and gives no dosing guidance.

## 12. Applicability domain
The applicability domain is enforced and surfaced: reliability is highest for well-studied targets with abundant data and degrades for sparse or novel targets; out-of-domain inputs are flagged for expert review.

## 13. ADMET validation protocol
ADMET signals come from public datasets and models and are labeled as model output (BASELINE_MODEL_OUTPUT / HEURISTIC_ANALYSIS), never as a safety determination.

## 14. Docking governance
Docking is governed rather than assumed: AutoDock Vina is CONFIGURED_BUT_NOT_RUN, so no docking scores are presented as real results in this deployment.

## 15. Multi-objective optimization
Candidate ranking uses transparent multi-objective (Pareto) trade-offs across validity, druglikeness, novelty, and evidence — with weights disclosed, not hidden.

## 16. Clinical precedent review
ClinicalTrials.gov precedent indicates prior interest in a target or modality; it is precedent, not proof of efficacy, and is graded accordingly.
Observed clinical-precedent status: reviewed.

## 17. Translational readiness
Translational readiness is reported on a capped scale (never above TRL_4_READY_FOR_EXPERIMENTAL_PLANNING) so the system can never imply wet-lab or clinical success.
Observed readiness: TRL_4_READY_FOR_EXPERIMENTAL_PLANNING.

## 18. Safety and ethics controls
Safety and ethics controls include a safety lint that blocks forbidden categories (synthesis routes, reagents, dosing, hazardous content), overclaim detection, and SAFETY_REDACTED labeling. These guardrails cannot be bypassed by any agent.

## 19. Evaluation protocol
Evaluation is descriptive and offline-safe: retrospective rediscovery, citation integrity, molecule validity, self-correction counts, and governance audits. Samples are small and support qualitative confidence only.
Observed governance status: BLOCKED.

## 20. Record/replay reproducibility
A record/replay layer captures real tool outputs as timestamped snapshots (metadata only where applicable) for reproducible, offline demonstration; replayed data is labeled RECORDED_REAL_TOOL_OUTPUT and never relabeled as live.

## 21. Limitations
Limitations. No clinical validation and no regulatory approval is claimed; the system is not a medical device. Computational and assay signals are not experimental proof and are not proof of efficacy. Small evaluation samples preclude statistical-significance claims. Coverage depends on upstream public databases. Configured-but-not-run tools contribute no results.

## 22. Roadmap
Roadmap. Broaden target/disease coverage, expand the rediscovery benchmark, and — only under explicit human control and appropriate safety review — enable the currently-not-run docking and generative tools.

## 23. Appendices
Appendices. Companion governance artifacts (system/model/data cards, risk register, traceability matrix, validation protocol, and the what-we-do-not-claim sheet) accompany this whitepaper.

## 24. Source-type legend
`REAL_TOOL_OUTPUT · RECORDED_REAL_TOOL_OUTPUT · CONFIGURED_BUT_NOT_RUN · TOOL_ERROR · HEURISTIC_ANALYSIS · ASSUMPTION · BASELINE_MODEL_OUTPUT · SAFETY_REDACTED · HUMAN_INPUT`

Every surfaced value carries exactly one of these labels; HEURISTIC_ANALYSIS marks rule-based synthesis and CONFIGURED_BUT_NOT_RUN marks integrated-but-unexecuted tools.

## 25. Human responsibility statement
> This system is research decision support only. It does not replace expert scientific, clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human research team.

> 본 시스템은 연구 의사결정 보조 도구이며 전문가 검토를 대체하지 않습니다. 최종 판단과 책임은 연구자에게 있습니다.
