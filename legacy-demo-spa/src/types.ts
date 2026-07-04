// ============================================================================
// HelixForge AI — Core Type System
// Every entity in the platform data model. These types are the shared contract
// used by the store, adapters, workflow engine, scoring, safety, and all pages.
// ============================================================================

export type Language = 'ko' | 'en'
export type Theme = 'dark' | 'light'
export type AppMode = 'demo' | 'real'

// ---- Labeling / provenance ----
// Section 5 requirement: every scientific output is labeled by source.
export type SourceType = 'real' | 'demo' | 'human' | 'fallback'
export type VerificationStatus = 'verified' | 'unverified' | 'demo' | 'failed'
export type ValidationStatus = 'pending' | 'passed' | 'failed' | 'warning' | 'skipped'

// ---- Safety ----
export type SafetyStatus = 'PASS' | 'REVIEW_REQUIRED' | 'BLOCKED' | 'DEMO_ONLY' | 'TOOL_ERROR'
export type SafetySeverity = 'info' | 'low' | 'medium' | 'high' | 'critical'

// ---- Tool status ----
export type ToolConnectionStatus =
  | 'connected'
  | 'missing_key'
  | 'local_only'
  | 'demo_fallback'
  | 'error'
export type RunStatus =
  | 'idle'
  | 'queued'
  | 'running'
  | 'success'
  | 'error'
  | 'blocked'
  | 'revised'
  | 'skipped'

// ============================================================================
// Workflow state machine
// ============================================================================
export type WorkflowStage =
  | 'IDLE'
  | 'PROJECT_CREATED'
  | 'PLANNING'
  | 'EVIDENCE_MINING'
  | 'DISEASE_MODELING'
  | 'TARGET_RANKING'
  | 'HYPOTHESIS_GENERATION'
  | 'MOLECULE_GENERATION'
  | 'STRUCTURE_VALIDATION'
  | 'DOCKING_OR_BINDING_ESTIMATION'
  | 'ADMET_SCREENING'
  | 'SYNTHESIS_FEASIBILITY'
  | 'SAFETY_AUDIT'
  | 'CRITIC_REVIEW'
  | 'REVISION_LOOP'
  | 'CLINICAL_STRATEGY'
  | 'REGULATORY_REVIEW'
  | 'EVALUATION'
  | 'REPORT_GENERATION'
  | 'COMPLETE'
  | 'BLOCKED'
  | 'ERROR'

export interface StageMeta {
  id: WorkflowStage
  label: string
  labelKo: string
  agents: string[]
  short: string
}

// ============================================================================
// Agents
// ============================================================================
export type AgentName =
  | 'Project Orchestrator'
  | 'Disease Biology Agent'
  | 'Evidence Miner'
  | 'Target Scout'
  | 'Hypothesis Generator'
  | 'Molecular Design Agent'
  | 'Cheminformatics Validator'
  | 'Binding & Structure Agent'
  | 'ADMET & Toxicology Agent'
  | 'Synthesis Feasibility Agent'
  | 'Safety Auditor'
  | 'Clinical Strategy Agent'
  | 'Regulatory Reviewer'
  | 'Business & Impact Analyst'
  | 'Evaluation Harness Agent'
  | 'Critic / Verifier Agent'
  | 'Report Builder'

export interface AgentDef {
  name: AgentName
  role: string
  roleKo: string
  tools: string[]
  color: string
  icon: string
}

// ============================================================================
// Settings
// ============================================================================
export interface UserSettings {
  id: string
  language: Language
  theme: Theme
  mode: AppMode
  modelName: string
  effortLevel: 'low' | 'medium' | 'high' | 'max'
  temperature: number
  maxOutput: number
  fallbackModel: string
  safetyPolicyVersion: string
  apiKeyStatus: Record<string, ToolConnectionStatus>
  fastDemo: boolean
  createdAt: string
  updatedAt: string
}

