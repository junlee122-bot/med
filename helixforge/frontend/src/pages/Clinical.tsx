import { useState } from 'react'
import { api } from '@/lib/api'
import type { ClinicalTrialItem, Envelope } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, Field, PageHeader, Panel, SourceBadge, Spinner } from '@/components/ui'

const CHECKLIST = [
  ['Target rationale documented', 'met', 'ASSUMPTION', 'low'],
  ['Candidate identity documented', 'met', 'ASSUMPTION', 'low'],
  ['Nonclinical safety data', 'gap', 'ASSUMPTION', 'high'],
  ['ADMET predictions', 'partial', 'ASSUMPTION', 'medium'],
  ['Clinical precedent searched', 'met', 'REAL_TOOL_OUTPUT', 'low'],
  ['Endpoint strategy', 'partial', 'ASSUMPTION', 'medium'],
  ['Biomarker strategy', 'partial', 'ASSUMPTION', 'medium'],
  ['CMC / manufacturing', 'gap', 'ASSUMPTION', 'medium'],
  ['Human expert review required', 'met', 'ASSUMPTION', 'low'],
  ['No medical advice provided', 'met', 'ASSUMPTION', 'low'],
]
const STATUS_TONE: Record<string, string> = { met: 'green', partial: 'amber', gap: 'red', not_assessed: 'slate' }
const RISK_TONE: Record<string, string> = { low: 'green', medium: 'amber', high: 'red' }

export function Clinical() {
  const [cond, setCond] = useState('non-small cell lung cancer')
  const [q, setQ] = useState('EGFR')
  const [res, setRes] = useState<(Envelope & { items: ClinicalTrialItem[] }) | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function search() {
    setLoading(true); setErr('')
    try { setRes(await api.clinicaltrials(cond, q, 10)) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }

  const phases: Record<string, number> = {}
  ;(res?.items || []).forEach((t) => { const p = t.phase || 'N/A'; phases[p] = (phases[p] || 0) + 1 })

  return (
    <div>
      <PageHeader
        icon={<Icon name="Stethoscope" size={22} />}
        title="Clinical & Regulatory Strategy"
        subtitle="Real ClinicalTrials.gov precedent + a high-level regulatory readiness checklist. Planning only — not medical, legal, or regulatory advice; no dosage."
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      <Panel className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[220px] flex-1"><Field label="Condition"><input className="input" value={cond} onChange={(e) => setCond(e.target.value)} /></Field></div>
          <div className="min-w-[160px] flex-1"><Field label="Intervention / target"><input className="input" value={q} onChange={(e) => setQ(e.target.value)} /></Field></div>
          <button className="btn-primary" onClick={search} disabled={loading}><Icon name="Search" size={15} /> Search precedent</button>
        </div>
      </Panel>

      <div className="grid gap-4 lg:grid-cols-[1fr_380px]">
        <Panel>
          <div className="mb-3 section-title">Trial precedent matrix</div>
          {loading && <Spinner label="Querying ClinicalTrials.gov v2…" />}
          {!loading && !res && <Empty>Search to load real trial precedent.</Empty>}
          {res && (<>
            <div className="mb-2 flex items-center gap-2 text-xs text-slate-400"><SourceBadge type={res.source_type} /><span>{res.output_summary}</span></div>
            {res.items.length === 0 ? <Empty>No trials.</Empty> : (
              <div className="overflow-auto rounded-lg border border-line">
                <table className="w-full text-left text-xs">
                  <thead className="bg-bg-soft text-slate-400"><tr><th className="p-2">NCT</th><th className="p-2">Title</th><th className="p-2">Phase</th><th className="p-2">Status</th></tr></thead>
                  <tbody>
                    {res.items.map((t) => (
                      <tr key={t.nct_id} className="border-t border-line">
                        <td className="p-2"><a href={t.url} target="_blank" rel="noreferrer" className="text-helix-cyan hover:underline">{t.nct_id}</a></td>
                        <td className="p-2 text-slate-300">{t.brief_title}</td>
                        <td className="p-2 text-slate-400">{t.phase || 'N/A'}</td>
                        <td className="p-2 text-slate-400">{t.status}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {Object.keys(phases).length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                {Object.entries(phases).map(([p, n]) => <span key={p} className="chip border-line-bright bg-bg-hover text-slate-300">{p}: {n}</span>)}
              </div>
            )}
          </>)}
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg border border-line bg-bg-soft/40 p-3">
              <div className="section-title mb-1">Population logic</div>
              <div className="text-xs text-slate-400">Biomarker-selected {cond} population altered for {q} (expert-defined).</div>
            </div>
            <div className="rounded-lg border border-line bg-bg-soft/40 p-3">
              <div className="section-title mb-1">Key risks</div>
              <div className="text-xs text-slate-400">On-target toxicity · acquired resistance · biomarker/endpoint mismatch · competitive landscape.</div>
            </div>
          </div>
        </Panel>

        <Panel>
          <div className="mb-3 section-title">Regulatory readiness checklist</div>
          <div className="space-y-1.5">
            {CHECKLIST.map(([item, status, source, risk]) => (
              <div key={item} className="flex items-center justify-between gap-2 rounded border border-line bg-bg-soft/40 p-2">
                <span className="text-xs text-slate-300">{item}</span>
                <div className="flex items-center gap-1">
                  <Badge tone={RISK_TONE[risk]}>{risk}</Badge>
                  <Badge tone={STATUS_TONE[status]}>{status}</Badge>
                </div>
              </div>
            ))}
          </div>
          <div className="mt-2 text-[11px] text-slate-500">Source labels: REAL_TOOL_OUTPUT for the precedent search; ASSUMPTION for heuristic items. A guidance-document RAG adapter is planned (FUTURE_RAG_ADAPTER). No approval path is claimed.</div>
        </Panel>
      </div>
      <div className="mt-4"><Disclaimer text="This is high-level research planning, not clinical, medical, legal, or regulatory advice. No dosage or treatment recommendation is provided." /></div>
    </div>
  )
}
