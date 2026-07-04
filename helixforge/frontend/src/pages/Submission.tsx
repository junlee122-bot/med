import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'

const ARTIFACTS = [
  { key: 'korean_proposal', label: 'Korean Proposal Draft', icon: 'FileText' },
  { key: 'technical_appendix', label: 'Technical Appendix', icon: 'Cpu' },
  { key: 'ethics_appendix', label: 'Ethics & Safety Appendix', icon: 'ShieldCheck' },
  { key: 'peer_review_summary', label: 'Peer Review Summary (KO)', icon: 'Users' },
  { key: 'demo_script', label: 'Final Demo Script', icon: 'Presentation' },
  { key: 'judge_readme', label: 'Judge README', icon: 'BookOpen' },
]

const RISKS = [
  'Live API dependency (mitigated by recorded snapshot replay)',
  'AutoDock Vina not installed → CONFIGURED_BUT_NOT_RUN',
  'REINVENT4 not installed → CONFIGURED_BUT_NOT_RUN',
  'TDC used as evaluation substrate (no fitted per-candidate ADMET predictor by default)',
  'Regulatory checklist is heuristic (RAG adapter planned)',
  'No wet-lab or clinical validation is claimed',
]

function download(name: string, content: string, type = 'text/markdown') {
  const blob = new Blob([content], { type }); const url = URL.createObjectURL(blob)
  const a = document.createElement('a'); a.href = url; a.download = name; a.click(); URL.revokeObjectURL(url)
}

export function Submission() {
  const [active, setActive] = useState<any | null>(null)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const [check, setCheck] = useState<any | null>(null)

  useEffect(() => { api.submissionCheck().then(setCheck).catch(() => {}) }, [])

  async function gen(key: string) {
    setBusy(key); setErr('')
    try { setActive(await api.submissionGenerate(key)) } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }
  async function bundle() {
    setBusy('bundle'); setErr('')
    try {
      const b = await api.submissionBundle()
      download('helixforge-submission-bundle.json', JSON.stringify(b, null, 2), 'application/json')
      setCheck(await api.submissionCheck())
    } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="Package" size={22} />}
        title="Submission Center"
        subtitle="One place to prepare the competition package. Every artifact embeds disclaimers, labels not-run tools honestly, and excludes secrets."
        actions={<button className="btn-primary" onClick={bundle} disabled={!!busy}><Icon name="Archive" size={15} /> {busy === 'bundle' ? 'Building…' : 'Generate full bundle (JSON)'}</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        <div className="space-y-4">
          <Panel>
            <div className="section-title mb-3">One-click generation</div>
            <div className="space-y-2">
              {ARTIFACTS.map((a) => (
                <button key={a.key} onClick={() => gen(a.key)} disabled={!!busy}
                  className={`flex w-full items-center justify-between rounded-lg border p-2.5 text-left ${active?.type === a.key ? 'border-helix-cyan/50 bg-helix-cyan/5' : 'border-line bg-bg-soft/40 hover:bg-bg-hover/60'}`}>
                  <span className="flex items-center gap-2 text-sm text-slate-200"><Icon name={a.icon} size={14} className="text-helix-cyan" /> {a.label}</span>
                  {busy === a.key ? <Spinner label="" /> : <Icon name="ChevronRight" size={14} className="text-slate-500" />}
                </button>
              ))}
            </div>
          </Panel>
          <Panel>
            <div className="section-title mb-2">Final sanity check</div>
            {!check ? <Spinner label="" /> : (
              <div className="space-y-1">
                {check.checklist.map((c: any) => (
                  <div key={c.item} className="flex items-center gap-2 text-xs">
                    <Icon name={c.ok ? 'CheckCircle2' : 'AlertCircle'} size={13} className={c.ok ? 'text-brand-400' : 'text-helix-amber'} />
                    <span className={c.ok ? 'text-slate-300' : 'text-helix-amber'}>{c.item}</span>
                  </div>
                ))}
                <div className="mt-2 flex gap-2 text-[11px]">
                  <Badge tone={check.safety_lint === 'PASS' ? 'green' : 'amber'}>safety {check.safety_lint}</Badge>
                  <Badge tone={check.evidence_lint === 'PASS' ? 'green' : 'amber'}>evidence {check.evidence_lint}</Badge>
                </div>
              </div>
            )}
          </Panel>
          <Panel>
            <div className="section-title mb-2">Submission risk warnings</div>
            <ul className="space-y-1 text-[11px] text-slate-400">
              {RISKS.map((r) => <li key={r} className="flex gap-2"><Icon name="AlertTriangle" size={12} className="mt-0.5 flex-shrink-0 text-helix-amber" /> {r}</li>)}
            </ul>
          </Panel>
        </div>

        <Panel>
          {!active ? <Empty>Generate an artifact to preview and download it.</Empty> : (
            <div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2 font-medium text-slate-100"><Icon name="FileText" size={16} className="text-helix-cyan" /> {active.title}</div>
                <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => download(`${active.type}.md`, active.markdown)}><Icon name="Download" size={13} /> .md</button>
              </div>
              <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-black/30 p-4 font-mono text-[11px] leading-relaxed text-slate-300">{active.markdown}</pre>
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
