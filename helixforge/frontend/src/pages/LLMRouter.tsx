import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'
import { ReasoningBadge } from '@/components/ReasoningBadge'

const MODE_BUTTONS: { mode: string; label: string }[] = [
  { mode: 'HYBRID_LLM_DEV', label: 'Use Sonnet for development' },
  { mode: 'HYBRID_FABLE_FINAL', label: 'Use Fable only for final snapshot' },
  { mode: 'DETERMINISTIC_ONLY', label: 'Disable LLM / deterministic mode' },
]

export function LLMRouter() {
  const [config, setConfig] = useState<any | null>(null)
  const [health, setHealth] = useState<any | null>(null)
  const [router, setRouter] = useState<any | null>(null)
  const [costs, setCosts] = useState<any | null>(null)
  const [templates, setTemplates] = useState<any | null>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const [smoke, setSmoke] = useState<any | null>(null)

  async function load() {
    setLoading(true); setErr('')
    try {
      const results = await Promise.allSettled([
        api.llmConfig(), api.llmHealth(), api.llmRouter(), api.llmCosts(), api.llmPromptTemplates(),
      ])
      const setters = [setConfig, setHealth, setRouter, setCosts, setTemplates]
      results.forEach((result, index) => {
        setters[index](result.status === 'fulfilled' ? result.value : null)
      })
      const failures = results.filter((result): result is PromiseRejectedResult => result.status === 'rejected')
      if (failures.length) setErr(failures.map((failure) => failure.reason instanceof Error ? failure.reason.message : String(failure.reason)).join('; '))
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function setMode(mode: string) {
    setBusy(mode); setErr('')
    try {
      const cfg = await api.llmSetMode(mode)
      if (cfg && cfg.mode) setConfig(cfg)
      setRouter(await api.llmRouter())
      setHealth(await api.llmHealth())
    } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  async function resetSession() {
    setBusy('reset'); setErr('')
    try { await api.llmResetSession(); setCosts(await api.llmCosts()) }
    catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  async function runSmoke() {
    setBusy('smoke'); setErr(''); setSmoke(null)
    try { setSmoke(await api.llmLiveSmoke({ max_cost_usd: 0.05 })) }
    catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  const routes = router?.routes || {}
  const budget = costs?.budget || {}
  const byModel = costs?.by_model || {}
  const tmplList = templates?.templates || []

  return (
    <div>
      <PageHeader
        icon={<Icon name="Cpu" size={22} />}
        title="LLM Router"
        subtitle="Hybrid reasoning layer: Fable/Sonnet handle planning, hypotheses and critique only — scientific facts always come from tools. Model routing, budget guard, provenance and a deterministic fallback are governed here."
        actions={<button className="btn-secondary" onClick={load} disabled={loading}><Icon name="RefreshCw" size={14} /> Reload</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Loading LLM configuration…" /> : (
        <div className="space-y-4">
          {/* Mode + API key status */}
          <Panel>
            <div className="mb-3 flex items-center justify-between">
              <div className="section-title">Mode &amp; availability</div>
              <Badge tone={config?.llm_available ? 'green' : 'slate'}>{config?.mode || 'UNKNOWN'}</Badge>
            </div>
            {!config ? <Empty>No LLM configuration.</Empty> : (
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded border border-white/8 p-3 text-xs">
                  <div className="text-slate-500">Current mode</div>
                  <div className="mt-0.5 text-slate-200">{config.mode}</div>
                  <div className="mt-2 text-slate-500">API key present</div>
                  <div className="mt-0.5"><Badge tone={config.api_key_present ? 'green' : 'slate'}>{config.api_key_present ? 'yes' : 'no'}</Badge></div>
                  <div className="mt-2 text-slate-500">API key (masked)</div>
                  <div className="mt-0.5 font-mono text-slate-300">{config.api_key_display || '—'}</div>
                </div>
                <div className="rounded border border-white/8 p-3 text-xs">
                  <div className="text-slate-500">LLM available</div>
                  <div className="mt-0.5"><Badge tone={config.llm_available ? 'green' : 'amber'}>{config.llm_available ? 'available' : 'unavailable'}</Badge></div>
                  <div className="mt-2 text-slate-500">Availability reason</div>
                  <div className="mt-0.5 text-slate-300">{config.availability_reason || '—'}</div>
                </div>
              </div>
            )}
            <div className="mt-3 flex flex-wrap gap-2">
              {MODE_BUTTONS.map((b) => (
                <button key={b.mode} className={`btn-secondary ${config?.mode === b.mode ? 'ring-1 ring-brand-400' : ''}`} disabled={!!busy} onClick={() => setMode(b.mode)}>
                  {busy === b.mode ? '…' : b.label}
                </button>
              ))}
            </div>
            <div className="mt-2 text-[11px] text-slate-500">Note: mode selects the routing policy, but the environment governs live LLM availability — a mode may resolve to deterministic fallback if no key/SDK is present.</div>
          </Panel>

          {/* Model routing table */}
          <Panel>
            <div className="mb-2 section-title">Model routing</div>
            {!Object.keys(routes).length ? <Empty>No routes defined for this mode.</Empty> : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-slate-500">
                    <th className="py-1 pr-2">Purpose</th><th className="pr-2">Model</th><th className="pr-2">Max output tokens</th><th>Final Fable</th>
                  </tr></thead>
                  <tbody>
                    {Object.entries(routes).map(([purpose, r]: any) => (
                      <tr key={purpose} className="border-t border-white/5">
                        <td className="py-1 pr-2 text-slate-300">{purpose}</td>
                        <td className="pr-2 text-slate-200">{r?.model || '—'}</td>
                        <td className="pr-2 text-slate-400">{r?.max_output_tokens ?? '—'}</td>
                        <td>{r?.is_final_fable ? <Badge tone="violet">final</Badge> : <span className="text-slate-500">—</span>}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Budget guard + cost ledger */}
          <Panel>
            <div className="mb-3 flex items-center justify-between">
              <div className="section-title">Budget guard &amp; cost ledger</div>
              <button className="btn-secondary" disabled={!!busy} onClick={resetSession}><Icon name="RotateCcw" size={14} /> {busy === 'reset' ? '…' : 'Reset session'}</button>
            </div>
            <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
              <StatCard label="Session $" value={fmtUsd(costs?.session_total_usd)} tone="cyan" />
              <StatCard label="Day $" value={fmtUsd(costs?.day_total_usd)} tone="cyan" />
              <StatCard label="Max $/run" value={fmtUsd(budget.max_cost_per_run_usd)} tone="slate" />
              <StatCard label="Max $/day" value={fmtUsd(budget.max_cost_per_day_usd)} tone="slate" />
              <StatCard label="Calls" value={costs?.call_count ?? 0} tone="violet" />
              <StatCard label="Cache hits" value={costs?.cache_hits ?? 0} tone="green" />
            </div>
            {Object.keys(byModel).length > 0 && (
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                {Object.entries(byModel).map(([m, v]: any) => (
                  <div key={m} className="rounded border border-white/8 px-2 py-1">
                    <span className="text-slate-300">{m}</span>: <span className="text-slate-400">{fmtUsd(typeof v === 'object' ? v?.cost_usd : v)}</span>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          {/* LLM health */}
          <Panel>
            <div className="mb-3 flex items-center justify-between">
              <div className="section-title">LLM health</div>
              <Badge tone={health?.safe ? 'green' : 'amber'}>{health?.safe ? 'safe' : 'review'}</Badge>
            </div>
            {!health ? <Empty>No health data.</Empty> : (
              <div className="grid gap-2 text-xs sm:grid-cols-2">
                <div className="text-slate-500">Mode: <span className="text-slate-300">{health.mode}</span></div>
                <div className="text-slate-500">LLM available: <Badge tone={health.llm_available ? 'green' : 'amber'}>{health.llm_available ? 'yes' : 'no'}</Badge></div>
                <div className="text-slate-500">SDK installed: <Badge tone={health.sdk_installed ? 'green' : 'slate'}>{health.sdk_installed ? 'yes' : 'no'}</Badge></div>
                <div className="text-slate-500">Reason: <span className="text-slate-300">{health.availability_reason || '—'}</span></div>
              </div>
            )}
          </Panel>

          {/* Prompt templates */}
          <Panel>
            <div className="mb-2 section-title">Prompt templates</div>
            {!tmplList.length ? <Empty>No prompt templates registered.</Empty> : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-slate-500">
                    <th className="py-1 pr-2">ID</th><th className="pr-2">Version</th><th className="pr-2">Purpose</th><th>Hash</th>
                  </tr></thead>
                  <tbody>
                    {tmplList.map((t: any, i: number) => (
                      <tr key={t.id || i} className="border-t border-white/5">
                        <td className="py-1 pr-2 text-slate-300">{t.id}</td>
                        <td className="pr-2 text-slate-400">{t.version}</td>
                        <td className="pr-2 text-slate-400">{t.purpose}</td>
                        <td className="font-mono text-slate-500">{(t.hash || '').slice(0, 12)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Panel>

          {/* Live smoke test */}
          <Panel>
            <div className="mb-2 flex items-center justify-between">
              <div className="section-title">Live LLM smoke test</div>
              <button className="btn-primary" disabled={!!busy} onClick={runSmoke}><Icon name="Zap" size={14} /> {busy === 'smoke' ? 'Running…' : 'Run tiny live LLM smoke test'}</button>
            </div>
            <div className="text-[11px] text-slate-500">Runs a minimal capped-cost call (max $0.05). It will report disabled unless the environment explicitly enables live LLM calls — that is expected.</div>
            {smoke && (
              <div className="mt-3 rounded border border-white/8 p-3 text-xs">
                <div className="flex items-center gap-2">
                  <Badge tone={smoke.ran ? 'green' : 'slate'}>{smoke.ran ? 'ran' : 'did not run'}</Badge>
                  {smoke.reasoning_source_type && <ReasoningBadge type={smoke.reasoning_source_type} />}
                </div>
                <div className="mt-1 text-slate-400">{smoke.reason || smoke.message || '—'}</div>
              </div>
            )}
          </Panel>

          <div className="text-[11px] text-slate-500">Deterministic fallback: when the LLM is unavailable, over budget, or blocked, the router returns a deterministic result tagged with an explicit reasoning source so provenance is never hidden.</div>
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}

function fmtUsd(v: any): string {
  const n = typeof v === 'number' ? v : Number(v)
  if (!isFinite(n)) return '—'
  return `$${n.toFixed(n < 1 ? 4 : 2)}`
}
