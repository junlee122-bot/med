import { useEffect, useState } from 'react'
import { api, getRememberedRunId, rememberRunId } from '@/lib/api'
import type { EvaluationSummary } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'
import { MetricTile } from '@/components/agentic'

const MODULE_META: Record<string, { label: string; icon: string }> = {
  tool_integration: { label: 'Real Tool Integration', icon: 'Plug' },
  evidence_integrity: { label: 'Evidence Integrity', icon: 'BookCheck' },
  molecule_validity: { label: 'Molecule Validity', icon: 'Atom' },
  agent_autonomy: { label: 'Agent Autonomy', icon: 'Cpu' },
  resource_efficiency: { label: 'Resource Efficiency', icon: 'Zap' },
  retrospective_rediscovery: { label: 'Retrospective Rediscovery', icon: 'Target' },
}

export function Evaluation() {
  const [runId, setRunId] = useState(getRememberedRunId)
  const [sum, setSum] = useState<EvaluationSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [err, setErr] = useState('')
  const [retro, setRetro] = useState<any | null>(null)

  async function load() {
    setLoading(true)
    setErr('')
    try { setSum(await api.evaluationSummary(undefined, runId || undefined)) } catch (e: any) { setSum(null); setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [runId])

  async function runRetro() {
    setRunning(true); setErr('')
    try {
      const r = await api.runRetrospective({ target_query: 'EGFR', condition: 'non-small cell lung cancer', max_results: 6, create_reinvent_config: false })
      setRetro(r.retrospective); rememberRunId(r.run_id); setRunId(r.run_id)
    } catch (e: any) { setErr(e.message) } finally { setRunning(false) }
  }

  const m = sum?.latest_metrics || {}
  const retroData = retro || m.retrospective
  return (
    <div>
      <PageHeader
        icon={<Icon name="BarChart3" size={22} />}
        title="Evaluation Bench"
        subtitle="Metrics computed from real agentic runs — tool integration, evidence integrity, molecule validity, agent autonomy, resource efficiency, and EGFR/NSCLC retrospective rediscovery. Nothing fabricated."
        actions={<button className="btn-primary" onClick={runRetro} disabled={running}><Icon name="Play" size={15} /> {running ? 'Running…' : 'Run retrospective benchmark'}</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Loading evaluation summary…" /> : (
        <>
          {retroData && (
            <Panel className="mb-4">
              <div className="mb-2 flex items-center justify-between">
                <div className="section-title">Retrospective rediscovery (EGFR / NSCLC)</div>
                <Badge tone={retroData.status === 'pass' ? 'green' : 'amber'}>{retroData.passed}/{retroData.total} criteria</Badge>
              </div>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
                {Object.entries(retroData.criteria || {}).map(([k, v]) => (
                  <div key={k} className={`rounded-lg border p-2 text-center ${v ? 'border-brand-500/30 bg-brand-500/5' : 'border-helix-red/30 bg-helix-red/5'}`}>
                    <Icon name={v ? 'CheckCircle2' : 'XCircle'} size={16} className={v ? 'text-brand-400' : 'text-helix-red'} />
                    <div className="mt-1 text-[10px] text-slate-400">{k.replace(/_/g, ' ')}</div>
                  </div>
                ))}
              </div>
              <div className="mt-2 text-[11px] text-slate-500">{retroData.note}</div>
            </Panel>
          )}

          {!sum || sum.metric_count === 0 ? (
            <Empty>No evaluation metrics yet. Run the retrospective benchmark (or the agentic pipeline) to populate the bench.</Empty>
          ) : (
            <>
              <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
                <MetricTile label="Real outputs" value={m.real_tool_output_count ?? '—'} tone="green" />
                <MetricTile label="Config·NotRun" value={m.configured_not_run_count ?? '—'} tone="amber" />
                <MetricTile label="Citation verif." value={m.citation_verification_rate ?? '—'} />
                <MetricTile label="Mol. validity" value={m.molecule_validity_rate ?? '—'} />
                <MetricTile label="Self-correction" value={m.self_correction_rate ?? '—'} tone="green" />
                <MetricTile label="Runtime" value={`${m.runtime_seconds ?? '—'}s`} />
              </div>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {Object.entries(sum.modules).map(([mod, metrics]) => {
                  const meta = MODULE_META[mod] || { label: mod, icon: 'Gauge' }
                  return (
                    <Panel key={mod}>
                      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-100">
                        <Icon name={meta.icon} size={15} className="text-helix-cyan" /> {meta.label}
                      </div>
                      <div className="space-y-1">
                        {metrics.slice(0, 8).map((x, i) => (
                          <div key={i} className="flex items-center justify-between border-b border-line/50 py-1 text-xs last:border-0">
                            <span className="text-slate-400">{x.metric.replace(/_/g, ' ')}</span>
                            <span className="font-mono tabular-nums text-slate-200">{String(x.value)}</span>
                          </div>
                        ))}
                      </div>
                    </Panel>
                  )
                })}
              </div>
            </>
          )}
        </>
      )}
    </div>
  )
}
