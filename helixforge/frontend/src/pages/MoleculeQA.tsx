import { useEffect, useState } from 'react'
import { api, getRememberedRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

type Tab = 'activity' | 'medchem' | 'applicability'

const STATUS_TONE: Record<string, string> = {
  FAVORABLE_FOR_REVIEW: 'green', NEEDS_OPTIMIZATION: 'amber', STRUCTURAL_ALERT_REVIEW: 'red',
  LOW_CONFIDENCE: 'slate', REJECT_INVALID: 'red',
  IN_DOMAIN: 'green', BORDERLINE: 'amber', OUT_OF_DOMAIN: 'red', UNKNOWN: 'slate',
}

const pendingAnalyses = new Map<string, Promise<any>>()

function requestAnalysis(tab: Tab, runId: string): Promise<any> {
  const key = `${runId || '__latest__'}:${tab}`
  const existing = pendingAnalyses.get(key)
  if (existing) return existing
  const request = (tab === 'activity' ? api.activitiesNormalizeRun(runId || undefined)
    : tab === 'medchem' ? api.medchemReviewRun(runId || undefined)
    : api.applicabilityRun(runId || undefined))
    .finally(() => pendingAnalyses.delete(key))
  pendingAnalyses.set(key, request)
  return request
}

export function MoleculeQA() {
  const [runId] = useState(getRememberedRunId)
  const [tab, setTab] = useState<Tab>('activity')
  const [data, setData] = useState<Record<Tab, any>>({ activity: null, medchem: null, applicability: null })
  const [pending, setPending] = useState<Record<Tab, boolean>>({ activity: false, medchem: false, applicability: false })
  const [errors, setErrors] = useState<Record<Tab, string>>({ activity: '', medchem: '', applicability: '' })

  async function load(t: Tab) {
    setTab(t); setErrors((current) => ({ ...current, [t]: '' }))
    if (data[t] || pending[t]) return
    setPending((current) => ({ ...current, [t]: true }))
    try {
      const res = await requestAnalysis(t, runId)
      setData((d) => ({ ...d, [t]: res }))
    } catch (e: unknown) {
      setErrors((current) => ({ ...current, [t]: e instanceof Error ? e.message : 'Molecule analysis failed.' }))
    } finally { setPending((current) => ({ ...current, [t]: false })) }
  }

  useEffect(() => {
    let active = true
    setData({ activity: null, medchem: null, applicability: null })
    setErrors({ activity: '', medchem: '', applicability: '' })
    setPending({ activity: true, medchem: false, applicability: false })
    requestAnalysis('activity', runId)
      .then((result) => { if (active) setData((current) => ({ ...current, activity: result })) })
      .catch((reason: unknown) => { if (active) setErrors((current) => ({ ...current, activity: reason instanceof Error ? reason.message : 'Molecule analysis failed.' })) })
      .finally(() => { if (active) setPending((current) => ({ ...current, activity: false })) })
    return () => { active = false }
  }, [runId])

  const cur = data[tab]
  const loading = pending[tab]
  const err = errors[tab]
  return (
    <div>
      <PageHeader
        icon={<Icon name="FlaskConical" size={22} />}
        title="Molecule QA (Expert)"
        subtitle="Professional per-molecule review: assay-activity normalization & reliability, medicinal-chemistry drug-likeness + structural alerts, and applicability domain. In-silico only — supports expert review, not a determination of activity, safety, or efficacy."
      />
      <div className="mb-4 flex gap-2">
        {(['activity', 'medchem', 'applicability'] as Tab[]).map((t) => (
          <button key={t} className={`btn-secondary ${tab === t ? 'ring-1 ring-brand-400' : ''}`} disabled={pending[t]} onClick={() => load(t)}>
            {t === 'activity' ? 'Activity Normalization' : t === 'medchem' ? 'MedChem Review' : 'Applicability Domain'}
          </button>
        ))}
      </div>
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Analyzing molecules…" /> : !cur ? <Empty>No data — run a pipeline first.</Empty> : (
        <div className="space-y-4">
          {tab === 'activity' && <ActivityView data={cur} />}
          {tab === 'medchem' && <MedChemView data={cur} />}
          {tab === 'applicability' && <ApplicabilityView data={cur} />}
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}

function ActivityView({ data }: { data: any }) {
  const rows = data.normalized || []
  return (
    <Panel>
      <div className="mb-2 flex items-center justify-between">
        <div className="section-title">Activity normalization</div>
        <div className="flex gap-2 text-xs text-slate-400">
          <Badge tone={data.unsupported_units ? 'amber' : 'green'}>{data.unsupported_units} unsupported units</Badge>
          <Badge tone={data.unknown_assay_confidence ? 'amber' : 'green'}>{data.unknown_assay_confidence} unknown assay conf.</Badge>
        </div>
      </div>
      {Object.keys(data.endpoint_summaries || {}).length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2 text-xs">
          {Object.entries(data.endpoint_summaries).map(([g, s]: any) => (
            <div key={g} className="rounded border border-white/8 px-2 py-1">
              <span className="text-slate-300">{g}</span>: n={s.count}, median pChEMBL={s.median_pchembl ?? '—'}, outliers={s.outliers}
            </div>
          ))}
        </div>
      )}
      {!rows.length ? <Empty>No activity records in the latest run.</Empty> : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-slate-500"><th className="py-1 pr-2">Molecule</th><th className="pr-2">Endpoint</th><th className="pr-2">Rel</th><th className="pr-2">nM</th><th className="pr-2">pChEMBL</th><th className="pr-2">Unit</th><th className="pr-2">Reliability</th><th>Flags</th></tr></thead>
            <tbody>
              {rows.slice(0, 100).map((r: any, i: number) => (
                <tr key={i} className="border-t border-white/5">
                  <td className="py-1 pr-2 text-slate-300">{r.molecule_chembl_id || '—'}</td>
                  <td className="pr-2 text-slate-400">{r.comparable_group}</td>
                  <td className="pr-2 text-slate-400">{r.standard_relation || '—'}</td>
                  <td className="pr-2 text-slate-400">{r.normalized_value_nm ?? '—'}</td>
                  <td className="pr-2 text-slate-400">{r.normalized_pchembl ?? '—'}</td>
                  <td className="pr-2"><Badge tone={r.unit_conversion_status === 'OK' ? 'green' : 'amber'}>{r.unit_conversion_status}</Badge></td>
                  <td className="pr-2 text-slate-300">{r.reliability_score}</td>
                  <td className="text-slate-500">{r.outlier_flag ? '⚠ outlier ' : ''}{r.duplicate_group_id ? 'dup' : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}

function MedChemView({ data }: { data: any }) {
  const reviews = data.reviews || []
  return (
    <Panel>
      <div className="mb-2 flex items-center justify-between">
        <div className="section-title">Medicinal chemistry review</div>
        <div className="flex gap-2 text-xs">
          <Badge tone={data.rdkit_available ? 'green' : 'amber'}>RDKit {data.rdkit_available ? 'on' : 'off'}</Badge>
          <Badge tone={data.pains_available ? 'green' : 'amber'}>PAINS {data.pains_available ? 'on' : 'off'}</Badge>
        </div>
      </div>
      {!reviews.length ? <Empty>No molecules in the latest run.</Empty> : (
        <div className="space-y-2">
          {reviews.slice(0, 60).map((r: any, i: number) => (
            <div key={i} className="rounded border border-white/8 p-2 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-slate-200">{r.label || r.molecule_id}</span>
                <Badge tone={STATUS_TONE[r.medchem_status] || 'slate'}>{r.medchem_status}</Badge>
              </div>
              {r.descriptor_summary && (
                <div className="mt-1 text-slate-500">MW {r.descriptor_summary.mol_weight} · cLogP {r.descriptor_summary.logp} · HBD {r.descriptor_summary.hbd} · HBA {r.descriptor_summary.hba} · TPSA {r.descriptor_summary.tpsa} · QED {r.descriptor_summary.qed ?? '—'}</div>
              )}
              {(r.pains_alerts?.length > 0 || r.reactive_group_alerts?.length > 0) && (
                <div className="mt-1 text-helix-red">alerts: {[...(r.pains_alerts || []), ...(r.reactive_group_alerts || [])].join(', ')}</div>
              )}
              <div className="mt-1 text-slate-400">{r.expert_recommendation}</div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  )
}

function ApplicabilityView({ data }: { data: any }) {
  const results = data.results || []
  return (
    <Panel>
      <div className="mb-2 flex items-center justify-between">
        <div className="section-title">Applicability domain</div>
        <div className="text-xs text-slate-400">reference: {data.reference_set_source}</div>
      </div>
      {!results.length ? <Empty>No molecules in the latest run.</Empty> : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead><tr className="text-left text-slate-500"><th className="py-1 pr-2">Molecule</th><th className="pr-2">NN sim</th><th className="pr-2">Mean top-k</th><th className="pr-2">Status</th><th className="pr-2">Conf. Δ</th><th>Warnings</th></tr></thead>
            <tbody>
              {results.slice(0, 100).map((r: any, i: number) => (
                <tr key={i} className="border-t border-white/5">
                  <td className="py-1 pr-2 text-slate-300">{r.label || r.molecule_id}</td>
                  <td className="pr-2 text-slate-400">{r.nearest_neighbor_similarity ?? '—'}</td>
                  <td className="pr-2 text-slate-400">{r.mean_similarity_top_k ?? '—'}</td>
                  <td className="pr-2"><Badge tone={STATUS_TONE[r.domain_status] || 'slate'}>{r.domain_status}</Badge></td>
                  <td className="pr-2 text-slate-400">{r.confidence_adjustment}</td>
                  <td className="text-slate-500">{(r.warnings || []).join('; ') || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Panel>
  )
}
