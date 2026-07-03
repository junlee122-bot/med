import React from 'react'
import { Icon } from '@/components/Icon'
import type { SafetyStatus, SourceType, AppMode, ValidationStatus } from '@/types'

// ============================================================================
// Design-system primitives shared across every page.
// ============================================================================

const TONE_CLASSES: Record<string, string> = {
  green: 'bg-brand-500/15 text-brand-300 border-brand-500/30',
  cyan: 'bg-helix-cyan/15 text-helix-cyan border-helix-cyan/30',
  blue: 'bg-helix-blue/15 text-blue-300 border-helix-blue/30',
  violet: 'bg-helix-violet/15 text-violet-300 border-helix-violet/30',
  amber: 'bg-helix-amber/15 text-amber-300 border-helix-amber/30',
  red: 'bg-helix-red/15 text-red-300 border-helix-red/30',
  pink: 'bg-helix-pink/15 text-pink-300 border-helix-pink/30',
  slate: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
}

export function Badge({
  children,
  tone = 'slate',
  icon,
  className = '',
}: {
  children: React.ReactNode
  tone?: string
  icon?: string
  className?: string
}) {
  return (
    <span className={`chip ${TONE_CLASSES[tone] ?? TONE_CLASSES.slate} ${className}`}>
      {icon && <Icon name={icon} size={12} />}
      {children}
    </span>
  )
}

export function ModeBadge({ mode, small }: { mode: AppMode | 'fallback'; small?: boolean }) {
  const map = {
    demo: { tone: 'cyan', label: 'DEMO', icon: 'FlaskConical' },
    real: { tone: 'green', label: 'REAL TOOL', icon: 'Plug' },
    fallback: { tone: 'amber', label: 'FALLBACK', icon: 'PlugZap' },
  } as const
  const m = map[mode]
  return (
    <Badge tone={m.tone} icon={m.icon} className={small ? 'text-[10px]' : ''}>
      {m.label}
    </Badge>
  )
}

const SAFETY_TONE: Record<SafetyStatus, { tone: string; label: string; icon: string }> = {
  PASS: { tone: 'green', label: 'PASS', icon: 'ShieldCheck' },
  REVIEW_REQUIRED: { tone: 'amber', label: 'REVIEW REQUIRED', icon: 'ShieldAlert' },
  BLOCKED: { tone: 'red', label: 'BLOCKED', icon: 'ShieldX' },
  DEMO_ONLY: { tone: 'cyan', label: 'DEMO ONLY', icon: 'FlaskConical' },
  TOOL_ERROR: { tone: 'slate', label: 'TOOL ERROR', icon: 'PlugZap' },
}

export function SafetyBadge({ status, small }: { status: SafetyStatus; small?: boolean }) {
  const s = SAFETY_TONE[status]
  return (
    <Badge tone={s.tone} icon={s.icon} className={small ? 'text-[10px]' : ''}>
      {s.label}
    </Badge>
  )
}

const SOURCE_TONE: Record<SourceType, { tone: string; label: string }> = {
  real: { tone: 'green', label: 'Real Tool Output' },
  demo: { tone: 'cyan', label: 'Demo Simulation' },
  human: { tone: 'violet', label: 'Human-entered' },
  fallback: { tone: 'amber', label: 'Demo Fallback' },
}

export function SourceBadge({ source }: { source: SourceType }) {
  const s = SOURCE_TONE[source]
  return <Badge tone={s.tone} icon={source === 'real' ? 'CircleCheck' : 'Info'}>{s.label}</Badge>
}

const VALIDATION_TONE: Record<ValidationStatus, { tone: string; icon: string }> = {
  passed: { tone: 'green', icon: 'CheckCircle2' },
  failed: { tone: 'red', icon: 'XCircle' },
  warning: { tone: 'amber', icon: 'AlertTriangle' },
  pending: { tone: 'slate', icon: 'Circle' },
  skipped: { tone: 'slate', icon: 'MinusCircle' },
}
export function ValidationBadge({ status }: { status: ValidationStatus }) {
  const v = VALIDATION_TONE[status]
  return <Badge tone={v.tone} icon={v.icon}>{status}</Badge>
}

export function Panel({
  children,
  className = '',
  raised,
}: {
  children: React.ReactNode
  className?: string
  raised?: boolean
}) {
  return <div className={`${raised ? 'panel-raised' : 'panel'} ${className}`}>{children}</div>
}

export function SectionTitle({
  children,
  right,
  icon,
}: {
  children: React.ReactNode
  right?: React.ReactNode
  icon?: string
}) {
  return (
    <div className="mb-3 flex items-center justify-between">
      <h3 className="section-title flex items-center gap-2">
        {icon && <Icon name={icon} size={14} className="text-helix-cyan" />}
        {children}
      </h3>
      {right}
    </div>
  )
}

