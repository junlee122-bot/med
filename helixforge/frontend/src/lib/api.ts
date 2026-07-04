// Typed API client for the HelixForge FastAPI backend.
// Base URL is configurable; defaults to same-origin (dev proxy forwards /api).

export const API_BASE =
  (import.meta as any).env?.VITE_API_BASE?.replace(/\/$/, '') || ''

export type SourceType =
  | 'REAL_TOOL_OUTPUT'
  | 'DEMO_FALLBACK'
  | 'CONFIGURED_BUT_NOT_RUN'
  | 'TOOL_ERROR'
  | 'HUMAN_INPUT'

export type HealthStatus =
  | 'AVAILABLE'
  | 'MISSING_DEPENDENCY'
  | 'NOT_CONFIGURED'
  | 'DEGRADED'
  | 'ERROR'

export interface ToolHealth {
  tool_id: string
  name: string
  category: string
  status: HealthStatus
  mode: string
  detail: string
  required_config: string[]
  checked_at: string
  latency_ms?: number
}

export interface Envelope {
  tool_name: string
  source: string
  source_type: SourceType
  input_summary: string
  output_summary: string
  retrieved_at?: string
  validation_status?: string
  audit_event_id?: string
  errors: string[]
  warnings: string[]
}

export interface PubMedItem {
  pmid: string; title: string; abstract: string; journal: string; year: string
  authors: string[]; url: string; retrieved_at: string
}
export interface ClinicalTrialItem {
  nct_id: string; brief_title: string; status: string; phase: string
  conditions: string[]; interventions: string[]; primary_outcomes: string[]; url: string
}
export interface RDKitDescriptors {
  mol_weight: number; logp: number; hbd: number; hba: number; tpsa: number
  rotatable_bonds: number; ring_count: number; qed: number
  lipinski_pass: boolean; lipinski_violations: number
}
export interface RDKitResponse extends Envelope {
  valid: boolean; canonical_smiles: string
  descriptors?: RDKitDescriptors; similarity?: number; fingerprint_bits?: number
}
export interface WorkflowStep {
  step: string; tool_name: string; source_type: SourceType; status: string
  summary: string; audit_event_id?: string; errors: string[]
}
export interface WorkflowRun {
  run_id: string; project_id: string; status: string; started_at: string
  completed_at?: string; steps: WorkflowStep[]; counts: Record<string, number>
  report_id?: string; disclaimer: string
}
export interface AuditEvent {
  id: string; timestamp: string; agent_name: string; tool_name: string
  event_type: string; source_type: SourceType; input_summary: string
  output_summary: string; validation_status: string; warnings: string[]; errors: string[]
}

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const j = await res.json()
      detail = j.detail || JSON.stringify(j)
    } catch {}
    throw new Error(`HTTP ${res.status}: ${detail}`)
  }
  return res.json() as Promise<T>
}

const post = <T,>(path: string, body: unknown) =>
  req<T>(path, { method: 'POST', body: JSON.stringify(body) })
const get = <T,>(path: string) => req<T>(path)

