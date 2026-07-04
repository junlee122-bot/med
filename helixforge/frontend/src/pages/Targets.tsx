import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'

export function Targets() {
  const [targets, setTargets] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [err, setErr] = useState('')
  const [sel, setSel] = useState<any | null>(null)

  async function load() {
    setLoading(true)
    try { const r = await api.listTargets(); setTargets(r.targets) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function runPipeline() {
    setRunning(true); setErr('')
    try { await api.runAgenticPipeline({ target_query: 'EGFR', condition: 'non-small cell lung cancer', max_results: 6, create_reinvent_config: false }); await load() }
    catch (e: any) { setErr(e.message) } finally { setRunning(false) }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="Crosshair" size={22} />}
        title="Target Prioritization Board"
        subtitle="Real ChEMBL targets ranked by the transparent Target Opportunity Score. The selected druggable single-protein target feeds the chemistry stages."
        actions={<button className="btn-primary" onClick={runPipeline} disabled={running}><Icon name="Play" size={15} /> {running ? 'Running…' : 'Run pipeline'}</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Loading targets…" /> : targets.length === 0 ? (
        <Empty>No targets yet. Run the agentic pipeline to populate the board with real ChEMBL targets.</Empty>
      ) : (
        <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
          <Panel>
            <div className="overflow-auto rounded-lg border border-line">
              <table className="w-full text-left text-xs">
                <thead className="bg-bg-soft text-slate-400"><tr>
                  <th className="p-2">Rank</th><th className="p-2">Target</th><th className="p-2">ChEMBL</th><th className="p-2">Type</th><th className="p-2">Organism</th><th className="p-2">Evidence</th><th className="p-2">Trials</th><th className="p-2">Score</th><th className="p-2">Status</th>
                </tr></thead>
                <tbody>
                  {targets.map((t) => (
                    <tr key={t.id} onClick={() => setSel(t)} className={`cursor-pointer border-t border-line hover:bg-bg-hover/50 ${sel?.id === t.id ? 'bg-helix-cyan/5' : ''}`}>
                      <td className="p-2 text-slate-500">{t.rank}</td>
                      <td className="p-2 font-medium text-slate-100">{t.pref_name}</td>
                      <td className="p-2 text-slate-400">{t.target_chembl_id}</td>
                      <td className="p-2 text-slate-400">{t.target_type}</td>
                      <td className="p-2 text-slate-400">{t.organism}</td>
                      <td className="p-2 text-slate-400">{t.evidence_count}</td>
                      <td className="p-2 text-slate-400">{t.clinical_precedent_count}</td>
                      <td className="p-2"><span className="font-semibold text-helix-cyan">{t.score}</span></td>
                      <td className="p-2">{t.status === 'selected' ? <Badge tone="green">selected</Badge> : <Badge tone="slate">{t.status}</Badge>}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>
          <Panel>
            {!sel ? <Empty>Select a target to see its score breakdown.</Empty> : (
              <div>
                <div className="mb-1 text-lg font-semibold text-white">{sel.pref_name}</div>
                <div className="mb-3 flex items-center gap-2 text-xs text-slate-400">
                  <Badge tone="cyan">{sel.target_chembl_id}</Badge><span>{sel.target_type} · {sel.organism}</span>
                </div>
                <div className="mb-3 rounded-lg border border-line bg-bg-soft/40 p-3 text-center">
                  <div className="text-[10px] uppercase tracking-wide text-slate-500">Target Opportunity Score</div>
                  <div className="text-3xl font-semibold text-helix-cyan">{sel.score}<span className="text-sm text-slate-500">/100</span></div>
                </div>
                <div className="section-title mb-2">Score breakdown</div>
                <div className="space-y-1.5">
                  {(sel.score_breakdown || []).map((b: any, i: number) => (
                    <div key={i} className="text-xs">
                      <div className="flex items-center justify-between text-slate-400"><span>{b.input}</span><span className="tabular-nums">{typeof b.value === 'number' ? b.value.toFixed(2) : b.value} × {b.weight ?? '—'}</span></div>
                      <div className="mt-0.5 h-1.5 overflow-hidden rounded-full bg-bg-hover">
                        <div className={`h-full ${b.contribution < 0 ? 'bg-helix-red' : 'bg-brand-500'}`} style={{ width: `${Math.min(100, Math.abs(b.contribution) * 4)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
                {sel.score_warnings?.length > 0 && <div className="mt-3 text-[11px] text-helix-amber">⚠ {sel.score_warnings.join('; ')}</div>}
              </div>
            )}
          </Panel>
        </div>
      )}
    </div>
  )
}