// ============================================================================
// Project
// ============================================================================
export type DiscoveryGoal =
  | 'target_discovery'
  | 'repurposing'
  | 'de_novo'
  | 'optimization'
  | 'clinical_strategy'
  | 'full_pipeline'

export type Modality = 'small_molecule' | 'biologic' | 'repurposing' | 'any'
export type ProjectStatus = 'draft' | 'ready' | 'running' | 'complete' | 'blocked' | 'error'

export interface ScientificConstraints {
  knownTargets: string[]
  excludedTargets: string[]
  mechanismPreferences: string[]
  biomarkerRequirements: string[]
  modality: Modality
}

export interface SafetyConstraints {
  excludeControlled: boolean
  excludeHighToxicityOptimization: boolean
  noSynthesisRecipe: boolean
  humanReviewRequired: boolean
}

export interface EvaluationPlan {
  retrospectiveRediscovery: boolean
  tdcAdmet: boolean
  dockingEnrichment: boolean
  citationVerification: boolean
  selfCorrection: boolean
  costLatency: boolean
}

export interface Project {
  id: string
  name: string
  disease: string
  indication: string
  patientPopulation: string
  unmetNeed: string
  discoveryGoal: DiscoveryGoal
  mode: AppMode
  status: ProjectStatus
  scientificConstraints: ScientificConstraints
  safetyConstraints: SafetyConstraints
  evaluationPlan: EvaluationPlan
  createdAt: string
  updatedAt: string
  owner: string
  currentWorkflowId?: string
  summary: string
  humanResponsibilityAccepted: boolean
  seeded?: boolean
}

// ============================================================================
// Workflow run + audit trail
// ============================================================================
export interface WorkflowRun {
  id: string
  projectId: string
  mode: AppMode
  status: RunStatus
  currentStage: WorkflowStage
  startedAt?: string
  completedAt?: string
  totalEstimatedCost: number
  totalEstimatedTokens: number
  toolRunCount: number
  safetyStatus: SafetyStatus
  confidence: number
  errorCount: number
  revisionCount: number
}

export interface AgentRun {
  id: string
  workflowId: string
  agentName: AgentName
  stage: WorkflowStage
  status: RunStatus
  inputSummary: string
  outputSummary: string
  confidence: number
  startedAt: string
  completedAt?: string
  validationStatus: ValidationStatus
  evidenceIds: string[]
  toolRunIds: string[]
  warnings: string[]
  revisionOf?: string
  isRevision?: boolean
}

export interface ToolRun {
  id: string
  workflowId: string
  agentRunId: string
  toolName: string
  toolCategory: string
  mode: AppMode
  status: RunStatus
  inputSummary: string
  outputSummary: string
  rawOutputRef?: string
  error?: string
  startedAt: string
  completedAt?: string
  latencyMs: number
  costEstimate: number
  sourceType: SourceType
  validationStatus: ValidationStatus
}

export type AuditEventType =
  | 'plan'
  | 'agent'
  | 'tool'
  | 'validation'
  | 'revision'
  | 'safety'
  | 'error'
  | 'stage'
  | 'report'

export interface AuditEvent {
  id: string
  workflowId: string
  ts: string
  type: AuditEventType
  stage: WorkflowStage
  agent?: AgentName
  tool?: string
  title: string
  detail: string
  sourceType?: SourceType
  validationStatus?: ValidationStatus
  safetyStatus?: SafetyStatus
  confidence?: number
  evidenceIds?: string[]
}

// ============================================================================
// Evidence
// ============================================================================
export type EvidenceDirection = 'supports' | 'contradicts' | 'neutral'

export interface EvidenceItem {
  id: string
  projectId: string
  sourceName: string
  sourceType: SourceType
  title: string
  authors: string
  year: number
  identifierType: 'PMID' | 'DOI' | 'URL' | 'DEMO' | 'ClinicalTrials' | 'OpenTargets'
  identifier: string
  url?: string
  claim: string
  evidenceDirection: EvidenceDirection
  confidence: number
  verificationStatus: VerificationStatus
  retrievedAt: string
  notes?: string
  relatedTarget?: string
}

