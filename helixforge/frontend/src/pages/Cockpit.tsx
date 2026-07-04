import { useState } from 'react'
import { api, HUMAN_RESPONSIBILITY } from '@/lib/api'
import type { WorkflowRun, AuditEvent } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, SourceBadge, Spinner, StatCard } from '@/components/ui'

const DISEASE = 'non-small cell lung cancer'
const TARGET = 'EGFR'

export function Cockpit() {
  const [run, setRun] = useState<WorkflowRun | null>(null)
  const [events, setEvents] = useState<AuditEvent[]>([])
  const [loading, setLoading] = useState<string | null>(null)
  const [error, setError] = useState('')
  const [report, setReport] = useState<{ report_id: string; title: string } | null>(null)

  async function exec(kind: 'pipeline' | 'target' | 'molecule') {
    setLoading(kind); setError(''); setReport(null)
    try {
      const body = { condition: DISEASE, target_query: TARGET, max_results: 5 }
      const r =
        kind === 'pipeline' ? await api.runPipeline(body)
        : kind === 'target' ? await api.runTargetDiscovery(body)
        : await api.runMoleculeScreening(body)
      setRun(r)
      try { const a = await api.auditEvents(r.project_id, 200); setEvents(a.events) } catch {}
    } catch (e: any) { setError(e.message) } finally { setLoading(null) }
  }

  async function genReport() {
    if (!run) return
    setLoading('report'); setError('')
    try {
      const rep = await api.reportGenerate({ project_id: run.project_id, run_id: run.run_id, report_type: 'candidate_package' })
      setReport({ report_id: rep.report_id, title: rep.title })
    } catch (e: any) { setError(e.message) } finally { setLoading(null) }
  }

  const counts = run?.counts || {}

  return (
    <div>
      <PageHeader
        icon={<Icon name="Cpu" size={22} />}
        title="Agent Cockpit"
        subtitle="Drive real multi-agent workflows. Each step calls a live tool adapter and is labeled with its true source type — no fabricated results."
        actions={
          <>
            <button className="btn-secondary" disabled={!!loading} onClick={() => exec('target')}>
              <Icon name="Crosshair" size={15} /> Target discovery
            </button>
            <button className="btn-secondary" disabled={!!loading} onClick={() => exec('molecule')}>
              <Icon name="FlaskConical" size={15} /> Molecule screening
            </button>
            <button className="btn-primary" disabled={!!loading} onClick={() => exec('pipeline')}>
              <Icon name="Play" size={15} /> Run full real pipeline
            </button>
          </>
        }
      />

      {loading && <div className="mb-4"><Spinner label={`Running ${loading}… (live API calls to PubMed / ChEMBL / ClinicalTrials / RDKit / TDC)`} /></div>}
      {error && <div className="mb-4"><ErrorNote error={error} /></div>}

      {!run && !loading && (
        <Empty>
          Run a workflow to see real tool calls, source-type badges, and the audit trail. The full pipeline queries PubMed, ChEMBL, ClinicalTrials.gov, validates molecules with RDKit, loads a TDC dataset, runs the safety gate, and builds a report.
        </Empty>
      )}

      {run && (
        <>
          <div className="mb-5 grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatCard label="Run status" value={run.status} tone={run.status === 'complete' ? 'green' : 'amber'} />
            <StatCard label="Steps" value={run.steps.length} sub={`${run.steps.filter(s => s.source_type === 'REAL_TOOL_OUTPUT').length} real-tool`} />
            <StatCard label="Evidence" value={(counts.pubmed || 0) + (counts.trials || 0)} sub={`${counts.pubmed || 0} papers · ${counts.trials || 0} trials`} />
            <StatCard label="Candidates" value={counts.candidates_valid ?? counts.candidates ?? 0} sub={`${counts.candidates_invalid || 0} invalid caught`} />
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel>
              <div className="mb-3 flex items-center justify-between">
                <div className="section-title">Workflow steps · observable trace</div>
                <Badge tone="cyan">{run.run_id}</Badge>
              </div>
              <ol className="space-y-2">
                {run.steps.map((s, i) => (
                  <li key={i} className="rounded-lg border border-line bg-bg-soft/40 p-3">
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-sm font-medium text-slate-200">
                        <span className="text-slate-500">{String(i + 1).padStart(2, '0')}</span>
                        {s.tool_name || s.step}
                      </div>
                      <SourceBadge type={s.source_type} />
                    </div>
                    <div className="mt-1 text-xs text-slate-400">{s.summary}</div>
                    {s.errors?.length > 0 && <div className="mt-1 text-xs text-helix-red">{s.errors.join('; ')}</div>}
                  </li>
                ))}
              </ol>
              <div className="mt-4 flex items-center gap-2">
                <button className="btn-primary" disabled={!!loading} onClick={genReport}>
                  <Icon name="FileText" size={15} /> Generate report
                </button>
                {report && <Badge tone="green">Report ready · {report.report_id}</Badge>}
              </div>
            </Panel>

            <Panel>
              <div className="mb-3 section-title">Audit trail · {events.length} events</div>
              {events.length === 0 ? (
                <Empty>No audit events for this run.</Empty>
              ) : (
                <div className="max-h-[520px] space-y-2 overflow-auto pr-1">
                  {events.map((e) => (
                    <div key={e.id} className="rounded-lg border border-line bg-bg-soft/40 p-2.5">
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs font-medium text-slate-300">{e.agent_name} · {e.tool_name}</span>
                        <SourceBadge type={e.source_type} />
                      </div>
                      <div className="mt-1 text-[11px] text-slate-400">{e.output_summary}</div>
                      <div className="mt-1 flex items-center gap-2 text-[10px] text-slate-500">
                        <span>{e.event_type}</span>
                        <span>· {e.validation_status}</span>
                        <span>· {new Date(e.timestamp).toLocaleTimeString()}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          </div>

          <div className="mt-4"><Disclaimer text={run.disclaimer || HUMAN_RESPONSIBILITY} /></div>
        </>
      )}
    </div>
  )
}
