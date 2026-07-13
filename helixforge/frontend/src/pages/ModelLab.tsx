import { useEffect, useState } from 'react'
import { api, getRememberedRunId, SOURCE_META } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

const TABS = ['Datasets', 'CPU Models', 'Ligand Screen'] as const
type Tab = typeof TABS[number]

const DEMO_SMILES = ['CCO', 'CCN', 'CCC', 'CCCC', 'c1ccccc1', 'c1ccncc1', 'CC(=O)O', 'CCOC(=O)C',
  'CCCCO', 'CCCCN', 'c1ccc(O)cc1', 'c1ccc(N)cc1', 'CCCCCC', 'CCCCCCO']
const DEMO_DATASET = DEMO_SMILES.map((s, i) => ({ smiles: s, label: i % 2, standard_type: 'IC50', standard_units: 'nM' }))
const EGFR_REFS = ['COc1cc2ncnc(Nc3ccc(F)c(Cl)c3)c2cc1OCCCN1CCOCC1', 'C#Cc1cccc(Nc2ncnc3cc(OCCOC)c(OCCOC)cc23)c1']

function SBadge({ type }: { type?: string }) {
  if (!type) return null
  const m = SOURCE_META[type] || { label: type, tone: 'slate' }
  return <Badge tone={m.tone}>{m.label}</Badge>
}

