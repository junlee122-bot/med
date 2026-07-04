import { useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, Field, PageHeader, Panel, Spinner } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'
import { ReasoningBadge } from '@/components/ReasoningBadge'

const MODES = ['DETERMINISTIC_ONLY', 'HYBRID_LLM_DEV', 'HYBRID_FABLE_FINAL', 'RECORDED_HYBRID_REPLAY']

const STATUS_TONE: Record<string, string> = {
  COMPLETED: 'green', SUCCESS: 'green', OK: 'green', PARTIAL: 'amber', FAILED: 'red', ERROR: 'red',
}
const SEVERITY_TONE: Record<string, string> = {
  BLOCKING: 'red', HIGH: 'red', MAJOR: 'amber', MEDIUM: 'amber', MINOR: 'slate', LOW: 'slate', INFO: 'cyan',
}

export function Hybrid() {
  const [mode, setMode] = useState('HYBRID_LLM_DEV')
  const [targetQuery, setTargetQuery] = useState('EGFR')
  const [condition, setCondition] = useState('non-small cell lung cancer')
  const [scenarioId, setScenarioId] = useState('egfr_nsclc')
  const [budgetUsd, setBudgetUsd] = useState(2.0)
  const [maxPubmed, setMaxPubmed] = useState(4)
  const [toggles, setToggles] = useState<Record<string, boolean>>({
    run_true_rediscovery: true,
    run_optimization_loop: true,
    run_semantic_critic: true,
    create_hybrid_snapshot: false,
  })
  const [running, setRunning] = useState(false)
  const [err, setErr] = useState('')
  const [result, setResult] = useState<any | null>(null)

  function toggle(key: string) { setToggles((t) => ({ ...t, [key]: !t[key] })) }

  async function run() {
    setRunning(true); setErr(''); setResult(null)
    try {
      setResult(await api.runHybridPipeline({
        mode, target_query: targetQuery, condition, scenario_id: scenarioId,
        budget_usd: budgetUsd, max_pubmed_results: maxPubmed, ...toggles,
      }))
    } catch (e: any) { setErr(e.message) } finally { setRunning(false) }
  }

  const calls = result?.llm_calls || []
  const hyps = result?.hypotheses || []
  const criticItems = result?.semantic_critic?.items || result?.semantic_critic_items || []
  const byModel = result?.cost_summary?.by_model || {}

  return (
    <div>
      <PageHeader
        icon={<Icon name="Workflow" size={22} />}
        title="Hybrid Agentic Pipeline"
        subtitle="Run the hybrid pipeline where Fable/Sonnet handle planning, hypotheses and critique only — scientific facts always come from tools. Provenance is tagged on every reasoning step."
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}

      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        {/* Controls */}
        <div className="space-y-4">
          <Panel>
            <div className="mb-3 section-title">Configuration</div>
            <div className="space-y-3">
              <Field label="Mode">
                <select className="input" value={mode} onChange={(e) => setMode(e.target.value)}>
                  {MODES.map((m) => <option key={m} value={m}>{m}</option>)}
                </select>
              </Field>
              <Field label="Target query"><input className="input" value={targetQuery} onChange={(e) => setTargetQuery(e.target.value)} /></Field>
              <Field label="Condition"><input className="input" value={condition} onChange={(e) => setCondition(e.target.value)} /></Field>
              <Field label="Scenario ID"><input className="input" value={scenarioId} onChange={(e) => setScenarioId(e.target.value)} /></Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Budget (USD)"><input type="number" step="0.5" min={0} className="input" value={budgetUsd} onChange={(e) => setBudgetUsd(Number(e.target.value))} /></Field>
                <Field label="Max PubMed"><input type="number" min={1} max={20} className="input" value={maxPubmed} onChange={(e) => setMaxPubmed(Number(e.target.value))} /></Field>
              </div>
              <div className="space-y-1.5">
                {['run_true_rediscovery', 'run_optimization_loop', 'run_semantic_critic', 'create_hybrid_snapshot'].map((k) => (
                  <label key={k} className="flex items-center gap-2 text-xs text-slate-300">
                    <input type="checkbox" checked={!!toggles[k]} onChange={() => toggle(k)} />
                    {k.replace(/_/g, ' ')}
                  </label>
                ))}
              </div>
              <button className="btn-primary w-full" disabled={running} onClick={run}>
                <Icon name="Play" size={14} /> {running ? 'Running…' : 'Run Hybrid Agentic Pipeline'}
              </button>
              <div className="text-[11px] text-slate-500">This can take ~30s. Fable is used for planning/hypotheses/critique only; scientific facts come from tools.</div>
            </div>
          </Panel>
        </div>

        {/* Results */}
        <div className="space-y-4">
          {running ? <Spinner label="Running hybrid pipeline (~30s)…" /> : !result ? (
            <Panel><Empty>Configure and run the hybrid pipeline to see results.</Empty></Panel>
          ) : (
            <>
              <Panel>
                <div className="mb-2 section-title">Run summary</div>
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="text-slate-500">mode</span> <Badge tone="violet">{result.global_mode || result.mode || mode}</Badge>
                  <span className="text-slate-500">status</span> <Badge tone={STATUS_TONE[result.status] || 'slate'}>{result.status || '—'}</Badge>
                  {result.run_id && <span className="text-slate-500">run <span className="font-mono text-slate-400">{result.run_id}</span></span>}
                </div>
                <div className="mt-3 grid gap-2 text-xs sm:grid-cols-3">
                  <div className="flex items-center gap-1.5"><span className="text-slate-500">plan</span> <ReasoningBadge type={result.plan_source} /></div>
                  <div className="flex items-center gap-1.5"><span className="text-slate-500">hypotheses</span> <ReasoningBadge type={result.hypothesis_reasoning_source} /></div>
                  <div className="flex items-center gap-1.5"><span className="text-slate-500">critic</span> <ReasoningBadge type={result.semantic_critic_source} /></div>
                </div>
              </Panel>

              <Panel>
                <div className="mb-2 section-title">LLM calls ({calls.length})</div>
                {!calls.length ? <Empty>No LLM calls recorded.</Empty> : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead><tr className="text-left text-slate-500">
                        <th className="py-1 pr-2">Model</th><th className="pr-2">Purpose</th><th className="pr-2">Reasoning source</th><th>Fallback</th>
                      </tr></thead>
                      <tbody>
                        {calls.map((c: any, i: number) => (
                          <tr key={i} className="border-t border-white/5">
                            <td className="py-1 pr-2 text-slate-200">{c.model || '—'}</td>
                            <td className="pr-2 text-slate-400">{c.purpose || '—'}</td>
                            <td className="pr-2"><ReasoningBadge type={c.reasoning_source_type} /></td>
                            <td>{c.fallback_used ? <Badge tone="amber">yes</Badge> : <span className="text-slate-500">no</span>}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </Panel>

              <Panel>
                <div className="mb-2 section-title">Hypotheses ({hyps.length})</div>
                {!hyps.length ? <Empty>No hypotheses generated.</Empty> : (
                  <div className="space-y-2">
                    {hyps.map((h: any, i: number) => (
                      <div key={i} className="rounded border border-white/8 p-2 text-xs">
                        <div className="text-slate-200">{h.statement || h.hypothesis || '—'}</div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-slate-500">
                          {h.evidence_grade && <Badge tone="cyan">{h.evidence_grade}</Badge>}
                          {(h.evidence_ids || []).length > 0 && <span>evidence: {(h.evidence_ids || []).join(', ')}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </Panel>

              <Panel>
                <div className="mb-2 section-title">Semantic critic ({criticItems.length})</div>
                {!criticItems.length ? <Empty>No critic findings.</Empty> : (
                  <div className="space-y-2">
                    {criticItems.map((it: any, i: number) => (
                      <div key={i} className="rounded border border-white/8 p-2 text-xs">
                        <div className="flex items-center gap-2">
                          <Badge tone={SEVERITY_TONE[it.severity] || 'slate'}>{it.severity || '—'}</Badge>
                          <span className="text-slate-500">{it.category || '—'}</span>
                        </div>
                        <div className="mt-1 text-slate-300">{it.issue_summary || '—'}</div>
                      </div>
                    ))}
                  </div>
                )}
              </Panel>

              <Panel>
                <div className="mb-2 section-title">Cost summary</div>
                <div className="text-xs text-slate-400">Session total: <span className="text-slate-200">{fmtUsd(result.cost_summary?.session_total_usd)}</span></div>
                {Object.keys(byModel).length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-2 text-xs">
                    {Object.entries(byModel).map(([m, v]: any) => (
                      <div key={m} className="rounded border border-white/8 px-2 py-1">
                        <span className="text-slate-300">{m}</span>: <span className="text-slate-400">{fmtUsd(typeof v === 'object' ? v?.cost_usd : v)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Panel>

              {(result.warnings || []).length > 0 && (
                <Panel>
                  <div className="mb-2 section-title">Warnings</div>
                  <ul className="space-y-1 text-xs text-helix-amber">
                    {result.warnings.map((w: string, i: number) => <li key={i}>⚠ {w}</li>)}
                  </ul>
                </Panel>
              )}

              {result.disclaimer && <div className="text-[11px] text-slate-500">{result.disclaimer}</div>}
            </>
          )}
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      </div>
    </div>
  )
}

function fmtUsd(v: any): string {
  const n = typeof v === 'number' ? v : Number(v)
  if (!isFinite(n)) return '—'
  return `$${n.toFixed(n < 1 ? 4 : 2)}`
}
