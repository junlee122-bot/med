import type { AgentRun, RevisionEvent } from '@/lib/api'
import { REASON_META } from '@/lib/api'
import { Badge, SourceBadge } from './ui'
import { Icon } from './Icon'

const STATUS_TONE: Record<string, string> = {
  COMPLETE: 'green', WARNING: 'amber', FAILED: 'red', BLOCKED: 'violet', REVISING: 'amber', RUNNING: 'cyan',
}

export function AgentRunCard({ run }: { run: AgentRun }) {
  return (
    <div className="rounded-lg border border-line bg-bg-soft/40 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="grid h-6 w-6 place-items-center rounded bg-bg-hover text-[10px] font-semibold text-slate-400">{run.stage_index}</span>
          <div>
            <div className="text-sm font-medium text-slate-100">{run.agent_name}</div>
            <div className="text-[10px] uppercase tracking-wide text-slate-500">{run.stage}</div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          <Badge tone={STATUS_TONE[run.status] || 'slate'}>{run.status}</Badge>
        </div>
      </div>
      <div className="mt-2 text-xs text-slate-300">{run.output_summary}</div>
      {run.rationale && <div className="mt-1 text-[11px] italic text-slate-500">{run.rationale}</div>}
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <span className="text-[10px] text-slate-500">conf</span>
        <div className="h-1.5 w-24 overflow-hidden rounded-full bg-bg-hover">
          <div className="h-full bg-gradient-to-r from-brand-500 to-helix-cyan" style={{ width: `${Math.round((run.confidence || 0) * 100)}%` }} />
        </div>
        <span className="text-[10px] tabular-nums text-slate-400">{Math.round((run.confidence || 0) * 100)}%</span>
        {[...new Set(run.source_types || [])].map((s) => <SourceBadge key={s} type={s} />)}
      </div>
      {run.validation_checks?.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {run.validation_checks.map((c, i) => (
            <span key={i} className={`inline-flex items-center gap-1 rounded px-1.5 py-0.5 text-[10px] ${c.ok ? 'bg-brand-500/10 text-brand-300' : 'bg-helix-red/10 text-helix-red'}`}>
              <Icon name={c.ok ? 'Check' : 'X'} size={10} /> {c.check}
            </span>
          ))}
        </div>
      )}
      {run.warnings?.length > 0 && <div className="mt-1 text-[10px] text-helix-amber">⚠ {run.warnings.join('; ')}</div>}
      {run.errors?.length > 0 && <div className="mt-1 text-[10px] text-helix-red">✕ {run.errors.join('; ')}</div>}
      {run.next_action && <div className="mt-1 text-[10px] text-slate-500">→ {run.next_action}</div>}
    </div>
  )
}

export function RevisionCard({ rev }: { rev: RevisionEvent }) {
  const meta = REASON_META[rev.reason_category] || { label: rev.reason_category, tone: 'amber' }
  return (
    <div className="rounded-lg border border-helix-amber/30 bg-helix-amber/5 p-3">
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
          <Icon name="RefreshCw" size={13} className="text-helix-amber" /> {meta.label}
        </div>
        <Badge tone={meta.tone}>revision</Badge>
      </div>
      <div className="mt-1 text-xs text-slate-400">{rev.issue_summary}</div>
      <div className="mt-2 grid gap-2 sm:grid-cols-2">
        <div className="rounded border border-line bg-bg-soft/60 p-2">
          <div className="text-[10px] uppercase tracking-wide text-helix-red">Before</div>
          <div className="mt-0.5 text-[11px] text-slate-400">{rev.before_summary || '—'}</div>
        </div>
        <div className="rounded border border-brand-500/30 bg-brand-500/5 p-2">
          <div className="text-[10px] uppercase tracking-wide text-brand-300">After</div>
          <div className="mt-0.5 text-[11px] text-slate-300">{rev.after_summary || '—'}</div>
        </div>
      </div>
      <div className="mt-1.5 text-[11px] text-slate-500"><span className="text-slate-400">Action:</span> {rev.action_taken}</div>
    </div>
  )
}

export function MetricTile({ label, value, tone = 'slate', sub }: { label: string; value: React.ReactNode; tone?: string; sub?: string }) {
  const color = tone === 'green' ? 'text-brand-300' : tone === 'red' ? 'text-helix-red' : tone === 'amber' ? 'text-helix-amber' : 'text-white'
  return (
    <div className="rounded-lg border border-line bg-bg-soft/40 p-3">
      <div className="text-[10px] font-medium uppercase tracking-wide text-slate-500">{label}</div>
      <div className={`mt-0.5 text-xl font-semibold tabular-nums ${color}`}>{value}</div>
      {sub && <div className="text-[10px] text-slate-500">{sub}</div>}
    </div>
  )
}
