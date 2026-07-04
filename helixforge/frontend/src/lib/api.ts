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
