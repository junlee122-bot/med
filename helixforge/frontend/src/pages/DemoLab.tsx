import { useState } from 'react'
import { api, HUMAN_RESPONSIBILITY } from '@/lib/api'
import type { ErrorInjectionResult } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'
import { RevisionCard, MetricTile } from '@/components/agentic'

const SCENARIOS = [
  { key: 'invalid_smiles', label: 'Invalid SMILES correction', icon: 'FlaskConical', desc: 'Inject an invalid structure; RDKit rejects it and the Critic excludes it from ranking.' },
  { key: 'fake_citation', label: 'Fake citation correction', icon: 'BookX', desc: 'Inject a fabricated PMID; the Citation Verifier fails it and the Critic demotes it.' },
  { key: 'overclaim', label: 'Overclaim correction', icon: 'MessageSquareWarning', desc: 'Inject "validated cure / proven efficacy"; the Critic rewrites to guarded language.' },
  { key: 'contradictory_evidence', label: 'Contradictory evidence', icon: 'GitCompareArrows', desc: 'Inject a contradictory item; target/hypothesis confidence is recalculated with uncertainty stated.' },
  { key: 'tool_failure', label: 'Tool failure recovery', icon: 'PlugZap', desc: 'Inject a tool outage; the Orchestrator continues with partial results, honestly labeled.' },
  { key: 'safety_flag', label: 'Safety gate block', icon: 'ShieldX', desc: 'Inject a hazardous category; the Safety Auditor quarantines the candidate (non-actionable).' },
]

export function DemoLab() {
  const [result, setResult] = useState<ErrorInjectionResult | null>(null)
  const [active, setActive] = useState('')
  const [loading, setLoading] = useState('')
  const [error, setError] = useState('')

  async function run(scenario: string) {
    setLoading(scenario); setActive(scenario); setError(''); setResult(null)
    try { setResult(await api.runErrorInjectionDemo(scenario)) }
    catch (e: any) { setError(e.message) } finally { setLoading('') }
  }

  const m = result?.metric_summary || {}
  return (
    <div>
      <PageHeader
        icon={<Icon name="Wand2" size={22} />}
        title="Agentic Demo Lab"
        subtitle="One-click self-correction demonstrations. Each scenario injects a specific fault into a real pipeline run; the Critic detects it and records a visible before/after revision — nothing is faked."
      />
      {error && <div className="mb-4"><ErrorNote error={error} /></div>}

      <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
        <div className="space-y-2">
          {SCENARIOS.map((s) => (
            <button
              key={s.key}
              onClick={() => run(s.key)}
              disabled={!!loading}
              className={`w-full rounded-lg border p-3 text-left transition-colors ${active === s.key ? 'border-helix-cyan/50 bg-helix-cyan/5' : 'border-line bg-bg-soft/40 hover:bg-bg-hover/60'}`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
                  <Icon name={s.icon} size={15} className="text-helix-cyan" /> {s.label}
                </div>
                {loading === s.key ? <Spinner label="" /> : <Icon name="Play" size={14} className="text-slate-500" />}
              </div>
              <div className="mt-1 text-[11px] text-slate-500">{s.desc}</div>
            </button>
          ))}
        </div>

        <Panel>
          {loading && <Spinner label="Running real pipeline with the injected fault…" />}
          {!loading && !result && <Empty>Pick a scenario to run a real agentic pipeline with that fault injected and watch the correction.</Empty>}
          {result && (
            <div>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <Badge tone={result.corrected ? 'green' : 'amber'}>{result.corrected ? 'Corrected ✓' : 'No revision produced'}</Badge>
                <span className="font-mono text-[10px] text-slate-500">{result.workflow_run_id}</span>
              </div>

              {result.corrected && (result.before || result.after) && (
                <div className="mb-4 grid gap-2 sm:grid-cols-2">
                  <div className="rounded-lg border border-helix-red/30 bg-helix-red/5 p-3">
                    <div className="text-[10px] uppercase tracking-wide text-helix-red">Before (detected fault)</div>
                    <div className="mt-1 text-xs text-slate-300">{result.before || '—'}</div>
                  </div>
                  <div className="rounded-lg border border-brand-500/30 bg-brand-500/5 p-3">
                    <div className="text-[10px] uppercase tracking-wide text-brand-300">After (corrected)</div>
                    <div className="mt-1 text-xs text-slate-300">{result.after || '—'}</div>
                  </div>
                </div>
              )}

              <div className="mb-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
                <MetricTile label="Revisions" value={result.revision_events.length} tone="amber" />
                <MetricTile label="Self-correction" value={m.self_correction_rate ?? '—'} tone="green" />
                <MetricTile label="Mol. validity" value={m.molecule_validity_rate ?? '—'} />
                <MetricTile label="Real outputs" value={m.real_tool_output_count ?? '—'} tone="green" />
              </div>

              <div className="section-title mb-2">Revision events</div>
              {result.revision_events.length === 0 ? (
                <Empty>No revision recorded for this run.</Empty>
              ) : (
                <div className="space-y-2">{result.revision_events.map((r) => <RevisionCard key={r.id} rev={r} />)}</div>
              )}
            </div>
          )}
        </Panel>
      </div>
      <div className="mt-4"><Disclaimer text={HUMAN_RESPONSIBILITY} /></div>
    </div>
  )
}