export function StatCard({
  label,
  value,
  sub,
  icon,
  tone = 'cyan',
}: {
  label: string
  value: React.ReactNode
  sub?: React.ReactNode
  icon?: string
  tone?: string
}) {
  return (
    <Panel className="p-4">
      <div className="flex items-start justify-between">
        <div>
          <div className="text-xs uppercase tracking-wide text-slate-400">{label}</div>
          <div className="kpi mt-1">{value}</div>
          {sub && <div className="mt-1 text-xs text-slate-500">{sub}</div>}
        </div>
        {icon && (
          <div className={`rounded-lg border p-2 ${TONE_CLASSES[tone]}`}>
            <Icon name={icon} size={18} />
          </div>
        )}
      </div>
    </Panel>
  )
}

export function ConfidenceMeter({
  value,
  reasons,
  label = 'Confidence',
  compact,
}: {
  value: number
  reasons?: string[]
  label?: string
  compact?: boolean
}) {
  const pct = Math.round(value * 100)
  const tone = pct >= 75 ? 'bg-brand-500' : pct >= 50 ? 'bg-helix-amber' : 'bg-helix-red'
  return (
    <div className={compact ? '' : 'space-y-1'}>
      <div className="flex items-center justify-between text-xs">
        <span className="text-slate-400">{label}</span>
        <span className="font-mono tabular-nums text-slate-200">{pct}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-bg-soft">
        <div className={`h-full rounded-full ${tone} transition-all`} style={{ width: `${pct}%` }} />
      </div>
      {reasons && reasons.length > 0 && !compact && (
        <div className="pt-0.5 text-[11px] text-slate-500">↓ {reasons.join(' · ')}</div>
      )}
    </div>
  )
}

export function ScoreBar({ value, max = 100, tone }: { value: number; max?: number; tone?: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100))
  const color = tone ?? (pct >= 70 ? 'bg-brand-500' : pct >= 45 ? 'bg-helix-amber' : 'bg-helix-red')
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-bg-soft">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-10 text-right font-mono text-xs tabular-nums text-slate-300">{value}</span>
    </div>
  )
}

export function ProgressBar({ value, tone = 'bg-helix-cyan' }: { value: number; tone?: string }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-bg-soft">
      <div className={`h-full rounded-full ${tone} transition-all duration-500`} style={{ width: `${Math.min(100, value)}%` }} />
    </div>
  )
}

export function Button({
  children,
  variant = 'secondary',
  icon,
  onClick,
  disabled,
  className = '',
  type = 'button',
  title,
}: {
  children?: React.ReactNode
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  icon?: string
  onClick?: () => void
  disabled?: boolean
  className?: string
  type?: 'button' | 'submit'
  title?: string
}) {
  const cls =
    variant === 'primary' ? 'btn-primary' : variant === 'ghost' ? 'btn-ghost' : variant === 'danger' ? 'btn-danger' : 'btn-secondary'
  return (
    <button type={type} title={title} className={`${cls} ${className}`} onClick={onClick} disabled={disabled}>
      {icon && <Icon name={icon} size={15} />}
      {children}
    </button>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
  desc,
  tone = 'cyan',
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label?: string
  desc?: string
  tone?: string
}) {
  return (
    <label className="flex cursor-pointer items-center justify-between gap-3">
      {(label || desc) && (
        <div className="min-w-0">
          {label && <div className="text-sm text-slate-200">{label}</div>}
          {desc && <div className="text-xs text-slate-500">{desc}</div>}
        </div>
      )}
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={`relative h-5 w-9 shrink-0 rounded-full border transition-colors ${
          checked ? `border-transparent ${tone === 'red' ? 'bg-helix-red' : 'bg-brand-500'}` : 'border-line bg-bg-soft'
        }`}
      >
        <span
          className={`absolute top-0.5 h-3.5 w-3.5 rounded-full bg-white transition-all ${checked ? 'left-4' : 'left-0.5'}`}
        />
      </button>
    </label>
  )
}

export function EmptyState({
  icon = 'Inbox',
  title,
  desc,
  action,
}: {
  icon?: string
  title: string
  desc?: string
  action?: React.ReactNode
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-line p-10 text-center">
      <div className="rounded-full border border-line bg-bg-soft p-3 text-slate-400">
        <Icon name={icon} size={22} />
      </div>
      <div>
        <div className="text-sm font-medium text-slate-200">{title}</div>
        {desc && <div className="mt-1 max-w-md text-xs text-slate-500">{desc}</div>}
      </div>
      {action}
    </div>
  )
}

