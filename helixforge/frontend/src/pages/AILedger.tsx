import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'
import { MetricTile } from '@/components/agentic'

const TYPE_TONE: Record<string, string> = {
  DETERMINISTIC_AGENT: 'green', LLM_CALL: 'violet', HUMAN_INPUT: 'cyan', REPORT_TEMPLATE: 'slate', SAFETY_LINT: 'amber',
}

export function AILedger() {
  const [rows, setRows] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  async function load() {
    setLoading(true)
    try { setRows((await api.aiLedger()).interactions) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const byType: Record<string, number> = {}
  rows.forEach((r) => { byType[r.interaction_type] = (byType[r.interaction_type] || 0) + 1 })
  const llmUsed = (byType['LLM_CALL'] || 0) > 0

  function exportJson() {
    const blob = new Blob([JSON.stringify(rows, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob); const a = document.createElement('a')
    a.href = url; a.download = 'ai-interaction-ledger.json'; a.click(); URL.revokeObjectURL(url)
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="ScrollText" size={22} />}
        title="AI Interaction Ledger"
        subtitle="Ethics transparency: every agent/AI interaction is logged with type, provider, model, and settings. The default runtime is deterministic (no external LLM). Full secrets and private chain-of-thought are never stored."
        actions={<button className="btn-secondary" onClick={exportJson} disabled={!rows.length}><Icon name="Download" size={14} /> Export JSON</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}

      <div className="mb-4 rounded-lg border border-line bg-bg-soft/40 p-3 text-xs text-slate-400">
        <Icon name="ShieldCheck" size={13} className="mr-1 inline text-brand-400" />
        {llmUsed ? 'This project included optional LLM calls; provider/model/settings are logged.' : 'All recorded runs used deterministic agents — no external LLM calls. This is logged honestly for research-ethics transparency.'}
      </div>

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricTile label="Interactions" value={rows.length} />
        <MetricTile label="Deterministic" value={byType['DETERMINISTIC_AGENT'] || 0} tone="green" />
        <MetricTile label="LLM calls" value={byType['LLM_CALL'] || 0} tone={llmUsed ? 'violet' : 'slate'} />
        <MetricTile label="Human notes" value={byType['HUMAN_INPUT'] || 0} />
      </div>

      {loading ? <Spinner label="Loading ledger…" /> : rows.length === 0 ? (
        <Empty>No interactions yet. Run the agentic pipeline to populate the ledger.</Empty>
      ) : (
        <Panel>
          <div className="max-h-[560px] overflow-auto">
            <table className="w-full text-left text-xs">
              <thead className="sticky top-0 bg-bg-soft text-slate-400"><tr>
                <th className="p-2">Type</th><th className="p-2">Provider / Model</th><th className="p-2">Prompt summary</th><th className="p-2">Input hash</th><th className="p-2">Time</th>
              </tr></thead>
              <tbody>
                {rows.slice(0, 200).map((r) => (
                  <tr key={r.id} className="border-t border-line">
                    <td className="p-2"><Badge tone={TYPE_TONE[r.interaction_type] || 'slate'}>{r.interaction_type.replace('_', ' ')}</Badge></td>
                    <td className="p-2 text-slate-400">{r.provider} · {r.model_name}</td>
                    <td className="p-2 text-slate-400">{(r.user_prompt_summary || '').slice(0, 48)}</td>
                    <td className="p-2 font-mono text-[10px] text-slate-500">{(r.input_hash || '').slice(0, 18)}</td>
                    <td className="p-2 text-slate-500">{r.timestamp ? new Date(r.timestamp).toLocaleTimeString() : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </div>
  )
}