export const api = {
  health: () => get<{ status: string; service: string; version: string }>('/api/health'),
  toolsHealth: () =>
    get<{ checked_at: string; summary: Record<string, number>; tools: ToolHealth[] }>('/api/tools/health'),

  pubmed: (query: string, max_results = 10) =>
    post<Envelope & { items: PubMedItem[] }>('/api/pubmed/search', { query, max_results }),
  clinicaltrials: (condition: string, query: string, max_results = 10) =>
    post<Envelope & { items: ClinicalTrialItem[] }>('/api/clinicaltrials/search', { condition, query, max_results }),

  chemblTargets: (query: string, max_results = 10) =>
    post<Envelope & { items: any[] }>('/api/chembl/search-targets', { query, max_results }),
  chemblMolecules: (query: string, max_results = 10) =>
    post<Envelope & { items: any[] }>('/api/chembl/search-molecules', { query, max_results }),
  chemblActivities: (target_chembl_id: string, activity_type = 'IC50', max_results = 50) =>
    post<Envelope & { items: any[] }>('/api/chembl/activities', { target_chembl_id, activity_type, max_results }),

  rdkitValidate: (smiles: string) => post<RDKitResponse>('/api/rdkit/validate', { smiles }),
  rdkitDescriptors: (smiles: string) => post<RDKitResponse>('/api/rdkit/descriptors', { smiles }),
  rdkitSimilarity: (smiles: string, reference_smiles: string) =>
    post<RDKitResponse>('/api/rdkit/similarity', { smiles, reference_smiles }),

  tdcDatasets: () =>
    get<{ source_type: SourceType; installed: boolean; datasets: any[] }>('/api/tdc/datasets'),
  tdcLoad: (dataset: string, task = 'ADME') => post<any>('/api/tdc/load', { dataset, task }),
  tdcBenchmark: (dataset: string, task = 'ADME') => post<any>('/api/tdc/benchmark-summary', { dataset, task }),

  vinaDock: (body: any) => post<any>('/api/vina/fixture-dock', body),

  reinventCreateConfig: (body: any) => post<any>('/api/reinvent/create-config', body),
  reinventRun: (config_path: string) => post<any>('/api/reinvent/run', { config_path }),

  safetyScreen: (body: { text?: string; smiles?: string; label?: string }) =>
    post<any>('/api/safety/screen', body),

  runPipeline: (body: any) => post<WorkflowRun>('/api/workflow/run-real-pipeline', body),
  runTargetDiscovery: (body: any) => post<WorkflowRun>('/api/workflow/run-target-discovery', body),
  runMoleculeScreening: (body: any) => post<WorkflowRun>('/api/workflow/run-molecule-screening', body),
  getRun: (id: string) => get<any>(`/api/workflow/runs/${id}`),

  auditEvents: (project_id?: string, limit = 200) =>
    get<{ events: AuditEvent[] }>(`/api/audit/events?limit=${limit}${project_id ? `&project_id=${project_id}` : ''}`),

  reportGenerate: (body: any) =>
    post<{ report_id: string; title: string; markdown: string; json_audit: any }>('/api/report/generate', body),
  getReport: (id: string) =>
    get<{ report_id: string; title: string; markdown: string; json_audit: any }>(`/api/report/${id}`),
  listReports: (project_id?: string) =>
    get<{ reports: any[] }>(`/api/reports${project_id ? `?project_id=${project_id}` : ''}`),

  getSettings: () => get<{ editable_keys: string[]; values: Record<string, any> }>('/api/settings'),
  updateSettings: (values: Record<string, any>) =>
    post<{ applied_keys: string[]; values: Record<string, any> }>('/api/settings', values),

  // --- Phase 2: agentic layer ---
  toolsHealthLive: (live: boolean, timeout_seconds = 5) =>
    get<{ checked_at: string; live: boolean; summary: Record<string, number>; tools: ToolHealth[] }>(
      `/api/tools/health?live=${live}&timeout_seconds=${timeout_seconds}`),
  listAgents: () => get<{ agents: AgentDef[]; count: number }>('/api/agents'),
  runAgenticPipeline: (body: AgenticRequest) => post<AgenticRunResult>('/api/workflow/run-agentic-pipeline', body),
  runErrorInjectionDemo: (scenario: string, condition = 'non-small cell lung cancer', target_query = 'EGFR') =>
    post<ErrorInjectionResult>('/api/workflow/run-error-injection-demo', { scenario, condition, target_query }),
  runAgents: (run_id: string) => get<{ run_id: string; agent_runs: AgentRun[] }>(`/api/workflow/runs/${run_id}/agents`),
  runRevisions: (run_id: string) => get<{ run_id: string; revision_events: RevisionEvent[] }>(`/api/workflow/runs/${run_id}/revisions`),
  runManifest: (run_id: string) => get<any>(`/api/workflow/runs/${run_id}/manifest`),

  listTargets: (project_id?: string) => get<{ targets: any[]; count: number }>(`/api/targets${project_id ? `?project_id=${project_id}` : ''}`),
  getTarget: (id: string) => get<any>(`/api/targets/${id}`),
  listHypotheses: (project_id?: string) => get<{ hypotheses: any[] }>(`/api/hypotheses${project_id ? `?project_id=${project_id}` : ''}`),
  listEvidence: (project_id?: string) => get<{ evidence: any[] }>(`/api/evidence${project_id ? `?project_id=${project_id}` : ''}`),
  listMoleculesData: (project_id?: string) => get<{ molecules: any[]; count: number }>(`/api/molecules${project_id ? `?project_id=${project_id}` : ''}`),
  verifyEvidence: (body: { source_name: string; identifier: string; identifier_type: string; url?: string }) =>
    post<{ verification_status: string; verification_reason: string }>('/api/evidence/verify', body),

  evaluationSummary: (project_id?: string) => get<EvaluationSummary>(`/api/evaluation/summary${project_id ? `?project_id=${project_id}` : ''}`),
  evaluationRun: (run_id: string) => get<{ run_id: string; metrics_flat: any[]; metrics: any }>(`/api/evaluation/runs/${run_id}`),
  runRetrospective: (body: AgenticRequest) => post<any>('/api/evaluation/run-retrospective', body),

  exportRun: (run_id: string) => get<any>(`/api/export/run/${run_id}`),
  safetyLintReport: (body: { markdown?: string; report_id?: string }) =>
    post<{ status: string; export_safe: boolean; findings: any[] }>('/api/safety/lint-report', body),
}

