import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'

export function ScenarioMatrix() {
  const [scenarios, setScenarios] = useState<any[]>([])
  const [selected, setSelected] = useState<string[]>(['egfr-nsclc', 'braf-melanoma'])
  const [results, setResults] = useState<any[]>([])
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => { api.listScenarios().then((r) => setScenarios(r.scenarios)).catch((e) => setErr(e.message)) }, [])

  function toggle(id: string) {
    setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id])
  }
  async function run() {
    setBusy(true); setErr(''); setResults([])
    try { setResults((await api.runScenarioMatrix(selected)).results) } catch (e: any) { setErr(e.message) } finally { setBusy(false) }
  }
  function exportCsv() {
    const cols = ['scenario_name', 'status', 'selected_target', 'pubmed_evidence_count', 'clinicaltrials_count', 'valid_molecule_count', 'runtime_seconds', 'rediscovery_success']
    const csv = [cols.join(','), ...results.map((r) => cols.map((c) => JSON.stringify(r[c] ?? '')).join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' }); const url = URL.createObjectURL(blob)
    const a = document.createElement('a'); a.href = url; a.download = 'scenario-matrix.csv'; a.click(); URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="Grid3x3" size={22} />}
        title="Scenario Matrix"
        subtitle="Retrieval & pipeline-robustness benchmark across disease/target presets. Runs real tools; when a target is not found it says so honestly — no scientific claim is made."
        actions={
          <>
            {results.length > 0 && <button className="btn-secondary" onClick={exportCsv}><Icon name="Download" size={14} /> CSV</button>}
            <button className="btn-primary" onClick={run} disabled={busy || selected.length === 0}><Icon name="Play" size={15} /> {busy ? `Running ${selected.length}…` : `Run matrix (${selected.length})`}</button>
          </>
        }
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      <div className="mb-3 rounded-lg border border-helix-amber/30 bg-helix-amber/10 px-3 py-2 text-[11px] text-helix-amber">
        Each scenario runs a real agentic pipeline (~10–20s each). Live APIs may be slow; select a few at a time.
      </div>

      <Panel className="mb-4">
        <div className="section-title mb-2">Presets</div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          {scenarios.map((s) => (
            <button key={s.id} onClick={() => toggle(s.id)}
              className={`rounded-lg border p-2.5 text-left ${selected.includes(s.id) ? 'border-helix-cyan/50 bg-helix-cyan/5' : 'border-line bg-bg-soft/40 hover:bg-bg-hover/60'}`}>
              <div className="flex items-center gap-2 text-xs font-medium text-slate-200">
                <span className={`h-2 w-2 rounded-full ${selected.includes(s.id) ? 'bg-helix-cyan' : 'bg-slate-600'}`} /> {s.name}
              </div>
              <div className="mt-0.5 text-[10px] text-slate-500">{s.target_query} · {s.status}</div>
            </button>
          ))}
        </div>
      </Panel>

      {busy && <Spinner label="Running scenario pipelines against live tools…" />}
      {!busy && results.length === 0 && <Empty>Select presets and run the matrix to benchmark retrieval robustness.</Empty>}
      {results.length > 0 && (
        <Panel>
          <div className="mb-2 flex items-center justify-between">
            <div className="section-title">Results</div>
            <Badge tone="green">{results.filter((r) => r.rediscovery_success).length}/{results.length} rediscovery</Badge>
          </div>
          <div className="overflow-auto rounded-lg border border-line">
            <table className="w-full text-left text-xs">
              <thead className="bg-bg-soft text-slate-400"><tr>
                <th className="p-2">Scenario</th><th className="p-2">Status</th><th className="p-2">Target</th><th className="p-2">PubMed</th><th className="p-2">Trials</th><th className="p-2">Valid mol</th><th className="p-2">Runtime</th><th className="p-2">Rediscovery</th>
              </tr></thead>
              <tbody>
                {results.map((r, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="p-2 font-medium text-slate-200">{r.scenario_name}</td>
                    <td className="p-2"><Badge tone={r.status === 'complete' ? 'green' : r.status === 'error' ? 'red' : 'amber'}>{r.status}</Badge></td>
                    <td className="p-2 text-slate-400">{r.selected_target || '—'}</td>
                    <td className="p-2 text-slate-400">{r.pubmed_evidence_count ?? '—'}</td>
                    <td className="p-2 text-slate-400">{r.clinicaltrials_count ?? '—'}</td>
                    <td className="p-2 text-slate-400">{r.valid_molecule_count ?? '—'}</td>
                    <td className="p-2 text-slate-400">{r.runtime_seconds ? `${r.runtime_seconds}s` : '—'}</td>
                    <td className="p-2">{r.rediscovery_success ? <Icon name="CheckCircle2" size={14} className="text-brand-400" /> : <Icon name="Minus" size={14} className="text-slate-500" />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-2 text-[11px] text-slate-500">Rediscovery = a druggable single human protein from the queried family was selected with bioactivity. Not a scientific validation.</div>
        </Panel>
      )}
    </div>
  )
}
