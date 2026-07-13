import { useState } from 'react'
import { api, getRememberedRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

const KINDS = [
  { id: 'full_proposal_ko', label: '전체 제안서 (20 섹션)' },
  { id: 'peer_one_pager_ko', label: '1페이지 동료 검토' },
  { id: 'qa_defense_ko', label: '심사위원 Q&A 방어' },
]

export function ProposalStudio() {
  const [runId] = useState(getRememberedRunId)
  const [kind, setKind] = useState('full_proposal_ko')
  const [artifact, setArtifact] = useState<any | null>(null)
  const [handoff, setHandoff] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function generate() {
    setLoading(true); setErr(''); setHandoff(null)
    try { setArtifact(await api.proposalGenerate(kind, runId || undefined)) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  async function loadHandoff() {
    setLoading(true); setErr(''); setArtifact(null)
    try { setHandoff(await api.hwpxHandoff(runId || undefined)) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  function copy(text: string) { navigator.clipboard?.writeText(text) }

  return (
    <div>
      <PageHeader
        icon={<Icon name="FileEdit" size={22} />}
        title="Proposal Studio"
        subtitle="Generate the Korean competition proposal, peer-review one-pager, and judge Q&A defense from the latest real run — every artifact passes the multilingual safety lint. Or produce paste-ready HWPX blocks for the official template."
        actions={<div className="flex gap-2">
          <select className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
            {KINDS.map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}
          </select>
          <button className="btn-primary" onClick={generate} disabled={loading}><Icon name="Sparkles" size={14} /> Generate</button>
          <button className="btn-secondary" onClick={loadHandoff} disabled={loading}><Icon name="ClipboardCopy" size={14} /> HWPX blocks</button>
        </div>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Generating…" /> : (
        <div className="space-y-4">
          {artifact && (
            <Panel>
              <div className="mb-2 flex items-center justify-between">
                <div className="section-title">{artifact.title}</div>
                <div className="flex items-center gap-2">
                  <Badge tone={artifact.export_safe ? 'green' : 'red'}>{artifact.safety_lint?.status || (artifact.export_safe ? 'PASS' : 'BLOCKED')}</Badge>
                  <button className="btn-ghost text-xs" onClick={() => copy(artifact.markdown)}><Icon name="Copy" size={12} /> Copy</button>
                </div>
              </div>
              <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap rounded-lg bg-black/30 p-3 text-xs leading-relaxed text-slate-300">{artifact.markdown}</pre>
            </Panel>
          )}
          {handoff && (
            <Panel>
              <div className="mb-2 flex items-center justify-between">
                <div className="section-title">HWPX Handoff — {handoff.block_count} paste-ready blocks</div>
                <Badge tone={handoff.all_blocks_export_safe ? 'green' : 'red'}>{handoff.all_blocks_export_safe ? 'all export-safe' : 'review'}</Badge>
              </div>
              <div className="mb-2 text-[11px] text-slate-500">{handoff.instructions}</div>
              <div className="space-y-2">
                {handoff.blocks.map((b: any) => (
                  <div key={b.id} className="rounded-lg border border-white/8 p-2">
                    <div className="mb-1 flex items-center justify-between">
                      <span className="text-xs font-medium text-slate-200">{b.heading}</span>
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-slate-500">{b.char_count}자</span>
                        <button className="btn-ghost text-xs" onClick={() => copy(b.paste_text)}><Icon name="Copy" size={12} /></button>
                      </div>
                    </div>
                    <pre className="max-h-40 overflow-auto whitespace-pre-wrap text-[11px] text-slate-400">{b.paste_text}</pre>
                  </div>
                ))}
              </div>
            </Panel>
          )}
          {!artifact && !handoff && <Empty>Generate a proposal artifact or load the HWPX handoff blocks.</Empty>}
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}
