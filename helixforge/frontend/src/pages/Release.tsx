import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'

const STATUS_TONE: Record<string, string> = {
  NOT_READY: 'red', DRAFT_READY: 'amber', PROPOSAL_READY: 'amber', DEMO_READY: 'green', SUBMISSION_READY: 'green',
}
const GROUP_LABEL: Record<string, string> = {
  tool_readiness: 'Tools', agent_readiness: 'Agents', evidence_readiness: 'Evidence',
  molecule_readiness: 'Molecules', report_readiness: 'Reports', safety_readiness: 'Safety', demo_readiness: 'Demo',
}

export function Release() {
  const [data, setData] = useState<any | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  async function load() {
    setLoading(true); setErr('')
    try { setData(await api.releaseReadiness()) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const score = data?.total_score ?? 0
  const circ = 2 * Math.PI * 52
  return (
    <div>
      <PageHeader
        icon={<Icon name="Gauge" size={22} />}
        title="Release Readiness"
        subtitle="Is the project ready for proposal, peer review, demo, and final submission? Computed from real project state — runs, reports, snapshots, safety, tools."
        actions={<button className="btn-secondary" onClick={load} disabled={loading}><Icon name="RefreshCw" size={14} /> Re-check</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Computing readiness…" /> : !data ? <Empty>No data.</Empty> : (
        <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
          <div className="space-y-4">
            <Panel>
              <div className="flex flex-col items-center">
                <svg width="140" height="140" viewBox="0 0 120 120" className="-rotate-90">
                  <circle cx="60" cy="60" r="52" fill="none" stroke="#1f2b48" strokeWidth="10" />
                  <circle cx="60" cy="60" r="52" fill="none" stroke={score >= 85 ? '#16b884' : score >= 70 ? '#f59e0b' : '#ef4444'}
                    strokeWidth="10" strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - score / 100)} />
                </svg>
                <div className="-mt-[92px] text-center">
                  <div className="text-3xl font-bold text-white">{score}</div>
                  <div className="text-[10px] text-slate-500">/ 100</div>
                </div>
                <div className="mt-[52px]"><Badge tone={STATUS_TONE[data.status] || 'slate'}>{data.status.replace(/_/g, ' ')}</Badge></div>
              </div>
            </Panel>
            <Panel>
              <div className="section-title mb-2">Blocking issues</div>
              {data.blocking_issues.length === 0 ? <div className="text-xs text-brand-300">None ✓</div> : (
                <ul className="space-y-1 text-[11px] text-helix-red">{data.blocking_issues.map((b: string) => <li key={b}>✕ {b}</li>)}</ul>
              )}
              <div className="section-title mb-2 mt-3">Next actions</div>
              <ul className="space-y-1 text-[11px] text-slate-400">{data.recommended_next_actions.map((a: string) => <li key={a} className="flex gap-1"><Icon name="ArrowRight" size={11} className="mt-0.5 flex-shrink-0 text-helix-cyan" /> {a}</li>)}</ul>
            </Panel>
          </div>

          <Panel>
            <div className="section-title mb-3">Readiness checklist</div>
            <div className="grid gap-3 sm:grid-cols-2">
              {Object.entries(data.checks).map(([group, items]) => (
                <div key={group} className="rounded-lg border border-line bg-bg-soft/40 p-3">
                  <div className="mb-1.5 text-sm font-medium text-slate-200">{GROUP_LABEL[group] || group}</div>
                  <div className="space-y-1">
                    {(items as any[]).map((c, i) => (
                      <div key={i} className="flex items-start gap-2 text-[11px]">
                        <Icon name={c.ok ? 'CheckCircle2' : c.blocking ? 'XCircle' : 'AlertCircle'} size={12}
                          className={`mt-0.5 flex-shrink-0 ${c.ok ? 'text-brand-400' : c.blocking ? 'text-helix-red' : 'text-helix-amber'}`} />
                        <span className={c.ok ? 'text-slate-400' : c.blocking ? 'text-helix-red' : 'text-helix-amber'}>{c.label}</span>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </div>
  )
}
