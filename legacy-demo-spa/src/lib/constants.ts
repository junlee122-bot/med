import type { AgentDef, StageMeta, WorkflowStage, ToolDef } from '@/types'

// ============================================================================
// Workflow stages (Section 8 state machine)
// ============================================================================
export const STAGES: StageMeta[] = [
  { id: 'IDLE', label: 'Idle', labelKo: '대기', agents: [], short: 'Waiting to start' },
  { id: 'PROJECT_CREATED', label: 'Project Created', labelKo: '프로젝트 생성', agents: ['Project Orchestrator'], short: 'Project initialized' },
  { id: 'PLANNING', label: 'Planning', labelKo: '계획 수립', agents: ['Project Orchestrator'], short: 'Decompose goal into a task DAG' },
  { id: 'EVIDENCE_MINING', label: 'Evidence Mining', labelKo: '근거 마이닝', agents: ['Evidence Miner'], short: 'Search literature & public sources' },
  { id: 'DISEASE_MODELING', label: 'Disease Modeling', labelKo: '질환 모델링', agents: ['Disease Biology Agent'], short: 'Frame disease biology & unmet need' },
  { id: 'TARGET_RANKING', label: 'Target Ranking', labelKo: '타깃 우선순위', agents: ['Target Scout'], short: 'Rank target opportunities' },
  { id: 'HYPOTHESIS_GENERATION', label: 'Hypothesis Generation', labelKo: '가설 생성', agents: ['Hypothesis Generator'], short: 'Generate testable hypotheses' },
  { id: 'MOLECULE_GENERATION', label: 'Molecule Generation', labelKo: '분자 생성', agents: ['Molecular Design Agent'], short: 'Generate / import candidates' },
  { id: 'STRUCTURE_VALIDATION', label: 'Structure Validation', labelKo: '구조 검증', agents: ['Cheminformatics Validator'], short: 'Validate SMILES & descriptors' },
  { id: 'DOCKING_OR_BINDING_ESTIMATION', label: 'Binding Estimation', labelKo: '결합 추정', agents: ['Binding & Structure Agent'], short: 'Estimate binding & pose' },
  { id: 'ADMET_SCREENING', label: 'ADMET Screening', labelKo: 'ADMET 스크리닝', agents: ['ADMET & Toxicology Agent'], short: 'Predict PK/tox risk' },
  { id: 'SYNTHESIS_FEASIBILITY', label: 'Synthesis Feasibility', labelKo: '합성 가능성', agents: ['Synthesis Feasibility Agent'], short: 'Feasibility summary only' },
  { id: 'SAFETY_AUDIT', label: 'Safety Audit', labelKo: '안전성 감사', agents: ['Safety Auditor'], short: 'Screen for hazards & dual-use' },
  { id: 'CRITIC_REVIEW', label: 'Critic Review', labelKo: '비평 검토', agents: ['Critic / Verifier Agent'], short: 'Challenge every output' },
  { id: 'REVISION_LOOP', label: 'Revision Loop', labelKo: '수정 루프', agents: ['Critic / Verifier Agent'], short: 'Loop back & revise' },
  { id: 'CLINICAL_STRATEGY', label: 'Clinical Strategy', labelKo: '임상 전략', agents: ['Clinical Strategy Agent'], short: 'High-level clinical plan' },
  { id: 'REGULATORY_REVIEW', label: 'Regulatory Review', labelKo: '규제 검토', agents: ['Regulatory Reviewer'], short: 'FDA/MFDS checklist alignment' },
  { id: 'EVALUATION', label: 'Evaluation', labelKo: '평가', agents: ['Evaluation Harness Agent'], short: 'Compute benchmark metrics' },
  { id: 'REPORT_GENERATION', label: 'Report Generation', labelKo: '보고서 생성', agents: ['Report Builder'], short: 'Assemble final report' },
  { id: 'COMPLETE', label: 'Complete', labelKo: '완료', agents: [], short: 'Workflow finished' },
  { id: 'BLOCKED', label: 'Blocked', labelKo: '차단됨', agents: ['Safety Auditor'], short: 'Blocked by safety gate' },
  { id: 'ERROR', label: 'Error', labelKo: '오류', agents: [], short: 'Unrecoverable error' },
]

export const STAGE_MAP: Record<WorkflowStage, StageMeta> = STAGES.reduce(
  (acc, s) => ({ ...acc, [s.id]: s }),
  {} as Record<WorkflowStage, StageMeta>,
)

