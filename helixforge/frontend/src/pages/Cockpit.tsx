import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { api, getRememberedRunId, HUMAN_RESPONSIBILITY, rememberRunId } from '@/lib/api'
import type { AgenticRunResult, ErrorInjections } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, SourceBadge, Spinner } from '@/components/ui'
import { AgentRunCard, RevisionCard, MetricTile } from '@/components/agentic'

const INJECTIONS: { key: keyof ErrorInjections; label: string; hint: string }[] = [
  { key: 'invalid_smiles', label: 'Invalid SMILES', hint: 'RDKit rejects → regenerate' },
  { key: 'fake_citation', label: 'Fake citation', hint: 'verifier fails → demote' },
  { key: 'overclaim', label: 'Overclaim', hint: 'critic rewrites language' },
  { key: 'contradictory_evidence', label: 'Contradictory evidence', hint: 'confidence recalculated' },
  { key: 'tool_failure', label: 'Tool failure', hint: 'fallback, partial results' },
  { key: 'safety_flag', label: 'Safety flag', hint: 'auditor blocks candidate' },
]

export function Cockpit() {
  const location = useLocation()
  const navigate = useNavigate()
  const [run, setRun] = useState<AgenticRunResult | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [inj, setInj] = useState<ErrorInjections>({})
  const [mode, setMode] = useState<'live' | 'replay'>('live')
  const [snaps, setSnaps] = useState<any[]>([])
  const [snapId, setSnapId] = useState('')
  const [replayInfo, setReplayInfo] = useState<{ warning: string; original: string } | null>(null)
  const [snapshotError, setSnapshotError] = useState('')

  useEffect(() => {
    let active = true
    api.listSnapshots()
      .then((r) => {
        if (!active) return
        setSnaps(r.snapshots)
        const b = r.snapshots.find((s: any) => s.is_builtin) || r.snapshots[0]
        if (b) setSnapId(b.id)
      })
      .catch((reason: unknown) => {
        if (active) setSnapshotError(reason instanceof Error ? reason.message : 'Failed to load snapshots.')
      })
    return () => { active = false }
  }, [])

  useEffect(() => {
    const queryRunId = new URLSearchParams(location.search).get('run')?.trim() || ''
    const runId = queryRunId || getRememberedRunId()
    if (!runId) {
      setRun(null)
      setReplayInfo(null)
      setError('')
      setLoading(false)
      return
    }

    let active = true
    setLoading(true)
    setError('')
    setRun(null)
    setReplayInfo(null)
    Promise.allSettled([api.getRun(runId), api.runAgents(runId), api.runRevisions(runId)])
      .then(([runResult, agentsResult, revisionsResult]) => {
        if (!active) return
        if (runResult.status === 'rejected') {
          throw runResult.reason
        }
        const stored = runResult.value
        const agentRuns = agentsResult.status === 'fulfilled' ? agentsResult.value.agent_runs : []
        const revisionEvents = revisionsResult.status === 'fulfilled' ? revisionsResult.value.revision_events : []
        setRun({
          ...stored,
          run_id: stored.run_id || stored.id || runId,
          project_id: stored.project_id || '',
          agent_runs: agentRuns,
          revision_events: revisionEvents,
          plan: stored.plan || { objective: 'Stored workflow run', stages: [] },
          steps: stored.steps || [],
          counts: stored.counts || {},
          metrics: stored.metrics || {},
          disclaimer: stored.disclaimer || HUMAN_RESPONSIBILITY,
        } as AgenticRunResult)
        rememberRunId(runId)
        const partialFailures = [agentsResult, revisionsResult].filter((result) => result.status === 'rejected').length
        if (partialFailures) setError(`Run restored with ${partialFailures} unavailable trace panel(s).`)
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : `Failed to restore run ${runId}.`)
      })
      .finally(() => { if (active) setLoading(false) })

    return () => { active = false }
  }, [location.search])

  async function exec() {
    setLoading(true); setError(''); setRun(null); setReplayInfo(null)
    try {
      if (mode === 'replay') {
        if (!snapId) throw new Error('No snapshot selected. Capture one on the Snapshots page.')
        const r = await api.replaySnapshot(snapId)
        setRun(r as AgenticRunResult)
        setReplayInfo({ warning: r.warning, original: r.original_run_id })
        rememberRunId(r.run_id)
        navigate(`/cockpit?run=${encodeURIComponent(r.run_id)}`, { replace: true })
      } else {
        const r = await api.runAgenticPipeline({
          condition: 'non-small cell lung cancer', target_query: 'EGFR', max_results: 6,
          create_reinvent_config: true, error_injections: inj,
        })
        setRun(r)
        rememberRunId(r.run_id)
        navigate(`/cockpit?run=${encodeURIComponent(r.run_id)}`, { replace: true })
      }
    } catch (e: unknown) { setError(e instanceof Error ? e.message : 'Failed to execute workflow.') } finally { setLoading(false) }
  }

  const m = run?.metrics || {}
  const anyInj = Object.values(inj).some(Boolean)

  return (
    <div>
      <PageHeader
        icon={<Icon name="Cpu" size={22} />}
        title="Agent Cockpit"
        subtitle="Run the real multi-agent pipeline: 17 agents call live tools, the Critic detects and corrects injected errors, and every step is observable — plan, tool calls, validation, confidence, revisions."
        actions={
          <>
            <div className="flex overflow-hidden rounded-lg border border-line text-xs">
              <button aria-pressed={mode === 'live'} onClick={() => setMode('live')} className={`px-3 py-2 ${mode === 'live' ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:bg-bg-hover'}`}>Live tools</button>
              <button aria-pressed={mode === 'replay'} onClick={() => setMode('replay')} className={`px-3 py-2 ${mode === 'replay' ? 'bg-helix-cyan/20 text-helix-cyan' : 'text-slate-400 hover:bg-bg-hover'}`}>Recorded replay</button>
            </div>
            {mode === 'replay' && (
              <select className="input !w-auto text-xs" value={snapId} onChange={(e) => setSnapId(e.target.value)}>
                {snaps.length === 0 && <option value="">no snapshot</option>}
                {snaps.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
              </select>
            )}
            <button className="btn-primary" disabled={loading} onClick={exec}>
              <Icon name="Play" size={15} /> {mode === 'replay' ? 'Replay snapshot' : 'Run agentic pipeline'}
            </button>
          </>
        }
      />
      {mode === 'replay' && (
        <div className="mb-4 rounded-lg border border-helix-cyan/40 bg-helix-cyan/10 px-3 py-2 text-xs text-helix-cyan">
          <Icon name="Info" size={13} className="mr-1 inline" />
          Recorded replay mode: outputs are labeled RECORDED_REAL_TOOL_OUTPUT. No live external API call is made — the demo-safe path for flaky networks.
        </div>
      )}
      {snapshotError && mode === 'replay' && <div className="mb-4"><ErrorNote error={snapshotError} /></div>}

      <Panel className="mb-4">
        <div className="mb-2 flex items-center justify-between">
          <div className="section-title">Error injection · self-correction demo</div>
          {anyInj && <Badge tone="amber">{Object.values(inj).filter(Boolean).length} enabled</Badge>}
        </div>
        <div className="grid grid-cols-2 gap-2 md:grid-cols-3">
          {INJECTIONS.map((it) => (
            <button
              key={it.key}
              aria-pressed={inj[it.key]}
              onClick={() => setInj((s) => ({ ...s, [it.key]: !s[it.key] }))}
              className={`rounded-lg border p-2.5 text-left transition-colors ${inj[it.key] ? 'border-helix-amber/50 bg-helix-amber/10' : 'border-line bg-bg-soft/40 hover:bg-bg-hover/60'}`}
            >
              <div className="flex items-center gap-2 text-xs font-medium text-slate-200">
                <span className={`h-2 w-2 rounded-full ${inj[it.key] ? 'bg-helix-amber' : 'bg-slate-600'}`} /> {it.label}
              </div>
              <div className="mt-0.5 text-[10px] text-slate-500">{it.hint}</div>
            </button>
          ))}
        </div>
        <div className="mt-2 text-[11px] text-slate-500">Toggle injections, then Run. Each enabled injection produces a visible correction loop in the trace.</div>
      </Panel>

      {loading && <div className="mb-4"><Spinner label="Running 17-agent pipeline against live PubMed / ChEMBL / ClinicalTrials / RDKit / TDC…" /></div>}
      {error && <div className="mb-4"><ErrorNote error={error} /></div>}
      {!run && !loading && <Empty>Run the agentic pipeline to see the plan, agent runs, tool provenance, revision events, and evaluation metrics.</Empty>}

      {run && (
        <>
          <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 lg:grid-cols-6">
            <MetricTile label="Status" value={run.status} tone={run.status === 'complete' ? 'green' : 'amber'} />
            <MetricTile label="Agent runs" value={run.agent_runs.length} />
            <MetricTile label="Revisions" value={run.revision_events.length} tone={run.revision_events.length ? 'amber' : 'green'} />
            <MetricTile label="Real outputs" value={m.real_tool_output_count ?? '—'} tone="green" />
            <MetricTile label="Self-correction" value={m.self_correction_rate ?? '—'} />
            <MetricTile label="Top target" value={m.top_target_chembl_id ?? '—'} sub={m.top_target} />
          </div>

          <div className="mb-4 flex flex-wrap items-center gap-2">
            {Object.entries(run.counts).filter(([, v]) => v > 0).map(([k, v]) => (
              <span key={k} className="inline-flex items-center gap-1"><SourceBadge type={k as any} /> <span className="text-xs text-slate-400">×{v}</span></span>
            ))}
            {run.report_id && <Badge tone="cyan">EN report {run.report_id}</Badge>}
            {run.ko_report_id && <Badge tone="cyan">KO report {run.ko_report_id}</Badge>}
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel>
              <div className="mb-3 section-title">Agent runs · observable trace ({run.agent_runs.length})</div>
              <div className="max-h-[640px] space-y-2 overflow-auto pr-1">
                {run.agent_runs.map((a) => <AgentRunCard key={a.id} run={a} />)}
              </div>
            </Panel>
            <div className="space-y-4">
              <Panel>
                <div className="mb-3 section-title">Revision events · self-correction ({run.revision_events.length})</div>
                {run.revision_events.length === 0 ? (
                  <Empty>No revisions were required. Enable an error injection above and re-run to see corrections.</Empty>
                ) : (
                  <div className="space-y-2">{run.revision_events.map((r) => <RevisionCard key={r.id} rev={r} />)}</div>
                )}
              </Panel>
              <Panel>
                <div className="mb-3 section-title">Evaluation snapshot</div>
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                  <MetricTile label="Citation verif." value={m.citation_verification_rate ?? '—'} />
                  <MetricTile label="Mol. validity" value={m.molecule_validity_rate ?? '—'} />
                  <MetricTile label="Invalid caught" value={m.invalid_smiles_caught ?? '—'} />
                  <MetricTile label="Safety blocked" value={m.safety_blocked_count ?? '—'} tone={m.safety_blocked_count ? 'violet' : 'slate'} />
                  <MetricTile label="Runtime" value={`${m.runtime_seconds ?? '—'}s`} />
                  <MetricTile label="HTTP calls" value={m.http_api_calls ?? '—'} />
                </div>
                {m.retrospective && (
                  <div className="mt-3 rounded-lg border border-line bg-bg-soft/40 p-2 text-xs text-slate-400">
                    Retrospective rediscovery: <span className="text-brand-300">{m.retrospective.passed}/{m.retrospective.total}</span> criteria — {m.retrospective.note}
                  </div>
                )}
              </Panel>
            </div>
          </div>
          <div className="mt-4"><Disclaimer text={run.disclaimer || HUMAN_RESPONSIBILITY} /></div>
        </>
      )}
    </div>
  )
}