// ============================================================================
// Targets & hypotheses
// ============================================================================
export interface TargetCandidate {
  id: string
  projectId: string
  symbol: string
  name: string
  diseaseRelevance: number // 0-1
  tractability: number
  novelty: number
  safetyConcern: number // 0-1, higher = worse
  biomarkerAvailability: number
  clinicalPrecedent: number
  evidenceCount: number
  evidenceConfidence: number
  confidence: number
  score: number // computed opportunity score 0-100
  rank: number
  rationale: string
  moleculeStrategy: string
  nextActions: string[]
  status: 'ranked' | 'selected' | 'exploratory' | 'deprioritized'
  evidenceIds: string[]
}

export interface Hypothesis {
  id: string
  projectId: string
  targetId: string
  targetSymbol: string
  statement: string
  mechanismSummary: string
  testability: number
  evidenceIds: string[]
  confidence: number
  limitations: string
  status: 'draft' | 'verified' | 'revised' | 'rejected'
  validationPlan: string
}

// ============================================================================
// Molecules
// ============================================================================
export interface MoleculeDescriptors {
  mw: number
  logP: number
  hbd: number
  hba: number
  tpsa: number
  rotatableBonds: number
  aromaticRings: number
}

export type Recommendation =
  | 'advance'
  | 'optimize'
  | 'hold'
  | 'quarantined'
  | 'reject'

export interface MoleculeCandidate {
  id: string
  projectId: string
  targetId: string
  label: string
  smiles: string
  source: 'generated' | 'imported' | 'known_comparator' | 'demo'
  sourceType: SourceType
  validityStatus: 'valid' | 'invalid' | 'pending'
  validityReason?: string
  descriptors: MoleculeDescriptors
  bindingScore: number // kcal/mol style, more negative = better
  bindingNormalized: number // 0-1
  poseConfidence: number
  dockingFailed?: boolean
  admetScore: number // 0-1
  qed: number
  lipinskiPass: boolean
  lipinskiViolations: number
  saScore: number // 1(easy)-10(hard)
  hERG: number // 0-1 risk
  Ames: number
  DILI: number
  cyp: number
  bbb: number
  solubility: number
  clearance: number
  bioavailability: number
  novelty: number
  ipDistance: number
  uncertainty: number
  synthesisFeasibility: 'High' | 'Medium' | 'Low'
  routeConfidence: number
  estimatedComplexity: number
  requiresExpertReview: boolean
  safetyStatus: SafetyStatus
  compositeScore: number // 0-100
  recommendation: Recommendation
  evidenceIds: string[]
  criticComments: string[]
  optimizationHistory: OptimizationStep[]
  createdAt: string
}

export interface OptimizationStep {
  iteration: number
  action: string
  compositeScoreBefore: number
  compositeScoreAfter: number
  note: string
}

// ============================================================================
// Safety
// ============================================================================
export interface SafetyFlag {
  id: string
  projectId: string
  entityType: 'molecule' | 'evidence' | 'text' | 'hypothesis'
  entityId: string
  entityLabel: string
  severity: SafetySeverity
  category: string
  status: SafetyStatus
  redactedSummary: string
  safeAlternative: string
  createdAt: string
  resolvedAt?: string
}

export interface SafetyPolicyCheck {
  id: string
  name: string
  nameKo: string
  description: string
  status: SafetyStatus
  detail: string
}

// ============================================================================
// Clinical & regulatory
// ============================================================================
export interface ClinicalProtocolDraft {
  id: string
  projectId: string
  candidateId: string
  candidateLabel: string
  indication: string
  targetProductProfile: string
  phase: string
  population: string
  endpoints: { name: string; type: 'primary' | 'secondary'; description: string }[]
  inclusionLogic: string[]
  exclusionLogic: string[]
  biomarkerStrategy: string
  comparator: string
  risks: { risk: string; severity: SafetySeverity; mitigation: string }[]
  disclaimer: string
  confidence: number
  createdAt: string
}