export function ModelLab() {
  const [runId] = useState(getRememberedRunId)
  const [tab, setTab] = useState<Tab>('Datasets')
  const [datasets, setDatasets] = useState<any[]>([])
  const [models, setModels] = useState<any[]>([])
  const [modelAvail, setModelAvail] = useState<any>(null)
  const [screen, setScreen] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')

  async function load() {
    setLoading(true); setErr('')
    try {
      const [datasetsResult, modelsResult] = await Promise.allSettled([
        api.datasetsList(runId || undefined), api.cpuModelsList(runId || undefined),
      ])
      setDatasets(datasetsResult.status === 'fulfilled' ? datasetsResult.value.datasets || [] : [])
      if (modelsResult.status === 'fulfilled') {
        setModels(modelsResult.value.models || []); setModelAvail(modelsResult.value.availability)
      } else {
        setModels([]); setModelAvail(null)
      }
      const failures = [datasetsResult, modelsResult].filter((result): result is PromiseRejectedResult => result.status === 'rejected')
      if (failures.length) setErr(failures.map((failure) => failure.reason instanceof Error ? failure.reason.message : String(failure.reason)).join('; '))
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function curate() {
    setBusy('curate'); setErr('')
    try { await api.datasetCurate({ records: DEMO_DATASET, dataset_name: 'demo', exploratory: true, run_id: runId || undefined }); await load() }
    catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }
  async function train() {
    setBusy('train'); setErr('')
    try { await api.cpuModelTrain({ dataset: DEMO_DATASET, task: 'classification', endpoint: 'demo', run_id: runId || undefined }); await load() }
    catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }
  async function runScreen() {
    setBusy('screen'); setErr('')
    try { setScreen(await api.ligandScreen({ candidates: [...EGFR_REFS, 'CCO', 'c1ccccc1'], reference_ligands: EGFR_REFS, target: 'EGFR', run_id: runId || undefined })) }
    catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="FlaskConical" size={22} />}
        title="Data & Model Lab"
        subtitle="CPU-first dataset curation, honest scikit-learn QSAR baselines (scaffold split + leakage checks + applicability), and ligand-based screening. No GPU required; degrades honestly if sklearn is absent."
        actions={<button className="btn-secondary" onClick={load} disabled={loading}><Icon name="RefreshCw" size={14} /> Refresh</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      <div className="mb-4 flex gap-1">
        {TABS.map((t) => (
          <button key={t} onClick={() => setTab(t)}
            className={`rounded px-3 py-1 text-xs ${tab === t ? 'bg-brand-400/15 text-brand-200 border border-brand-400/40' : 'text-slate-400 border border-transparent hover:text-slate-200'}`}>{t}</button>
        ))}
      </div>

      {loading ? <Spinner label="Loading…" /> : (
        <div className="space-y-4">
          {tab === 'Datasets' && (
            <Panel>
              <div className="mb-2 flex items-center justify-between">
                <div className="section-title">Dataset Registry</div>
                <button className="btn-primary" onClick={curate} disabled={busy !== ''}>
                  {busy === 'curate' ? <Icon name="Loader2" size={14} className="animate-spin" /> : <Icon name="Plus" size={14} />} Curate demo dataset
                </button>
              </div>
              {datasets.length === 0 ? <Empty>No datasets yet. Curate a demo dataset to begin.</Empty> : (
                <div className="overflow-x-auto"><table className="w-full text-xs">
                  <thead><tr className="text-left text-slate-500"><th className="py-1 pr-2">Name</th><th className="pr-2">Quality</th>
                    <th className="pr-2">Valid</th><th className="pr-2">Split</th><th className="pr-2">Leakage</th><th className="pr-2">Trainable</th><th>License</th></tr></thead>
                  <tbody>{datasets.map((d) => (
                    <tr key={d.id} className="border-t border-white/5">
                      <td className="py-1.5 pr-2 text-slate-200">{d.dataset_name}</td>
                      <td className="pr-2">{d.quality_score}</td>
                      <td className="pr-2 text-slate-400">{d.valid_smiles_count}/{d.row_count}</td>
                      <td className="pr-2 text-slate-400">{d.split_strategy}</td>
                      <td className="pr-2"><Badge tone={d.duplicate_leakage_count ? 'red' : 'green'}>{d.duplicate_leakage_count}</Badge></td>
                      <td className="pr-2"><Badge tone={d.trainable ? 'green' : 'amber'}>{String(d.trainable)}</Badge></td>
                      <td><Badge tone={d.license_status === 'PASS' ? 'green' : 'amber'}>{d.license_status}</Badge></td>
                    </tr>))}</tbody>
                </table></div>
              )}
            </Panel>
          )}

          {tab === 'CPU Models' && (
            <Panel>
              <div className="mb-2 flex items-center justify-between">
                <div className="section-title">CPU Baseline Models {modelAvail && !modelAvail.sklearn && <Badge tone="amber">sklearn absent → configured-not-run</Badge>}</div>
                <button className="btn-primary" onClick={train} disabled={busy !== ''}>
                  {busy === 'train' ? <Icon name="Loader2" size={14} className="animate-spin" /> : <Icon name="Play" size={14} />} Train demo baseline
                </button>
              </div>
              {models.length === 0 ? <Empty>No models. Train a demo baseline (CPU, scaffold split, honest metrics).</Empty> : (
                <div className="space-y-2">{models.map((m) => (
                  <div key={m.id} className="rounded border border-white/5 p-2 text-xs">
                    <div className="flex items-center gap-2">
                      <span className="text-slate-200">{m.model_family} · {m.task} · {m.endpoint}</span>
                      <SBadge type={m.source_type} />
                      <Badge tone={m.validation_status === 'VALIDATED_BASELINE' ? 'green' : 'amber'} className="ml-auto">{m.validation_status}</Badge>
                    </div>
                    <div className="mt-1 text-slate-400">split: {m.split_strategy} · leakage: {m.duplicate_leakage_count} · metrics: {JSON.stringify(m.metrics)}</div>
                    {m.sample_size_warning && <div className="text-helix-amber">⚠ {m.sample_size_warning}</div>}
                    <div className="text-[11px] text-slate-500">{(m.limitations || [])[0]}</div>
                  </div>))}</div>
              )}
            </Panel>
          )}

          {tab === 'Ligand Screen' && (
            <Panel>
              <div className="mb-2 flex items-center justify-between">
                <div className="section-title">Ligand-based Screening</div>
                <button className="btn-primary" onClick={runScreen} disabled={busy !== ''}>
                  {busy === 'screen' ? <Icon name="Loader2" size={14} className="animate-spin" /> : <Icon name="Play" size={14} />} Screen vs EGFR refs
                </button>
              </div>
              {!screen ? <Empty>Run a screen against known EGFR reference ligands.</Empty> : (
                <div className="space-y-2 text-xs">
                  <div className="rounded bg-helix-amber/10 border border-helix-amber/30 px-2 py-1 text-helix-amber">{screen.banner}</div>
                  <div className="text-slate-400">valid {screen.valid_count}/{screen.candidate_count} · best similarity {screen.best_similarity} · roles {JSON.stringify(screen.recommendation_counts)}</div>
                  {screen.top_candidates?.map((c: any, i: number) => (
                    <div key={i} className="flex items-center gap-2 border-t border-white/5 py-1">
                      <span className="flex-1 truncate text-slate-300">{c.smiles}</span>
                      <span className="text-slate-500">sim {c.nearest_reference_similarity}</span>
                      <Badge tone={c.recommendation === 'KNOWN_LIKE_PRIORITY' ? 'green' : c.recommendation === 'REJECT_INVALID' ? 'red' : 'amber'}>{c.recommendation}</Badge>
                    </div>
                  ))}
                  <div className="text-[11px] text-slate-500">{(screen.limitations || [])[0]}</div>
                </div>
              )}
            </Panel>
          )}
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}
