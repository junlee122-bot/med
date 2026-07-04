import React from 'react'
import { LineChart, Line, ResponsiveContainer, YAxis, Tooltip as RTooltip } from 'recharts'
import { Icon } from '@/components/Icon'
import { Badge, Panel, SourceBadge, ValidationBadge, ConfidenceMeter } from '@/components/ui'
import { AGENT_MAP, PIPELINE_STAGES, STAGE_MAP } from '@/lib/constants'
import type { AgentRun, AuditEvent, InjectionToggles, ToolRun, WorkflowStage } from '@/types'

// ---------------------------------------------------------------------------
// WorkflowDAG — vertical stage rail with active-node pulse & revision branch.
// ---------------------------------------------------------------------------
const DAG_ORDER: WorkflowStage[] = [...PIPELINE_STAGES, 'COMPLETE']

export function WorkflowDAG({ current, revisionCount }: { current: WorkflowStage; revisionCount: number }) {
  const curIdx = DAG_ORDER.indexOf(current === 'REVISION_LOOP' ? 'CRITIC_REVIEW' : current)
  const done = current === 'COMPLETE'
  return (
    <div className="space-y-0.5">
      {DAG_ORDER.map((stage, i) => {
        const meta = STAGE_MAP[stage]
        const isDone = done || i < curIdx
        const isActive = !done && i === curIdx
        const isPending = !done && i > curIdx
        const agent = meta.agents[0]
        const color = agent ? AGENT_MAP[agent]?.color : '#22d3ee'
        return (
          <div key={stage} className="flex items-stretch gap-3">
            <div className="flex flex-col items-center">
              <div
                className={`grid h-6 w-6 shrink-0 place-items-center rounded-full border-2 transition-all ${
                  isActive
                    ? 'animate-pulse-ring border-helix-cyan bg-helix-cyan/20'
                    : isDone
                      ? 'border-brand-500 bg-brand-500/20'
                      : 'border-line bg-bg-soft'
                }`}
              >
                {isDone ? (
                  <Icon name="Check" size={12} className="text-brand-300" />
                ) : isActive ? (
                  <span className="h-2 w-2 rounded-full bg-helix-cyan" />
                ) : (
                  <span className="h-1.5 w-1.5 rounded-full bg-slate-600" />
                )}
              </div>
              {i < DAG_ORDER.length - 1 && (
                <div className={`w-0.5 flex-1 ${isDone ? 'bg-brand-500/40' : 'bg-line'}`} style={{ minHeight: 14 }} />
              )}
            </div>
            <div
              className={`mb-1 flex-1 rounded-lg border px-3 py-1.5 transition-all ${
                isActive
                  ? 'border-helix-cyan/50 bg-helix-cyan/5 shadow-glow'
                  : isDone
                    ? 'border-line bg-bg-raised/60'
                    : 'border-line-soft bg-transparent opacity-70'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <span className={`text-xs font-medium ${isActive ? 'text-white' : isPending ? 'text-slate-500' : 'text-slate-300'}`}>
                  {meta.label}
                </span>
                {agent && (
                  <span className="hidden items-center gap-1 text-[10px] text-slate-500 sm:inline-flex">
                    <span className="h-1.5 w-1.5 rounded-full" style={{ background: color }} />
                    {agent.replace(' Agent', '').replace(' / Verifier', '')}
                  </span>
                )}
              </div>
            </div>
          </div>
        )
      })}
      {revisionCount > 0 && (
        <div className="ml-9 mt-1 flex items-center gap-1.5 text-[11px] text-helix-amber">
          <Icon name="RefreshCw" size={12} />
          {revisionCount} revision loop{revisionCount > 1 ? 's' : ''} executed (critic → agent → re-validate)
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// AgentCard
// ---------------------------------------------------------------------------
const STATUS_TONE: Record<string, { tone: string; label: string; icon: string }> = {
  success: { tone: 'green', label: 'done', icon: 'CheckCircle2' },
  running: { tone: 'cyan', label: 'running', icon: 'Loader' },
  error: { tone: 'red', label: 'error', icon: 'XCircle' },
  revised: { tone: 'amber', label: 'revised', icon: 'RefreshCw' },
  blocked: { tone: 'red', label: 'blocked', icon: 'ShieldX' },
  queued: { tone: 'slate', label: 'queued', icon: 'Clock' },
  idle: { tone: 'slate', label: 'idle', icon: 'Circle' },
  skipped: { tone: 'slate', label: 'skipped', icon: 'MinusCircle' },
}

export function AgentCard({ run }: { run: AgentRun }) {
  const def = AGENT_MAP[run.agentName]
  const st = STATUS_TONE[run.status] ?? STATUS_TONE.idle
  return (
    <Panel className={`p-3 ${run.isRevision ? 'border-helix-amber/40' : ''}`}>
      <div className="flex items-start gap-2.5">
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line" style={{ background: `${def?.color}18`, color: def?.color }}>
          <Icon name={def?.icon ?? 'Bot'} size={16} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <span className="truncate text-sm font-semibold text-white">{run.agentName}</span>
            <Badge tone={st.tone} icon={st.icon} className="shrink-0">
              {run.isRevision ? 'revision' : st.label}
            </Badge>
          </div>
          <div className="mt-0.5 text-[11px] text-slate-500">{STAGE_MAP[run.stage].label}</div>
          <div className="mt-1.5 text-xs leading-relaxed text-slate-300">{run.outputSummary}</div>
          {run.warnings.length > 0 && (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {run.warnings.map((w, i) => (
                <span key={i} className="chip bg-helix-amber/10 text-amber-300 border-helix-amber/30 text-[10px]">
                  <Icon name="AlertTriangle" size={10} />
                  {w}
                </span>
              ))}
            </div>
          )}
          <div className="mt-2 flex items-center gap-3">
            <div className="flex-1">
              <ConfidenceMeter value={run.confidence} compact />
            </div>
            <ValidationBadge status={run.validationStatus} />
          </div>
        </div>
      </div>
    </Panel>
  )
}

// ---------------------------------------------------------------------------
// ToolRunCard
// ---------------------------------------------------------------------------
export function ToolRunCard({ run }: { run: ToolRun }) {
  const err = run.status === 'error'
  return (
    <div className={`rounded-lg border p-2.5 text-xs ${err ? 'border-helix-red/40 bg-helix-red/5' : 'border-line bg-bg-raised/50'}`}>
      <div className="flex items-center justify-between gap-2">
        <span className="flex items-center gap-1.5 font-medium text-slate-200">
          <Icon name="Plug" size={12} className="text-helix-cyan" />
          {run.toolName}
        </span>
        <SourceBadge source={run.sourceType} />
      </div>
      <div className="mt-1.5 space-y-0.5 text-[11px] text-slate-400">
        <div className="flex gap-1">
          <span className="text-slate-500">in:</span>
          <span className="truncate">{run.inputSummary}</span>
        </div>
        <div className="flex gap-1">
          <span className="text-slate-500">out:</span>
          <span className={err ? 'text-red-300' : ''}>{run.error ?? run.outputSummary}</span>
        </div>
      </div>
      <div className="mt-1.5 flex items-center gap-2 text-[10px] text-slate-500">
        <span className="flex items-center gap-0.5"><Icon name="Clock" size={10} />{run.latencyMs}ms</span>
        <span className="flex items-center gap-0.5"><Icon name="Coins" size={10} />${run.costEstimate.toFixed(4)}</span>
        <span className={`ml-auto ${err ? 'text-red-300' : 'text-slate-500'}`}>{run.status}</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// AuditTimeline — observable process trace (no hidden chain-of-thought)
// ---------------------------------------------------------------------------
const EVENT_ICON: Record<string, { icon: string; tone: string }> = {
  plan: { icon: 'ListTree', tone: 'text-helix-cyan' },
  agent: { icon: 'Bot', tone: 'text-brand-300' },
  tool: { icon: 'Plug', tone: 'text-helix-blue' },
  validation: { icon: 'CheckCheck', tone: 'text-brand-300' },
  revision: { icon: 'RefreshCw', tone: 'text-helix-amber' },
  safety: { icon: 'ShieldAlert', tone: 'text-helix-red' },
  error: { icon: 'AlertOctagon', tone: 'text-helix-red' },
  stage: { icon: 'Flag', tone: 'text-slate-400' },
  report: { icon: 'FileText', tone: 'text-helix-violet' },
}

export function AuditTimeline({ events, dense }: { events: AuditEvent[]; dense?: boolean }) {
  const ref = React.useRef<HTMLDivElement>(null)
  React.useEffect(() => {
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight
  }, [events.length])
  if (events.length === 0)
    return <div className="p-4 text-center text-xs text-slate-500">No events yet. Run the workflow to populate the observable trace.</div>
  return (
    <div ref={ref} className={`space-y-2 overflow-y-auto ${dense ? 'max-h-[420px]' : ''}`}>
      {events.map((e) => {
        const ic = EVENT_ICON[e.type] ?? EVENT_ICON.stage
        return (
          <div key={e.id} className="flex gap-2 animate-fade-in">
            <div className={`mt-0.5 ${ic.tone}`}>
              <Icon name={ic.icon} size={14} />
            </div>
            <div className="min-w-0 flex-1 border-b border-line-soft pb-2">
              <div className="flex items-center justify-between gap-2">
                <span className="truncate text-xs font-medium text-slate-200">{e.title}</span>
                <span className="shrink-0 font-mono text-[10px] text-slate-600">
                  {e.ts ? new Date(e.ts).toLocaleTimeString([], { hour12: false }) : ''}
                </span>
              </div>
              <div className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{e.detail}</div>
              <div className="mt-1 flex flex-wrap items-center gap-1">
                {e.agent && <span className="text-[10px] text-slate-600">{e.agent}</span>}
                {e.sourceType && <SourceBadge source={e.sourceType} />}
                {e.validationStatus && <ValidationBadge status={e.validationStatus} />}
                {e.evidenceIds && e.evidenceIds.length > 0 && (
                  <span className="chip border-line bg-bg-soft text-[10px] text-slate-400">evidence: {e.evidenceIds.join(', ')}</span>
                )}
              </div>
            </div>
          </div>
        )
      })}
    </div>
  )
}

// ---------------------------------------------------------------------------
// CostLedger
// ---------------------------------------------------------------------------
export function CostLedger({
  cost,
  tokens,
  toolRuns,
  latencyMs,
}: {
  cost: number
  tokens: number
  toolRuns: number
  latencyMs: number
}) {
  const efficiency = toolRuns > 0 ? (cost / toolRuns).toFixed(4) : '0'
  const items = [
    { label: 'Est. cost', value: `$${cost.toFixed(3)}`, icon: 'Coins', tone: 'text-brand-300' },
    { label: 'Est. tokens', value: tokens.toLocaleString(), icon: 'Hash', tone: 'text-helix-cyan' },
    { label: 'Tool runs', value: toolRuns, icon: 'Plug', tone: 'text-helix-blue' },
    { label: 'Tool runtime', value: `${(latencyMs / 1000).toFixed(1)}s`, icon: 'Clock', tone: 'text-helix-violet' },
    { label: '$ / tool run', value: `$${efficiency}`, icon: 'Gauge', tone: 'text-slate-300' },
  ]
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
      {items.map((it) => (
        <div key={it.label} className="rounded-lg border border-line bg-bg-raised/50 p-2.5">
          <div className="flex items-center gap-1 text-[10px] uppercase tracking-wide text-slate-500">
            <Icon name={it.icon} size={11} className={it.tone} />
            {it.label}
          </div>
          <div className="mt-0.5 font-mono text-sm font-semibold text-white">{it.value}</div>
        </div>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// ConfidenceTrend
// ---------------------------------------------------------------------------
export function ConfidenceTrend({ agentRuns }: { agentRuns: AgentRun[] }) {
  const data = agentRuns.map((a, i) => ({ i, c: Math.round(a.confidence * 100), name: a.agentName }))
  if (data.length < 2)
    return <div className="grid h-24 place-items-center text-xs text-slate-600">Confidence trend appears as agents complete.</div>
  return (
    <ResponsiveContainer width="100%" height={96}>
      <LineChart data={data} margin={{ top: 6, right: 6, bottom: 0, left: -24 }}>
        <YAxis domain={[0, 100]} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
        <RTooltip
          contentStyle={{ background: '#0f172a', border: '1px solid #1f2b48', borderRadius: 8, fontSize: 11 }}
          labelFormatter={(i) => data[i as number]?.name ?? ''}
          formatter={(v) => [`${v}%`, 'confidence']}
        />
        <Line type="monotone" dataKey="c" stroke="#22d3ee" strokeWidth={2} dot={{ r: 2, fill: '#22d3ee' }} />
      </LineChart>
    </ResponsiveContainer>
  )
}

// ---------------------------------------------------------------------------
// ErrorInjectionPanel — self-correction demo (Section 15)
// ---------------------------------------------------------------------------
const INJECTIONS: { key: keyof InjectionToggles; label: string; desc: string; icon: string }[] = [
  { key: 'invalidSmiles', label: 'Invalid SMILES', desc: 'Validator rejects → regenerate', icon: 'FlaskConical' },
  { key: 'fakeCitation', label: 'Fake citation', desc: 'Verifier fails → demote', icon: 'BookX' },
  { key: 'contradictoryEvidence', label: 'Contradictory evidence', desc: 'Recalculate confidence', icon: 'GitCompareArrows' },
  { key: 'toolFailure', label: 'Tool failure', desc: 'Retry → demo fallback', icon: 'PlugZap' },
  { key: 'safetyHazard', label: 'Safety hazard', desc: 'Auditor blocks candidate', icon: 'ShieldX' },
  { key: 'overclaim', label: 'Overclaim', desc: 'Critic rewrites language', icon: 'MessageSquareWarning' },
]

export function ErrorInjectionPanel({
  injections,
  onToggle,
}: {
  injections: InjectionToggles
  onToggle: (k: keyof InjectionToggles, v: boolean) => void
}) {
  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-3">
      {INJECTIONS.map((it) => {
        const on = injections[it.key]
        return (
          <button
            key={it.key}
            onClick={() => onToggle(it.key, !on)}
            className={`flex items-start gap-2 rounded-lg border p-2.5 text-left transition-all ${
              on ? 'border-helix-amber/50 bg-helix-amber/10' : 'border-line bg-bg-raised/40 hover:border-line-bright'
            }`}
          >
            <Icon name={it.icon} size={15} className={on ? 'text-helix-amber' : 'text-slate-500'} />
            <div className="min-w-0">
              <div className={`text-xs font-medium ${on ? 'text-amber-200' : 'text-slate-300'}`}>{it.label}</div>
              <div className="text-[10px] text-slate-500">{it.desc}</div>
            </div>
            <div className={`ml-auto mt-0.5 h-2 w-2 shrink-0 rounded-full ${on ? 'bg-helix-amber' : 'bg-slate-700'}`} />
          </button>
        )
      })}
    </div>
  )
}
