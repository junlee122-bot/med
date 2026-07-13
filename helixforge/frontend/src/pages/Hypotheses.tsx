import { useEffect, useState } from 'react'
import { api, getRememberedRunId, rememberRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'

export function Hypotheses() {
  const [runId, setRunId] = useState(getRememberedRunId)
  const [hyps, setHyps] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [err, setErr] = useState('')

  async function load() {
    setLoading(true)
    try { const r = await api.listHypotheses(undefined, runId || undefined); setHyps(r.hypotheses) } catch (e: any) { setHyps([]); setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [runId])

  async function runPipeline() {
    setRunning(true); setErr('')
    try {
      const result = await api.runAgenticPipeline({ target_query: 'EGFR', max_results: 6, create_reinvent_config: false })
      rememberRunId(result.run_id); setRunId(result.run_id)
    }
    catch (e: any) { setErr(e.message) } finally { setRunning(false) }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="Lightbulb" size={22} />}
        title="Hypotheses"
        subtitle="Conservative, evidence-linked in-silico hypotheses from the Hypothesis Agent. Guarded language only — no efficacy, cure, or clinical-confirmation claims."
        actions={<button className="btn-primary" onClick={runPipeline} disabled={running}><Icon name="Play" size={15} /> {running ? 'Running…' : 'Run pipeline'}</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Loading hypotheses…" /> : hyps.length === 0 ? (
        <Empty>No hypotheses yet. Run the agentic pipeline to generate evidence-linked hypotheses.</Empty>
      ) : (
        <div className="space-y-3">
          {hyps.map((h) => (
            <Panel key={h.id}>
              <div className="flex items-start justify-between gap-3">
                <div className="text-sm font-medium text-slate-100">{h.statement}</div>
                <div className="flex flex-shrink-0 items-center gap-2">
                  {h.critic_status === 'rewritten' && <Badge tone="amber">rewritten by critic</Badge>}
                  <Badge tone={h.confidence >= 0.65 ? 'green' : 'amber'}>{Math.round((h.confidence || 0) * 100)}%</Badge>
                </div>
              </div>
              <div className="mt-2 grid gap-2 text-xs text-slate-400 sm:grid-cols-2">
                <div><span className="text-slate-500">Target: </span>{h.target_symbol} ({h.target_id})</div>
                <div><span className="text-slate-500">Mechanism: </span>{h.mechanism_summary}</div>
              </div>
              {h.evidence_ids?.length > 0 && (
                <div className="mt-2 flex flex-wrap items-center gap-1">
                  <span className="text-[10px] uppercase tracking-wide text-slate-500">evidence</span>
                  {h.evidence_ids.map((e: string) => <span key={e} className="chip border-line-bright bg-bg-hover text-slate-300">{e}</span>)}
                </div>
              )}
              {h.limitations && <div className="mt-2 text-[11px] text-slate-500">⚠ {h.limitations}</div>}
            </Panel>
          ))}
        </div>
      )}
    </div>
  )
}
