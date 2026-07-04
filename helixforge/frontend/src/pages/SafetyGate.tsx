import { useState } from 'react'
import { api, HUMAN_RESPONSIBILITY } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, ErrorNote, Field, PageHeader, Panel, SourceBadge, Spinner } from '@/components/ui'

const POLICY = [
  ['No wet-lab protocols', 'Reaction recipes, conditions, and purification procedures are never generated.'],
  ['No synthesis routes', 'Step-by-step synthesis routes and reagent lists are withheld by policy. Only high-level feasibility summaries are produced.'],
  ['No dosage / medical advice', 'The system provides research decision support, not clinical, medical, legal, or regulatory advice.'],
  ['No toxicity enhancement', 'Requests to increase toxicity, lethality, delivery, evasion, or misuse are blocked. Toxicity is screened, never optimized.'],
  ['No controlled-material guidance', 'Controlled or hazardous material production guidance is refused; structural alerts quarantine the candidate.'],
  ['Provenance & audit', 'Every tool result is labeled by source type and logged to the audit trail; fabricated data is not permitted.'],
]

const EXAMPLES = [
  { label: 'Benign molecule', smiles: 'CC(=O)Oc1ccccc1C(=O)O' },
  { label: 'Overclaim text', text: 'This candidate is a validated cure with proven efficacy and 100% safe results.' },
]

export function SafetyGate() {
  const [text, setText] = useState('')
  const [smiles, setSmiles] = useState('')
  const [res, setRes] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function screen(payload?: { text?: string; smiles?: string }) {
    setLoading(true); setErr(''); setRes(null)
    try { setRes(await api.safetyScreen(payload ?? { text: text || undefined, smiles: smiles || undefined, label: 'manual screen' })) }
    catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }

  const tone = res?.status === 'PASS' ? 'green' : res?.status === 'BLOCKED' ? 'red' : 'amber'
  return (
    <div>
      <PageHeader
        icon={<Icon name="ShieldCheck" size={22} />}
        title="Safety Gate"
        subtitle="The safety adapter screens text outputs and molecule records, quarantines hazardous content, and enforces the no-synthesis-route policy across the whole system."
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}

      <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
        <Panel>
          <div className="section-title mb-3">Safety policy</div>
          <div className="grid gap-2 sm:grid-cols-2">
            {POLICY.map(([t, d]) => (
              <div key={t} className="rounded-lg border border-line bg-bg-soft/40 p-3">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-200"><Icon name="ShieldCheck" size={14} className="text-brand-400" /> {t}</div>
                <div className="mt-1 text-xs text-slate-400">{d}</div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel>
          <div className="section-title mb-3">Run screen</div>
          <Field label="Text output to screen"><textarea className="input h-20" value={text} onChange={(e) => setText(e.target.value)} placeholder="Paste model output text…" /></Field>
          <div className="mt-3"><Field label="Or molecule SMILES"><input className="input font-mono text-xs" value={smiles} onChange={(e) => setSmiles(e.target.value)} placeholder="e.g. CCO" /></Field></div>
          <button className="btn-primary mt-3 w-full" onClick={() => screen()} disabled={loading}><Icon name="ScanSearch" size={15} /> Screen</button>
          <div className="mt-3 flex flex-wrap gap-2">
            {EXAMPLES.map((e) => (
              <button key={e.label} className="btn-secondary !px-2 !py-1 text-xs" onClick={() => screen({ text: e.text, smiles: e.smiles })}>{e.label}</button>
            ))}
          </div>
          {loading && <div className="mt-3"><Spinner label="Screening…" /></div>}
          {res && (
            <div className="mt-4 rounded-lg border border-line bg-bg-soft/40 p-3">
              <div className="mb-2 flex flex-wrap items-center gap-2"><SourceBadge type={res.source_type} /><Badge tone={tone}>{res.status}</Badge></div>
              {res.categories?.length > 0 && <div className="mb-2 text-xs text-slate-400">Categories: {res.categories.join(', ')}</div>}
              {res.redacted_summary && <div className="text-xs text-slate-300">{res.redacted_summary}</div>}
              {res.safe_alternative && <div className="mt-2 rounded border border-brand-500/30 bg-brand-500/5 p-2 text-xs text-brand-300"><span className="font-medium">Safe alternative: </span>{res.safe_alternative}</div>}
            </div>
          )}
        </Panel>
      </div>
      <div className="mt-4"><Disclaimer text={HUMAN_RESPONSIBILITY} /></div>
    </div>
  )
}