export interface RegulatoryCheck {
  id: string
  projectId: string
  jurisdiction: 'FDA' | 'MFDS' | 'EMA' | 'ICH'
  checklistItem: string
  status: 'met' | 'partial' | 'gap' | 'not_assessed'
  evidenceNeeded: string
  riskLevel: SafetySeverity
  notes: string
  sourceIds: string[]
}

// ============================================================================
// Evaluation
// ============================================================================
export interface EvaluationResult {
  id: string
  projectId: string
  workflowId: string
  benchmarkName: string
  metricName: string
  value: number
  unit?: string
  target: number
  higherIsBetter: boolean
  status: 'pass' | 'warn' | 'fail'
  interpretation: string
  createdAt: string
}

// ============================================================================
// Reports
// ============================================================================
export type ReportType =
  | 'judge_demo'
  | 'technical_architecture'
  | 'candidate_package'
  | 'ethics_safety'
  | 'evaluation_benchmark'
  | 'business_value'
  | 'full_proposal'

export interface Report {
  id: string
  projectId: string
  type: ReportType
  title: string
  markdown: string
  jsonAudit: string
  createdAt: string
  exportStatus: 'ready' | 'exported'
}

// ============================================================================
// Training studio
// ============================================================================
export type TrainingJobType =
  | 'reinvent_rl'
  | 'admet_finetune'
  | 'reward_model'
  | 'tool_router'

export interface TrainingMetric {
  name: string
  value: number
  target?: number
  unit?: string
}

export interface TrainingCurvePoint {
  step: number
  loss: number
  metric: number
}

export interface TrainingJob {
  id: string
  projectId: string
  name: string
  jobType: TrainingJobType
  modelFamily: string
  dataset: string
  objective: string
  status: 'queued' | 'running' | 'complete' | 'failed'
  progress: number
  metrics: TrainingMetric[]
  curve: TrainingCurvePoint[]
  checkpointName: string
  logs: string[]
  mode: AppMode
  hyperparameters: Record<string, string | number>
  createdAt: string
  completedAt?: string
}

export interface DatasetEntry {
  id: string
  name: string
  source: string
  taskType: string
  endpoint: string
  size: number
  licenseStatus: string
  qualityNotes: string
  split: string
  leakageWarning: boolean
}

export interface CheckpointEntry {
  id: string
  name: string
  modelFamily: string
  trainingData: string
  metrics: TrainingMetric[]
  createdAt: string
  status: 'staged' | 'validated' | 'archived'
  notes: string
  mode: AppMode
}

// ============================================================================
// Tools
// ============================================================================
export interface ToolDef {
  id: string
  name: string
  category: string
  categoryLabel: string
  purpose: string
  status: ToolConnectionStatus
  mode: AppMode
  requiredConfig: string[]
  lastRun?: string
  lastError?: string
  exampleOutput: string
  safetyNotes: string
}

// ============================================================================
// Scoring weights (editable)
// ============================================================================
export interface TargetWeights {
  diseaseRelevance: number
  tractability: number
  clinicalPrecedent: number
  biomarkerAvailability: number
  novelty: number
  evidenceConfidence: number
  safetyConcern: number
}

export interface MoleculeWeights {
  binding: number
  admet: number
  qed: number
  lipinski: number
  syntheticFeasibility: number
  novelty: number
  targetRationale: number
  confidence: number
}

// ============================================================================
// Error injection toggles (self-correction demo)
// ============================================================================
export interface InjectionToggles {
  invalidSmiles: boolean
  fakeCitation: boolean
  contradictoryEvidence: boolean
  toolFailure: boolean
  safetyHazard: boolean
  overclaim: boolean
}

// ============================================================================
// Business value assumptions
// ============================================================================
export interface BusinessAssumptions {
  literatureTriageHours: number
  targetPrioritizationDays: number
  moleculeScreeningCount: number
  costPerResearcherHour: number
  workflowsPerMonth: number
  percentTimeSaved: number
  llmToolRunCost: number
}
