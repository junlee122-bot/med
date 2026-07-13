import { useState } from 'react'
import { api, getRememberedRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

type Tab = 'setup' | 'trace' | 'scores' | 'rejected' | 'safety' | 'reinvent' | 'limitations'

const MODE_TONE: Record<string, string> = {
  SELECTION_LOOP: 'cyan', LOCAL_HEURISTIC_GENERATION: 'violet',
  REINVENT4_EXTERNAL: 'green', CONFIGURED_BUT_NOT_RUN: 'amber',
}

export function OptimizationLoop() {
  const [tab, setTab] = useState<Tab>('setup')
  const [result, setResult] = useState<any | null>(null)
  const [trace, setTrace] = useState<any | null>(null)
  const [report, setReport] = useState<string>('')
  const [running, setRunning] = useState(false)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')

  async function run() {
    setRunning(true); setErr(''); setResult(null); setTrace(null); setReport('')
    try {
      const runId = getRememberedRunId()
      const r = await api.optimizationRun({ run_id: runId || undefined })
      setResult(r); setTab('setup')
    }
    catch (e: any) { setErr(e.message) } finally { setRunning(false) }
  }

  async function selectTab(t: Tab) {
    setTab(t)
    if (t === 'trace' && result?.id && !trace) {
      setBusy('trace')
      try { setTrace(await api.optimizationTrace(result.id)) }
      catch (e: any) { setErr(e.message) } finally { setBusy('') }
    }
  }

  async function viewReport() {
    if (!result?.id) return
    setBusy('report'); setErr('')
    try {
      const r = await api.optimizationReport(result.id)
      setReport(r?.markdown || r?.report || '')
    } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  const tabs: [Tab, string][] = [
    ['setup', 'Setup'], ['trace', 'Generation Trace'], ['scores', 'Score Improvement'],
    ['rejected', 'Rejected Candidates'], ['safety', 'Safety Gate'], ['reinvent', 'REINVENT4 Bridge'], ['limitations', 'Limitations'],
  ]

  return (
    <div>
      <PageHeader
        icon={<Icon name="TrendingUp" size={22} />}
        title="Optimization Loop"
        subtitle="In-silico candidate prioritization, not synthesis or experimental validation. No synthesis routes."
        actions={<button className="btn-primary" disabled={running} onClick={run}><Icon name="Play" size={14} /> {running ? 'Running…' : 'Run optimization loop'}</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {running ? <Spinner label="Running optimization loop…" /> : !result ? (
        <Panel><Empty>Run the optimization loop to see generations, scores and safety gating.</Empty></Panel>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard label="Mode" value={<Badge tone={MODE_TONE[result.mode] || 'slate'}>{(result.mode || '—').replace(/_/g, ' ')}</Badge>} tone="cyan" />
            <StatCard label="Generations" value={result.generations ?? 0} tone="violet" />
            <StatCard label="Safety blocks" value={result.safety_block_count ?? 0} tone={result.safety_block_count ? 'red' : 'green'} />
            <StatCard label="Best score" value={fmtNum(lastOf(result.best_score_by_generation))} tone="green" />
            <StatCard label="Candidates" value={sumOf(result.candidate_count_by_generation)} tone="slate" />
          </div>

          <div className="flex flex-wrap gap-2">
            {tabs.map(([t, label]) => (
              <button key={t} aria-pressed={tab === t} className={`btn-secondary ${tab === t ? 'ring-1 ring-brand-400' : ''}`} onClick={() => selectTab(t)}>{label}</button>
            ))}
          </div>

          {tab === 'setup' && (
            <Panel>
              <div className="mb-2 section-title">Setup &amp; per-generation counts</div>
              <div className="mb-2 flex items-center gap-2 text-xs">
                <Badge tone={MODE_TONE[result.mode] || 'slate'}>{(result.mode || '—').replace(/_/g, ' ')}</Badge>
                <span className="text-slate-500">{result.improvement_summary || '—'}</span>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-slate-500">
                    <th className="py-1 pr-2">Generation</th><th className="pr-2">Candidates</th><th className="pr-2">Valid</th><th className="pr-2">Rejected</th><th>Best score</th>
                  </tr></thead>
                  <tbody>
                    {genRows(result).length ? genRows(result).map((r) => (
                      <tr key={r.gen} className="border-t border-white/5">
                        <td className="py-1 pr-2 text-slate-300">{r.gen}</td>
                        <td className="pr-2 text-slate-400">{r.candidates ?? '—'}</td>
                        <td className="pr-2 text-slate-400">{r.valid ?? '—'}</td>
                        <td className="pr-2 text-slate-400">{r.rejected ?? '—'}</td>
                        <td className="text-slate-300">{fmtNum(r.best)}</td>
                      </tr>
                    )) : <tr><td colSpan={5} className="py-3 text-center text-slate-500">No generation data.</td></tr>}
                  </tbody>
                </table>
              </div>
            </Panel>
          )}

          {tab === 'trace' && (
            <Panel>
              <div className="mb-2 section-title">Generation trace</div>
              {busy === 'trace' ? <Spinner label="Loading trace…" /> : !trace ? <Empty>No trace loaded.</Empty> : (
                <div className="space-y-3">
                  {trace.reinvent_status && (
                    <div className="text-xs text-slate-400">REINVENT status: <Badge tone={MODE_TONE[trace.reinvent_status.mode] || 'slate'}>{(trace.reinvent_status.mode || '—').replace(/_/g, ' ')}</Badge></div>
                  )}
                  {!(trace.generation_records || []).length ? <Empty>No generation records.</Empty> : (
                    <div className="space-y-2">
                      {trace.generation_records.map((g: any, i: number) => (
                        <div key={i} className="rounded border border-white/8 p-2 text-xs">
                          <div className="flex items-center justify-between">
                            <span className="text-slate-200">Generation {g.generation ?? i}</span>
                            <span className="text-slate-500">best {fmtNum(g.best_score)}</span>
                          </div>
                          <div className="mt-1 text-slate-500">candidates {g.candidate_count ?? '—'} · valid {g.valid_count ?? '—'} · rejected {g.rejected_count ?? '—'} · safety-blocked {g.safety_block_count ?? 0}</div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Panel>
          )}

          {tab === 'scores' && (
            <Panel>
              <div className="mb-2 section-title">Score improvement</div>
              {!(result.best_score_by_generation || []).length ? <Empty>No scores recorded.</Empty> : (
                <div className="space-y-2 text-xs">
                  <div className="font-mono text-slate-300">{(result.best_score_by_generation || []).map((s: any) => fmtNum(s)).join('  →  ')}</div>
                  <div className="flex items-end gap-1">
                    {sparkbars(result.best_score_by_generation)}
                  </div>
                </div>
              )}
            </Panel>
          )}

          {tab === 'rejected' && (
            <Panel>
              <div className="mb-2 section-title">Rejected candidates</div>
              {!(result.rejected_count_by_generation || []).length ? <Empty>No rejection data.</Empty> : (
                <div className="flex flex-wrap gap-2 text-xs">
                  {(result.rejected_count_by_generation || []).map((c: any, i: number) => (
                    <div key={i} className="rounded border border-white/8 px-2 py-1">
                      <span className="text-slate-500">gen {i}</span>: <span className="text-slate-300">{c}</span>
                    </div>
                  ))}
                </div>
              )}
            </Panel>
          )}

          {tab === 'safety' && (
            <Panel>
              <div className="mb-2 section-title">Safety gate</div>
              <div className="flex items-center gap-2 text-xs">
                <Badge tone={result.safety_block_count ? 'red' : 'green'}>{result.safety_block_count ?? 0} blocked</Badge>
                <span className="text-slate-500">Structurally hazardous or safety-flagged candidates are removed before scoring.</span>
              </div>
            </Panel>
          )}

          {tab === 'reinvent' && (
            <Panel>
              <div className="mb-2 section-title">REINVENT4 bridge</div>
              <div className="text-xs text-slate-400">
                <div className="flex items-center gap-2">
                  <span className="text-slate-500">bridge mode</span>
                  <Badge tone={MODE_TONE[trace?.reinvent_status?.mode || result.mode] || 'slate'}>{((trace?.reinvent_status?.mode) || result.mode || '—').replace(/_/g, ' ')}</Badge>
                </div>
                <p className="mt-2">When REINVENT4 is configured but not executed, this is reported honestly as <span className="text-slate-300">CONFIGURED_BUT_NOT_RUN</span> rather than presented as a real generative run. Load the Generation Trace tab to fetch the live bridge status.</p>
              </div>
            </Panel>
          )}

          {tab === 'limitations' && (
            <Panel>
              <div className="mb-2 section-title">Limitations</div>
              {!(result.limitations || []).length ? <Empty>No limitations reported.</Empty> : (
                <ul className="space-y-0.5 text-xs text-slate-400">
                  {(result.limitations || []).map((l: string, i: number) => <li key={i}>· {l}</li>)}
                </ul>
              )}
            </Panel>
          )}

          <div>
            <button className="btn-secondary" disabled={!!busy} onClick={viewReport}><Icon name="FileText" size={14} /> {busy === 'report' ? '…' : 'View report'}</button>
            {report && <pre className="mt-3 max-h-[480px] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-black/30 p-4 font-mono text-[11px] leading-relaxed text-slate-300">{report}</pre>}
          </div>

          <div className="text-[11px] text-slate-500">In-silico candidate prioritization, not synthesis or experimental validation. No synthesis routes.</div>
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}

function genRows(result: any): { gen: number; candidates: any; valid: any; rejected: any; best: any }[] {
  const cand = result.candidate_count_by_generation || []
  const valid = result.valid_count_by_generation || []
  const rej = result.rejected_count_by_generation || []
  const best = result.best_score_by_generation || []
  const n = Math.max(cand.length, valid.length, rej.length, best.length)
  const rows = []
  for (let i = 0; i < n; i++) rows.push({ gen: i, candidates: cand[i], valid: valid[i], rejected: rej[i], best: best[i] })
  return rows
}

function sparkbars(arr: any) {
  const vals = (arr || []).map((v: any) => Number(v)).filter((v: number) => isFinite(v))
  if (!vals.length) return null
  const max = Math.max(...vals, 0.0001)
  return vals.map((v: number, i: number) => (
    <div key={i} className="w-3 rounded-t bg-helix-cyan/60" style={{ height: `${Math.max(4, (v / max) * 48)}px` }} title={String(v)} />
  ))
}

function fmtNum(v: any): string {
  const n = typeof v === 'number' ? v : Number(v)
  if (!isFinite(n)) return '—'
  return n.toFixed(3)
}
function lastOf(arr: any): any { return Array.isArray(arr) && arr.length ? arr[arr.length - 1] : undefined }
function sumOf(arr: any): number { return Array.isArray(arr) ? arr.reduce((a: number, b: any) => a + (Number(b) || 0), 0) : 0 }
