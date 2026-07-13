import { useState } from 'react'
import { api, getRememberedRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

const DOC_TYPES: [string, string][] = [
  ['SYSTEM_CARD', 'System Card'], ['DATA_CARD', 'Data Card'], ['MODEL_CARD', 'Model Card'],
  ['EVALUATION_CARD', 'Evaluation Card'], ['RISK_REGISTER', 'Risk Register'],
  ['VALIDATION_PROTOCOL', 'Validation Protocol'], ['TRACEABILITY_MATRIX', 'Traceability Matrix'],
  ['WHAT_WE_DO_NOT_CLAIM', 'What We Do NOT Claim'], ['REAL_VS_REPLAY_VS_NOT_RUN', 'Real vs Replay vs Not-Run'],
  ['SCIENTIFIC_REVIEWER_BRIEF', 'Scientific Reviewer Brief'], ['BUSINESS_REVIEWER_BRIEF', 'Business Reviewer Brief'],
  ['MODEL_GOVERNANCE_APPENDIX', 'Model Governance Appendix'], ['DATA_GOVERNANCE_APPENDIX', 'Data Governance Appendix'],
]

export function ProfessionalDocs() {
  const [runId] = useState(getRememberedRunId)
  const [doc, setDoc] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function gen(kind: string) {
    setLoading(true); setErr('')
    try { setDoc(await api.professionalDocsGenerate(kind, runId || undefined)) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  async function whitepaper(lang: string) {
    setLoading(true); setErr('')
    try { const wp = await api.whitepaperGenerate(lang, runId || undefined); setDoc({ ...wp, title: wp.title || `Whitepaper (${lang})`, markdown: wp.markdown }) }
    catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  function copy(t: string) { navigator.clipboard?.writeText(t) }

  return (
    <div>
      <PageHeader icon={<Icon name="FileStack" size={22} />} title="Professional Documentation"
        subtitle="Audit-ready documentation: model / data / system cards, risk register, validation protocol, traceability matrix, reviewer briefs, a 25-section scientific whitepaper (KO/EN), and the 'What We Do NOT Claim' sheet." />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
        <div className="space-y-3">
          <Panel>
            <div className="mb-2 section-title">Generate document</div>
            <div className="flex flex-col gap-1.5">
              {DOC_TYPES.map(([k, label]) => (
                <button key={k} className="btn-secondary justify-start text-xs" onClick={() => gen(k)} disabled={loading}>{label}</button>
              ))}
            </div>
          </Panel>
          <Panel>
            <div className="mb-2 section-title">Scientific whitepaper</div>
            <div className="flex gap-2">
              <button className="btn-primary flex-1" onClick={() => whitepaper('en')} disabled={loading}>EN</button>
              <button className="btn-primary flex-1" onClick={() => whitepaper('ko')} disabled={loading}>KO</button>
            </div>
          </Panel>
        </div>
        <div>
          {loading ? <Spinner label="Generating…" /> : !doc ? <Empty>Select a document to generate.</Empty> : (
            <Panel>
              <div className="mb-2 flex items-center justify-between">
                <div className="section-title">{doc.title || doc.doc_type}</div>
                <div className="flex items-center gap-2">
                  {doc.source_type && <Badge tone="slate">{doc.source_type}</Badge>}
                  <button className="btn-ghost text-xs" onClick={() => copy(doc.markdown)}><Icon name="Copy" size={12} /> Copy</button>
                </div>
              </div>
              <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap rounded-lg bg-black/30 p-3 text-xs leading-relaxed text-slate-300">{doc.markdown}</pre>
            </Panel>
          )}
        </div>
      </div>
      <div className="mt-4"><Disclaimer text={HUMAN_RESPONSIBILITY} /></div>
    </div>
  )
}
