import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, PageHeader, Panel, SourceBadge, Spinner, StatCard } from '@/components/ui'

export function TDCBench() {
  const [datasets, setDatasets] = useState<any[]>([])
  const [installed, setInstalled] = useState<boolean | null>(null)
  const [selected, setSelected] = useState('Caco2_Wang')
  const [loaded, setLoaded] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [listLoading, setListLoading] = useState(true)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.tdcDatasets().then((r) => { setDatasets(r.datasets || []); setInstalled(r.installed) }).catch((e) => setErr(e.message)).finally(() => setListLoading(false))
  }, [])

  async function load(ds: string, task: string) {
    setSelected(ds); setLoading(true); setErr(''); setLoaded(null)
    try { setLoaded(await api.tdcLoad(ds, task)) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="Gauge" size={22} />}
        title="TDC Evaluation Bench"
        subtitle="Load real Therapeutics Data Commons ADME/Tox datasets (PyTDC). Row counts, columns, and scaffold splits come from the actual downloaded data — the basis for honest ADMET model evaluation."
        actions={installed != null && <Badge tone={installed ? 'green' : 'amber'}>{installed ? 'PyTDC installed' : 'PyTDC not installed'}</Badge>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <Panel>
          <div className="section-title mb-3">ADME / Tox datasets</div>
          {listLoading ? <Spinner label="Listing TDC datasets…" /> : (
            <div className="space-y-2">
              {datasets.map((d) => (
                <div key={d.name} className={`rounded-lg border p-3 ${selected === d.name ? 'border-helix-cyan/50 bg-helix-cyan/5' : 'border-line bg-bg-soft/40'}`}>
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-slate-100">{d.name}</div>
                    <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => load(d.name, d.task)} disabled={loading}><Icon name="Download" size={13} /> Load</button>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">{d.group} · {d.task} · {d.endpoint}</div>
                  {d.description && <div className="mt-1 text-[11px] text-slate-500">{d.description}</div>}
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel>
          <div className="section-title mb-3">Loaded dataset</div>
          {loading && <Spinner label={`Loading ${selected} via PyTDC (may download on first use)…`} />}
          {!loading && !loaded && <Empty>Select a dataset and click Load to fetch real rows, columns, and split summary.</Empty>}
          {loaded && (
            <div>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <SourceBadge type={loaded.source_type} />
                <span className="text-sm font-medium text-slate-200">{loaded.dataset_name || selected}</span>
                <Badge tone="slate">{loaded.task}</Badge>
              </div>
              {loaded.errors?.length > 0 && <div className="mb-3"><ErrorNote error={loaded.errors.join('; ')} /></div>}
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                <StatCard label="Rows" value={loaded.row_count ?? 0} />
                <StatCard label="Train" value={loaded.split_summary?.train ?? '—'} />
                <StatCard label="Valid" value={loaded.split_summary?.valid ?? '—'} />
                <StatCard label="Test" value={loaded.split_summary?.test ?? '—'} />
              </div>
              {loaded.columns?.length > 0 && (
                <div className="mt-3 text-xs text-slate-400">Columns: {loaded.columns.map((c: string) => <span key={c} className="chip border-line-bright bg-bg-hover text-slate-300 mr-1">{c}</span>)}</div>
              )}
              {loaded.preview?.length > 0 && (
                <div className="mt-4 overflow-auto rounded-lg border border-line">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-bg-soft text-slate-400"><tr>{Object.keys(loaded.preview[0]).map((k) => <th key={k} className="p-2">{k}</th>)}</tr></thead>
                    <tbody>
                      {loaded.preview.slice(0, 8).map((row: any, i: number) => (
                        <tr key={i} className="border-t border-line">
                          {Object.keys(loaded.preview[0]).map((k) => <td key={k} className="p-2 font-mono text-[10px] text-slate-400">{String(row[k]).slice(0, 40)}</td>)}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
              <div className="mt-4 rounded-lg border border-line bg-bg-soft/50 p-3 text-xs text-slate-400">
                <span className="font-medium text-slate-300">Evaluation use · </span>
                Loaded metadata (splits, size, endpoint) grounds a reproducible ADMET benchmark. Train an open-source predictor (e.g. ChemProp) on the train split and report ROC-AUC / RMSE on the held-out test split — no fabricated metrics.
              </div>
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