export interface AgentDef { name: string; role: string; stage: string; stage_index: number; allowed_tools: string[] }
export interface AgentRun {
  id: string; agent_name: string; agent_role: string; stage: string; stage_index: number; status: string
  output_summary: string; rationale: string; assumptions: string[]; uncertainty_notes: string; next_action: string
  confidence: number; validation_status: string; validation_checks: { check: string; ok: boolean; detail: string }[]
  source_types: SourceType[]; warnings: string[]; errors: string[]; evidence_ids: string[]; molecule_ids: string[]; target_ids: string[]
}
export interface RevisionEvent {
  id: string; reason_category: string; issue_summary: string; action_taken: string
  before_summary: string; after_summary: string; confidence_delta: number
}
export interface ErrorInjections {
  invalid_smiles?: boolean; fake_citation?: boolean; tool_failure?: boolean
  safety_flag?: boolean; overclaim?: boolean; contradictory_evidence?: boolean
}
export interface AgenticRequest {
  condition?: string; target_query?: string; max_results?: number
  create_reinvent_config?: boolean; run_vina_fixture?: boolean; error_injections?: ErrorInjections
}
export interface AgenticRunResult {
  run_id: string; project_id: string; status: string; agent_runs: AgentRun[]
  plan: { objective: string; stages: { index: number; agent: string; stage: string }[] }
  steps: any[]; revision_events: RevisionEvent[]; counts: Record<string, number>
  metrics: Record<string, any>; report_id?: string; ko_report_id?: string; disclaimer: string
}
export interface ErrorInjectionResult {
  scenario: string; workflow_run_id: string; corrected: boolean; before: string; after: string
  agent_runs: AgentRun[]; revision_events: RevisionEvent[]; metric_summary: Record<string, any>; report_id?: string
}
export interface EvaluationSummary {
  modules: Record<string, { metric: string; value: any; status: string }[]>
  module_count: number; metric_count: number; latest_run?: string; latest_metrics: Record<string, any>
}

export const REASON_META: Record<string, { label: string; tone: string }> = {
  invalid_structure: { label: 'Invalid SMILES', tone: 'red' },
  fake_citation: { label: 'Fake citation', tone: 'red' },
  overclaim: { label: 'Overclaim', tone: 'amber' },
  contradictory_evidence: { label: 'Contradictory evidence', tone: 'amber' },
  tool_failure: { label: 'Tool failure', tone: 'amber' },
  safety_block: { label: 'Safety block', tone: 'violet' },
}

export const SOURCE_META: Record<SourceType, { label: string; tone: string }> = {
  REAL_TOOL_OUTPUT: { label: 'Real Tool Output', tone: 'green' },
  DEMO_FALLBACK: { label: 'Demo Fallback', tone: 'cyan' },
  CONFIGURED_BUT_NOT_RUN: { label: 'Configured · Not Run', tone: 'amber' },
  TOOL_ERROR: { label: 'Tool Error', tone: 'red' },
  HUMAN_INPUT: { label: 'Human Input', tone: 'violet' },
}

export const HEALTH_META: Record<HealthStatus, { label: string; tone: string }> = {
  AVAILABLE: { label: 'Available', tone: 'green' },
  DEGRADED: { label: 'Degraded', tone: 'amber' },
  NOT_CONFIGURED: { label: 'Not Configured', tone: 'amber' },
  MISSING_DEPENDENCY: { label: 'Missing Dependency', tone: 'red' },
  ERROR: { label: 'Error', tone: 'red' },
}

export const HUMAN_RESPONSIBILITY =
  'This system is research decision support only. It does not replace expert scientific, clinical, regulatory, legal, or ethical review. Final responsibility belongs to the human research team.'
