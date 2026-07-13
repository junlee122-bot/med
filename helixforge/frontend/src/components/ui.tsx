import React from 'react'
import type { SourceType, HealthStatus } from '@/lib/api'
import { SOURCE_META, HEALTH_META } from '@/lib/api'

const TONE: Record<string, string> = {
  green: 'border-brand-500/40 bg-brand-500/10 text-brand-300',
  cyan: 'border-helix-cyan/40 bg-helix-cyan/10 text-helix-cyan',
  amber: 'border-helix-amber/40 bg-helix-amber/10 text-helix-amber',
  red: 'border-helix-red/40 bg-helix-red/10 text-helix-red',
  violet: 'border-helix-violet/40 bg-helix-violet/10 text-helix-violet',
  slate: 'border-line-bright bg-bg-hover text-slate-300',
}

export function Badge({ tone = 'slate', children, className = '' }: { tone?: string; children: React.ReactNode; className?: string }) {
  return <span className={`chip ${TONE[tone] || TONE.slate} ${className}`}>{children}</span>
}

export function SourceBadge({ type }: { type: SourceType }) {
  const m = SOURCE_META[type] || { label: type, tone: 'slate' }
  return <Badge tone={m.tone}>{m.label}</Badge>
}

export function HealthBadge({ status }: { status: HealthStatus }) {
  const m = HEALTH_META[status] || { label: status, tone: 'slate' }
  return <Badge tone={m.tone}>{m.label}</Badge>
}

export function Panel({ children, className = '' }: { children: React.ReactNode; className?: string }) {
  return <div className={`panel p-5 ${className}`}>{children}</div>
}

export function StatCard({ label, value, sub, tone = 'slate' }: { label: string; value: React.ReactNode; sub?: React.ReactNode; tone?: string }) {
  return (
    <div className="panel p-4">
      <div className="text-[11px] font-medium uppercase tracking-wide text-slate-400">{label}</div>
      <div className={`kpi mt-1 ${tone === 'green' ? 'text-brand-300' : tone === 'red' ? 'text-helix-red' : tone === 'amber' ? 'text-helix-amber' : ''}`}>{value}</div>
      {sub && <div className="mt-1 text-xs text-slate-400">{sub}</div>}
    </div>
  )
}

export function PageHeader({ icon, title, subtitle, actions }: { icon?: React.ReactNode; title: string; subtitle?: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        {icon && <div className="mt-0.5 text-helix-cyan">{icon}</div>}
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-white">{title}</h1>
          {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-400">{subtitle}</p>}
        </div>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

export function Spinner({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-400" role="status" aria-live="polite">
      <span aria-hidden="true" className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-helix-cyan/30 border-t-helix-cyan" />
      {label}
    </div>
  )
}

export function ErrorNote({ error }: { error: string }) {
  return (
    <div className="rounded-lg border border-helix-red/40 bg-helix-red/10 px-3 py-2 text-sm text-helix-red" role="alert">
      {error}
    </div>
  )
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="rounded-lg border border-dashed border-line-bright bg-bg-soft/40 px-4 py-8 text-center text-sm text-slate-500">{children}</div>
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
    </label>
  )
}

export function Disclaimer({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-line bg-bg-soft/50 px-3 py-2 text-xs text-slate-400">
      <span className="font-medium text-slate-300">Disclaimer · </span>{text}
    </div>
  )
}