export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string; icon?: string; count?: number }[]
  active: string
  onChange: (id: string) => void
}) {
  return (
    <div className="flex flex-wrap gap-1 rounded-lg border border-line bg-bg-soft/60 p-1">
      {tabs.map((tb) => (
        <button
          key={tb.id}
          onClick={() => onChange(tb.id)}
          className={`flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
            active === tb.id ? 'bg-bg-raised text-white shadow-card' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          {tb.icon && <Icon name={tb.icon} size={14} />}
          {tb.label}
          {tb.count !== undefined && (
            <span className="ml-1 rounded-full bg-bg-soft px-1.5 text-[10px] tabular-nums text-slate-400">{tb.count}</span>
          )}
        </button>
      ))}
    </div>
  )
}

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  children,
  width = 'max-w-2xl',
}: {
  open: boolean
  onClose: () => void
  title: React.ReactNode
  subtitle?: React.ReactNode
  children: React.ReactNode
  width?: string
}) {
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm animate-fade-in" onClick={onClose} />
      <div className={`relative z-10 flex h-full w-full ${width} flex-col border-l border-line bg-bg-panel shadow-2xl animate-slide-in`}>
        <div className="flex items-start justify-between border-b border-line p-4">
          <div>
            <div className="text-base font-semibold text-white">{title}</div>
            {subtitle && <div className="mt-0.5 text-xs text-slate-400">{subtitle}</div>}
          </div>
          <Button variant="ghost" icon="X" onClick={onClose} className="!px-2" />
        </div>
        <div className="flex-1 overflow-y-auto p-4">{children}</div>
      </div>
    </div>
  )
}

export function KeyVal({ k, v, mono }: { k: string; v: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 border-b border-line-soft py-1.5 text-sm last:border-0">
      <span className="text-slate-400">{k}</span>
      <span className={`text-right text-slate-200 ${mono ? 'font-mono text-xs' : ''}`}>{v}</span>
    </div>
  )
}

export function Disclaimer({ children, tone = 'slate' }: { children: React.ReactNode; tone?: string }) {
  return (
    <div className={`flex items-start gap-2 rounded-lg border p-3 text-xs leading-relaxed ${TONE_CLASSES[tone]}`}>
      <Icon name="Info" size={14} className="mt-0.5 shrink-0" />
      <span>{children}</span>
    </div>
  )
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search…',
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <div className="relative">
      <Icon name="Search" size={15} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
      <input
        className="input pl-9"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
      />
    </div>
  )
}

export function PageHeader({
  title,
  subtitle,
  icon,
  actions,
}: {
  title: string
  subtitle?: string
  icon?: string
  actions?: React.ReactNode
}) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="flex items-center gap-2.5 text-xl font-semibold text-white">
          {icon && (
            <span className="rounded-lg border border-line bg-bg-raised p-1.5 text-helix-cyan">
              <Icon name={icon} size={18} />
            </span>
          )}
          {title}
        </h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-400">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  )
}

// Simple sortable header cell state hook helper
export function useSort<T>(rows: T[], initialKey: keyof T | null, initialDir: 'asc' | 'desc' = 'desc') {
  const [key, setKey] = React.useState<keyof T | null>(initialKey)
  const [dir, setDir] = React.useState<'asc' | 'desc'>(initialDir)
  const sorted = React.useMemo(() => {
    if (!key) return rows
    return [...rows].sort((a, b) => {
      const av = a[key] as unknown as number | string
      const bv = b[key] as unknown as number | string
      if (typeof av === 'number' && typeof bv === 'number') return dir === 'asc' ? av - bv : bv - av
      return dir === 'asc' ? String(av).localeCompare(String(bv)) : String(bv).localeCompare(String(av))
    })
  }, [rows, key, dir])
  const toggle = (k: keyof T) => {
    if (key === k) setDir((d) => (d === 'asc' ? 'desc' : 'asc'))
    else {
      setKey(k)
      setDir('desc')
    }
  }
  return { sorted, key, dir, toggle }
}

export function Th({
  children,
  sortKey,
  active,
  dir,
  onSort,
  className = '',
  align = 'left',
}: {
  children: React.ReactNode
  sortKey?: string
  active?: boolean
  dir?: 'asc' | 'desc'
  onSort?: () => void
  className?: string
  align?: 'left' | 'right' | 'center'
}) {
  return (
    <th
      onClick={onSort}
      className={`whitespace-nowrap px-3 py-2 text-${align} text-[11px] font-semibold uppercase tracking-wide text-slate-400 ${
        onSort ? 'cursor-pointer select-none hover:text-slate-200' : ''
      } ${className}`}
    >
      <span className={`inline-flex items-center gap-1 ${align === 'right' ? 'flex-row-reverse' : ''}`}>
        {children}
        {sortKey && onSort && (
          <Icon name={active ? (dir === 'asc' ? 'ChevronUp' : 'ChevronDown') : 'ChevronsUpDown'} size={12} className={active ? 'text-helix-cyan' : 'text-slate-600'} />
        )}
      </span>
    </th>
  )
}

export function Ring({ value, size = 44, label }: { value: number; size?: number; label?: string }) {
  const r = (size - 6) / 2
  const c = 2 * Math.PI * r
  const pct = Math.max(0, Math.min(100, value))
  const tone = pct >= 70 ? '#16b884' : pct >= 45 ? '#f59e0b' : '#ef4444'
  return (
    <div className="relative inline-flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#172038" strokeWidth={4} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke={tone}
          strokeWidth={4}
          strokeDasharray={c}
          strokeDashoffset={c - (pct / 100) * c}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute font-mono text-[11px] font-semibold tabular-nums text-white">{label ?? pct}</span>
    </div>
  )
}