// Linear pipeline order used by the workflow engine and DAG.
export const PIPELINE_STAGES: WorkflowStage[] = [
  'PLANNING',
  'EVIDENCE_MINING',
  'DISEASE_MODELING',
  'TARGET_RANKING',
  'HYPOTHESIS_GENERATION',
  'MOLECULE_GENERATION',
  'STRUCTURE_VALIDATION',
  'DOCKING_OR_BINDING_ESTIMATION',
  'ADMET_SCREENING',
  'SYNTHESIS_FEASIBILITY',
  'SAFETY_AUDIT',
  'CRITIC_REVIEW',
  'CLINICAL_STRATEGY',
  'REGULATORY_REVIEW',
  'EVALUATION',
  'REPORT_GENERATION',
]

// ============================================================================
// Agents (Section 7)
// ============================================================================
export const AGENTS: AgentDef[] = [
  { name: 'Project Orchestrator', role: 'Decomposes the goal into a DAG, assigns tasks, tracks state, decides when to revise.', roleKo: '목표를 DAG로 분해하고 작업을 배정하며 상태를 추적합니다.', tools: ['Planner'], color: '#22d3ee', icon: 'Network' },
  { name: 'Disease Biology Agent', role: 'Frames disease biology, unmet need, pathways, phenotypes, biomarkers.', roleKo: '질환 생물학과 미충족 수요, 경로/바이오마커를 정의합니다.', tools: ['Literature', 'KnowledgeGraph', 'Pathway'], color: '#3b82f6', icon: 'Dna' },
  { name: 'Evidence Miner', role: 'Searches literature and public sources; separates supporting & contradictory evidence.', roleKo: '문헌·공공 소스를 검색하고 지지/반박 근거를 분류합니다.', tools: ['PubMed', 'EuropePMC', 'SemanticScholar', 'CrossRef'], color: '#8b5cf6', icon: 'BookOpen' },
  { name: 'Target Scout', role: 'Ranks targets by relevance, tractability, novelty, safety, clinical precedent.', roleKo: '타깃을 관련성·개발가능성·신규성·안전성 등으로 순위화합니다.', tools: ['OpenTargets', 'ChEMBL', 'UniProt', 'KnowledgeGraph'], color: '#22d3ee', icon: 'Crosshair' },
  { name: 'Hypothesis Generator', role: 'Converts evidence into testable high-level therapeutic hypotheses.', roleKo: '근거를 검증 가능한 고수준 치료 가설로 변환합니다.', tools: ['Reasoner'], color: '#0ea5e9', icon: 'Lightbulb' },
  { name: 'Molecular Design Agent', role: 'Generates or imports candidate molecules under constraints.', roleKo: '제약 조건 하에서 후보 분자를 생성/도입합니다.', tools: ['REINVENT4', 'PubChem', 'ChEMBL'], color: '#16b884', icon: 'Atom' },
  { name: 'Cheminformatics Validator', role: 'Validates molecular structure and computes descriptors.', roleKo: '분자 구조를 검증하고 디스크립터를 계산합니다.', tools: ['RDKit'], color: '#10b981', icon: 'FlaskConical' },
  { name: 'Binding & Structure Agent', role: 'Estimates target binding and structural plausibility.', roleKo: '타깃 결합과 구조적 타당성을 추정합니다.', tools: ['PDB', 'AlphaFold', 'AutoDockVina', 'DiffDock', 'Boltz'], color: '#6366f1', icon: 'Magnet' },
  { name: 'ADMET & Toxicology Agent', role: 'Predicts pharmacokinetic and toxicity risks.', roleKo: '약동학 및 독성 위험을 예측합니다.', tools: ['TDC', 'ChemProp'], color: '#f59e0b', icon: 'Activity' },
  { name: 'Synthesis Feasibility Agent', role: 'Estimates synthetic feasibility (score only, no routes).', roleKo: '합성 가능성을 점수로만 추정합니다(경로 미표시).', tools: ['AiZynthFinder', 'ASKCOS'], color: '#eab308', icon: 'Wrench' },
  { name: 'Safety Auditor', role: 'Screens outputs for hazard, dual-use, controlled chemicals, fake citations.', roleKo: '위험·이중용도·규제물질·허위 인용을 심사합니다.', tools: ['SafetyScreen', 'DualUseClassifier'], color: '#ef4444', icon: 'ShieldAlert' },
  { name: 'Clinical Strategy Agent', role: 'Produces a high-level clinical development plan.', roleKo: '고수준 임상 개발 계획을 수립합니다.', tools: ['ClinicalTrials', 'Precedent'], color: '#ec4899', icon: 'Stethoscope' },
  { name: 'Regulatory Reviewer', role: 'Checks alignment with FDA/MFDS-style guidance via RAG.', roleKo: 'RAG로 FDA/MFDS 가이던스 정합성을 점검합니다.', tools: ['RegulatoryRAG'], color: '#f472b6', icon: 'Scale' },
  { name: 'Business & Impact Analyst', role: 'Estimates time/cost reduction and industry value.', roleKo: '시간/비용 절감과 산업적 가치를 추정합니다.', tools: ['Model'], color: '#14b8a6', icon: 'TrendingUp' },
  { name: 'Evaluation Harness Agent', role: 'Runs benchmark logic and reproducibility package.', roleKo: '벤치마크 로직과 재현 패키지를 실행합니다.', tools: ['EvalHarness'], color: '#a3e635', icon: 'Gauge' },
  { name: 'Critic / Verifier Agent', role: 'Challenges every output; forces revision loops.', roleKo: '모든 출력을 검증하고 수정 루프를 유도합니다.', tools: ['Verifier'], color: '#fb923c', icon: 'SearchCheck' },
  { name: 'Report Builder', role: 'Assembles final reports linking every claim to evidence.', roleKo: '모든 주장을 근거와 연결하여 최종 보고서를 생성합니다.', tools: ['Reporter'], color: '#94a3b8', icon: 'FileText' },
]

export const AGENT_MAP: Record<string, AgentDef> = AGENTS.reduce(
  (acc, a) => ({ ...acc, [a.name]: a }),
  {},
)

// ============================================================================
// Tool Registry (Section 12 / 20)
// ============================================================================
export const TOOL_DEFS: ToolDef[] = [
  // A. Literature & citation
  { id: 'pubmed', name: 'PubMed Adapter', category: 'literature', categoryLabel: 'Literature & Citation', purpose: 'E-utilities search over biomedical literature.', status: 'demo_fallback', mode: 'demo', requiredConfig: ['NCBI_API_KEY (optional)'], exampleOutput: '{ pmid, title, authors, year, abstractSnippet }', safetyNotes: 'Read-only public metadata. No full-text redistribution.' },
  { id: 'europepmc', name: 'Europe PMC Adapter', category: 'literature', categoryLabel: 'Literature & Citation', purpose: 'Open literature + preprint search.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ id, source, title, doi }', safetyNotes: 'Read-only.' },
  { id: 'semanticscholar', name: 'Semantic Scholar Adapter', category: 'literature', categoryLabel: 'Literature & Citation', purpose: 'Citation graph & TLDR retrieval.', status: 'missing_key', mode: 'demo', requiredConfig: ['S2_API_KEY'], exampleOutput: '{ paperId, title, citationCount, tldr }', safetyNotes: 'Read-only.' },
  { id: 'crossref', name: 'CrossRef Adapter', category: 'literature', categoryLabel: 'Literature & Citation', purpose: 'DOI resolution & metadata.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ doi, title, container, verified }', safetyNotes: 'Read-only.' },
  { id: 'citationverifier', name: 'Citation Verifier', category: 'literature', categoryLabel: 'Literature & Citation', purpose: 'Cross-checks identifiers, marks verified/failed/demo.', status: 'local_only', mode: 'demo', requiredConfig: [], exampleOutput: '{ status: verified|failed|demo, identifier, confidence }', safetyNotes: 'Blocks fabricated references from entering reports.' },

  // B. Target & biology
  { id: 'opentargets', name: 'Open Targets Adapter', category: 'biology', categoryLabel: 'Target & Biology', purpose: 'Disease-target association evidence.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ target, disease, associationScore, datatypes }', safetyNotes: 'Read-only public data.' },
  { id: 'uniprot', name: 'UniProt Adapter', category: 'biology', categoryLabel: 'Target & Biology', purpose: 'Protein function & sequence metadata.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ accession, gene, function, length }', safetyNotes: 'Read-only.' },
  { id: 'chembl_target', name: 'ChEMBL Target Adapter', category: 'biology', categoryLabel: 'Target & Biology', purpose: 'Bioactivity & tractability signal.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ targetChemblId, tractability, actives }', safetyNotes: 'Read-only.' },
  { id: 'kg', name: 'Knowledge Graph Adapter', category: 'biology', categoryLabel: 'Target & Biology', purpose: 'Disease→pathway→target→biomarker graph.', status: 'local_only', mode: 'demo', requiredConfig: ['GRAPH_ENDPOINT (optional)'], exampleOutput: '{ nodes[], edges[], confidence }', safetyNotes: 'Provenance retained per edge.' },

  // C. Chemistry
  { id: 'rdkit', name: 'RDKit Adapter', category: 'chemistry', categoryLabel: 'Chemistry', purpose: 'SMILES parsing, descriptors, QED, Lipinski.', status: 'local_only', mode: 'demo', requiredConfig: ['python worker (optional)'], exampleOutput: '{ valid, mw, logP, tpsa, qed, lipinski }', safetyNotes: 'Structure validation only. No synthesis output.' },
  { id: 'reinvent', name: 'REINVENT4 Adapter', category: 'chemistry', categoryLabel: 'Chemistry', purpose: 'Target-conditioned molecular generation (RL/TL).', status: 'missing_key', mode: 'demo', requiredConfig: ['REINVENT_ENDPOINT', 'checkpoint'], exampleOutput: '{ candidates[], validity, novelty, diversity }', safetyNotes: 'Generation constrained by safety scoring; hazardous space excluded.' },
  { id: 'chemprop', name: 'ChemProp Adapter', category: 'chemistry', categoryLabel: 'Chemistry', purpose: 'Message-passing ADMET/property models.', status: 'missing_key', mode: 'demo', requiredConfig: ['MODEL_DIR'], exampleOutput: '{ endpoint, prediction, uncertainty }', safetyNotes: 'Predictive only.' },
  { id: 'tdc', name: 'TDC Benchmark Adapter', category: 'chemistry', categoryLabel: 'Chemistry', purpose: 'Therapeutics Data Commons benchmark tasks.', status: 'local_only', mode: 'demo', requiredConfig: ['pytdc (optional)'], exampleOutput: '{ task, split, metric, value }', safetyNotes: 'Public benchmark.' },
  { id: 'pubchem', name: 'PubChem Adapter', category: 'chemistry', categoryLabel: 'Chemistry', purpose: 'Compound lookup & known comparator retrieval.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ cid, canonicalSmiles, name }', safetyNotes: 'Read-only.' },
  { id: 'chembl_mol', name: 'ChEMBL Molecule Adapter', category: 'chemistry', categoryLabel: 'Chemistry', purpose: 'Known bioactive comparators.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ molChemblId, smiles, maxPhase }', safetyNotes: 'Read-only.' },

  // D. Structure & docking
  { id: 'pdb', name: 'PDB Adapter', category: 'structure', categoryLabel: 'Structure & Docking', purpose: 'Experimental protein structures.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ pdbId, resolution, chains }', safetyNotes: 'Read-only.' },
  { id: 'alphafold', name: 'AlphaFold DB Adapter', category: 'structure', categoryLabel: 'Structure & Docking', purpose: 'Predicted structures & pLDDT.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ uniprot, meanPlddt, modelUrl }', safetyNotes: 'Read-only.' },
  { id: 'boltz', name: 'Boltz / ESMFold Adapter', category: 'structure', categoryLabel: 'Structure & Docking', purpose: 'Complex/structure prediction.', status: 'missing_key', mode: 'demo', requiredConfig: ['GPU worker'], exampleOutput: '{ plddt, complexConfidence }', safetyNotes: 'Predictive only.' },
  { id: 'vina', name: 'AutoDock Vina Adapter', category: 'structure', categoryLabel: 'Structure & Docking', purpose: 'Physics-based docking score.', status: 'missing_key', mode: 'demo', requiredConfig: ['docking worker', 'receptor'], exampleOutput: '{ affinity_kcal_mol, poseConfidence }', safetyNotes: 'In-silico estimate; not experimental affinity.' },
  { id: 'diffdock', name: 'DiffDock Adapter', category: 'structure', categoryLabel: 'Structure & Docking', purpose: 'Diffusion-based pose generation.', status: 'missing_key', mode: 'demo', requiredConfig: ['GPU worker'], exampleOutput: '{ poses[], confidence }', safetyNotes: 'In-silico estimate.' },

  // E. Synthesis feasibility
  { id: 'aizynth', name: 'AiZynthFinder Adapter', category: 'synthesis', categoryLabel: 'Synthesis Feasibility', purpose: 'Retrosynthetic feasibility SCORE only.', status: 'missing_key', mode: 'demo', requiredConfig: ['model + stock'], exampleOutput: '{ feasibility, complexity, confidence }', safetyNotes: 'POLICY: no step-by-step routes, reagents, or conditions are exposed.' },
  { id: 'askcos', name: 'ASKCOS Adapter', category: 'synthesis', categoryLabel: 'Synthesis Feasibility', purpose: 'Route feasibility signal only.', status: 'missing_key', mode: 'demo', requiredConfig: ['ASKCOS_ENDPOINT'], exampleOutput: '{ feasibilityScore, expertReviewRequired }', safetyNotes: 'POLICY: procedural detail is intentionally withheld.' },

  // F. Clinical / regulatory
  { id: 'clinicaltrials', name: 'ClinicalTrials.gov Adapter', category: 'clinical', categoryLabel: 'Clinical & Regulatory', purpose: 'Trial precedent & risk summary.', status: 'demo_fallback', mode: 'demo', requiredConfig: [], exampleOutput: '{ nctId, phase, status, outcome }', safetyNotes: 'Read-only public registry.' },
  { id: 'fdarag', name: 'FDA Guidance RAG Adapter', category: 'clinical', categoryLabel: 'Clinical & Regulatory', purpose: 'Retrieval over FDA guidance corpus.', status: 'missing_key', mode: 'demo', requiredConfig: ['VECTOR_DB', 'corpus'], exampleOutput: '{ checklist[], gaps[], sourceIds[] }', safetyNotes: 'High-level checklist; not regulatory advice.' },
  { id: 'mfdsrag', name: 'MFDS Guidance RAG Adapter', category: 'clinical', categoryLabel: 'Clinical & Regulatory', purpose: 'Retrieval over MFDS (KR) guidance.', status: 'missing_key', mode: 'demo', requiredConfig: ['VECTOR_DB', 'corpus'], exampleOutput: '{ checklist[], gaps[], sourceIds[] }', safetyNotes: 'High-level checklist; not regulatory advice.' },
  { id: 'protocolchecklist', name: 'Protocol Checklist Adapter', category: 'clinical', categoryLabel: 'Clinical & Regulatory', purpose: 'Structured protocol completeness check.', status: 'local_only', mode: 'demo', requiredConfig: [], exampleOutput: '{ item, status, riskLevel }', safetyNotes: 'Planning aid only.' },

  // G. Safety
  { id: 'controlledscreen', name: 'Controlled Chemical Screening Adapter', category: 'safety', categoryLabel: 'Safety', purpose: 'Screens for controlled/hazardous structures.', status: 'local_only', mode: 'demo', requiredConfig: [], exampleOutput: '{ flagged, category, redactedSummary }', safetyNotes: 'Blocks controlled/explosive/highly toxic classes.' },
  { id: 'toxendpoint', name: 'Toxicity Endpoint Adapter', category: 'safety', categoryLabel: 'Safety', purpose: 'hERG/Ames/DILI risk aggregation.', status: 'local_only', mode: 'demo', requiredConfig: [], exampleOutput: '{ hERG, Ames, DILI, gate }', safetyNotes: 'Risk screening; never optimizes toxicity.' },
  { id: 'dualuse', name: 'Dual-Use Safety Classifier', category: 'safety', categoryLabel: 'Safety', purpose: 'Flags dual-use / weaponization intent.', status: 'local_only', mode: 'demo', requiredConfig: [], exampleOutput: '{ status, category, action }', safetyNotes: 'Blocks weaponization & harmful-enhancement requests.' },
  { id: 'promptauditor', name: 'Prompt/Output Safety Auditor', category: 'safety', categoryLabel: 'Safety', purpose: 'Logs prompts/settings; audits outputs.', status: 'local_only', mode: 'demo', requiredConfig: [], exampleOutput: '{ logged, violations[], auditComplete }', safetyNotes: 'Ensures audit completeness & no hidden CoT exposure.' },
]

export const TOOL_CATEGORIES = [
  { id: 'literature', label: 'Literature & Citation' },
  { id: 'biology', label: 'Target & Biology' },
  { id: 'chemistry', label: 'Chemistry' },
  { id: 'structure', label: 'Structure & Docking' },
  { id: 'synthesis', label: 'Synthesis Feasibility' },
  { id: 'clinical', label: 'Clinical & Regulatory' },
  { id: 'safety', label: 'Safety' },
]

// Global disclaimers reused across reports and pages (Section 3C / 23)
export const HUMAN_RESPONSIBILITY_STATEMENT =
  'This system is research decision support only. It does not replace expert scientific, clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human research team.'

export const DEMO_LABEL = 'Demo Simulation — not a real database/tool result.'

export const CLINICAL_DISCLAIMER =
  'This draft is a high-level research planning artifact. It is not clinical, medical, legal, or regulatory advice.'

export const NO_SYNTHESIS_NOTICE =
  'Synthesis feasibility is summarized only. Actionable synthesis routes are intentionally not displayed by policy.'

export const SAFETY_POLICY_VERSION = 'HF-SAFE-v1.3'
