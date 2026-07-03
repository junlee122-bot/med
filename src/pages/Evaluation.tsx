import React from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Cell,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Panel,
  StatCard,
  SectionTitle,
  Disclaimer,
  PageHeader,
  Tabs,
  EmptyState,
  Th,
  Ring,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import type { EvaluationResult } from '@/types'

// ----------------------------------------------------------------------------
// Benchmark presentation metadata. Provenance labels honor Section 5: ADMET /
// docking numbers are illustrative Demo Simulation values, while agent & safety
// metrics reflect behavior that actually happened inside the app.
// ----------------------------------------------------------------------------
type Provenance = 'demo' | 'real' | 'mixed'
interface BenchMeta {
  icon: string
  short: string
  provenance: Provenance
  blurb: string
}

const BENCH_META: Record<string, BenchMeta> = {
  'Retrospective Rediscovery': {
    icon: 'History',
    short: 'Rediscovery',
    provenance: 'mixed',
    blurb: 'Can the system re-derive a known driver & mechanism from evidence? · 기지 타깃/기전 재발견',
  },
  'Molecule Generation': {
    icon: 'Atom',
    short: 'Generation',
    provenance: 'mixed',
    blurb: 'Validity, uniqueness, novelty & diversity of generated candidates.',
  },
  'ADMET Prediction': {
    icon: 'Activity',
    short: 'ADMET',
    provenance: 'demo',
    blurb: 'Illustrative property-prediction performance on demo splits.',
  },
  'Docking / Enrichment': {
    icon: 'Magnet',
    short: 'Docking',
    provenance: 'demo',
    blurb: 'Illustrative virtual-screening enrichment & docking robustness.',
  },
  'Agent Metrics': {
    icon: 'Cpu',
    short: 'Agent',
    provenance: 'real',
    blurb: 'Task success, self-correction, tool recovery & cost — from live runs.',
  },
  'Safety Metrics': {
    icon: 'ShieldCheck',
    short: 'Safety',
    provenance: 'real',
    blurb: 'Unsafe outputs blocked & audit completeness — from live runs.',
  },
}

function metaFor(name: string): BenchMeta {
  return BENCH_META[name] ?? { icon: 'Gauge', short: name, provenance: 'demo', blurb: '' }
}

const STATUS_META = {
  pass: { tone: 'green', icon: 'CircleCheck', label: 'PASS' },
  warn: { tone: 'amber', icon: 'AlertTriangle', label: 'WARN' },
  fail: { tone: 'red', icon: 'XCircle', label: 'FAIL' },
} as const

const VAL_COLOR: Record<EvaluationResult['status'], string> = {
  pass: 'text-brand-300',
  warn: 'text-amber-300',
  fail: 'text-red-300',
}

const BAR_COLOR: Record<EvaluationResult['status'], string> = {
  pass: 'bg-brand-500',
  warn: 'bg-helix-amber',
  fail: 'bg-helix-red',
}

function trimNum(v: number): string {
  return Number.isInteger(v) ? String(v) : String(Math.round(v * 1000) / 1000)
}

function fmtVal(v: number, unit?: string): string {
  if (unit === 'bool') return v >= 1 ? 'Yes' : 'No'
  if (unit === '%') return `${trimNum(v)}%`
  if (unit === 'USD') return `$${v.toFixed(2)}`
  if (unit) return `${trimNum(v)} ${unit}`
  return trimNum(v)
}

function StatusBadge({ s }: { s: EvaluationResult['status'] }) {
  const m = STATUS_META[s]
  return (
    <Badge tone={m.tone} icon={m.icon}>
      {m.label}
    </Badge>
  )
}

function ProvenanceBadge({ p }: { p: Provenance }) {
  if (p === 'real') return <Badge tone="green" icon="CircleCheck">Real in-app behavior</Badge>
  if (p === 'mixed') return <Badge tone="violet" icon="Blend">Mixed provenance</Badge>
  return <Badge tone="cyan" icon="FlaskConical">Demo Simulation</Badge>
}

// Value bar with a target marker (vertical tick). Reads intuitively for both
// higher-is-better (bar reaches/passes marker) and lower-is-better (short bar,
// well under the marker).
function TargetBar({ e }: { e: EvaluationResult }) {
  const denom = Math.max(e.value, e.target) || 1
  const raw = (e.value / denom) * 100
  const valPct = e.value === 0 ? 0 : Math.max(3, Math.min(100, raw))
  const tgtPct = Math.min(100, (e.target / denom) * 100)
  return (
    <div
      className="relative h-2 w-full rounded-full bg-bg-soft"
      title={`value ${fmtVal(e.value, e.unit)} · target ${fmtVal(e.target, e.unit)}`}
    >
      <div
        className={`absolute inset-y-0 left-0 rounded-full ${BAR_COLOR[e.status]}`}
        style={{ width: `${valPct}%` }}
      />
      <div
        className="absolute inset-y-[-2px] w-px bg-slate-200/70"
        style={{ left: `calc(${tgtPct}% - 0.5px)` }}
      />
    </div>
  )
}

export function Evaluation() {
  const evaluations = useAppStore((s) => s.evaluations)
  const [active, setActive] = React.useState<string>('all')

  // Benchmark names in first-seen order, so unexpected suites still render.
  const benchNames = React.useMemo(
    () =>
      evaluations.reduce<string[]>(
        (acc, e) => (acc.includes(e.benchmarkName) ? acc : [...acc, e.benchmarkName]),
        [],
      ),
    [evaluations],
  )

  const groups = React.useMemo(
    () =>
      benchNames.map((name) => {
        const rows = evaluations.filter((e) => e.benchmarkName === name)
        const meta = metaFor(name)
        return {
          name,
          ...meta,
          rows,
          pass: rows.filter((r) => r.status === 'pass').length,
          warn: rows.filter((r) => r.status === 'warn').length,
          fail: rows.filter((r) => r.status === 'fail').length,
        }
      }),
    [benchNames, evaluations],
  )

  const total = evaluations.length
  const passCount = evaluations.filter((e) => e.status === 'pass').length
  const warnCount = evaluations.filter((e) => e.status === 'warn').length
  const failCount = evaluations.filter((e) => e.status === 'fail').length
  const overallPassRate = total ? Math.round((passCount / total) * 100) : 0

  const findMetric = (n: string) => evaluations.find((e) => e.metricName === n)
  const selfCorr = findMetric('Self-correction rate')
  const blocked = findMetric('Blocked unsafe outputs')
  const cost = findMetric('Cost per completed workflow')

  const chartData = groups.map((g) => ({
    short: g.short,
    pass: g.pass,
    warn: g.warn,
    fail: g.fail,
  }))

  const visibleGroups = active === 'all' ? groups : groups.filter((g) => g.name === active)

  const tabs = [
    { id: 'all', label: 'All', icon: 'LayoutGrid', count: total },
    ...groups.map((g) => ({ id: g.name, label: g.short, icon: g.icon, count: g.rows.length })),
  ]

  return (
    <div className="space-y-4">
      <PageHeader
        title="평가 벤치마크 · Evaluation Bench"
        subtitle="Retrospective rediscovery, generation, ADMET, docking, agent & safety benchmarks. 각 지표는 목표값 대비 통과 여부로 표시되며, 실행 가능한 합성 정보는 포함하지 않습니다."
        icon="Gauge"
        actions={
          <div className="flex items-center gap-2">
            <Badge tone={overallPassRate >= 100 ? 'green' : overallPassRate >= 60 ? 'amber' : 'red'} icon="CircleCheck">
              {overallPassRate}% pass
            </Badge>
            <Badge tone="slate" icon="ListChecks">{total} metrics</Badge>
          </div>
        }
      />

      {total === 0 ? (
        <EmptyState
          icon="Gauge"
          title="No evaluation results yet"
          desc="Run the full demo workflow to populate the benchmark harness with rediscovery, generation, ADMET, docking, agent, and safety metrics."
        />
      ) : (
        <>
          {/* Summary KPIs */}
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard
              label="Total metrics"
              value={<span className="font-mono tabular-nums">{total}</span>}
              sub={`${benchNames.length} benchmark suites`}
              icon="ListChecks"
              tone="cyan"
            />
            <StatCard
              label="Passing"
              value={<span className="font-mono tabular-nums">{passCount}/{total}</span>}
              sub={`${warnCount} warn · ${failCount} fail`}
              icon="CircleCheck"
              tone="green"
            />
            <StatCard
              label="Self-correction rate"
              value={<span className="font-mono tabular-nums">{selfCorr ? `${Math.round(selfCorr.value * 100)}%` : '—'}</span>}
              sub={selfCorr ? `≥ ${Math.round(selfCorr.target * 100)}% target · real behavior` : 'not measured'}
              icon="RefreshCw"
              tone="violet"
            />
            <StatCard
              label="Safety blocks"
              value={<span className="font-mono tabular-nums">{blocked ? trimNum(blocked.value) : '—'}</span>}
              sub="quarantined by safety gate"
              icon="ShieldX"
              tone="red"
            />
            <StatCard
              label="Est. cost / workflow"
              value={<span className="font-mono tabular-nums">{cost ? `$${cost.value.toFixed(2)}` : '—'}</span>}
              sub={cost ? `≤ $${cost.target.toFixed(2)} budget` : 'not measured'}
              icon="DollarSign"
              tone="amber"
            />
          </div>

          {/* Per-benchmark result composition */}
          <Panel className="p-5">
            <SectionTitle
              icon="BarChart3"
              right={<Ring value={overallPassRate} label={`${overallPassRate}%`} />}
            >
              Per-benchmark results · 벤치마크별 통과 구성
            </SectionTitle>
            <div className="h-[240px] w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 8, right: 12, bottom: 4, left: -18 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#172038" vertical={false} />
                  <XAxis dataKey="short" tick={{ fontSize: 11, fill: '#94a3b8' }} axisLine={false} tickLine={false} interval={0} />
                  <YAxis allowDecimals={false} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                  <Tooltip
                    cursor={{ fill: 'rgba(148,163,184,0.08)' }}
                    contentStyle={{ background: '#0f1729', border: '1px solid #1f2b48', borderRadius: 8, fontSize: 12 }}
                    labelStyle={{ color: '#e2e8f0' }}
                  />
                  <Bar dataKey="pass" stackId="a" fill="#16b884" radius={[3, 3, 0, 0]} name="Pass" />
                  <Bar dataKey="warn" stackId="a" fill="#f59e0b" name="Warn" />
                  <Bar dataKey="fail" stackId="a" fill="#ef4444" name="Fail" />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-4 text-[11px] text-slate-400">
              {([['#16b884', 'Pass'], ['#f59e0b', 'Warn'], ['#ef4444', 'Fail']] as const).map(([c, l]) => (
                <span key={l} className="inline-flex items-center gap-1.5">
                  <span className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />
                  {l}
                </span>
              ))}
              <span className="ml-auto font-mono tabular-nums text-slate-500">{passCount}/{total} metrics passing</span>
            </div>
          </Panel>

          {/* Methodology */}
          <Disclaimer tone="cyan">
            <span className="font-medium text-slate-100">방법론 · Methodology.</span> ADMET 및 도킹/농축(EF) 수치는 설명용{' '}
            <span className="font-medium">Demo Simulation</span> 값으로, 실제 학습·가상 스크리닝 결과가 아닙니다. 반면
            self-correction, tool-error recovery, citation verification, safety-block, audit-completeness 지표는 앱 내부에서
            실제로 발생한 에이전트 동작을 반영합니다. 세로선은 목표값(threshold)을 표시합니다.
          </Disclaimer>

          {/* Filter */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <Tabs active={active} onChange={setActive} tabs={tabs} />
            <span className="text-[11px] text-slate-500">
              <span className="mr-1 inline-block h-3 w-px translate-y-0.5 bg-slate-200/70" /> vertical marker = target threshold
            </span>
          </div>

          {/* Benchmark groups */}
          <div className="space-y-4">
            {visibleGroups.map((g) => (
              <Panel key={g.name} className="overflow-hidden">
                <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line bg-bg-soft/40 px-4 py-3">
                  <div className="flex items-center gap-2.5">
                    <span className="rounded-lg border border-line bg-bg-raised p-1.5 text-helix-cyan">
                      <Icon name={g.icon} size={15} />
                    </span>
                    <div>
                      <div className="text-sm font-semibold text-white">{g.name}</div>
                      {g.blurb && <div className="text-[11px] text-slate-500">{g.blurb}</div>}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <ProvenanceBadge p={g.provenance} />
                    <Badge tone={g.pass === g.rows.length ? 'green' : g.fail > 0 ? 'red' : 'amber'} icon="Gauge">
                      {g.pass}/{g.rows.length} pass
                    </Badge>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[720px] border-collapse text-sm">
                    <thead className="border-b border-line bg-bg-soft/30">
                      <tr>
                        <Th>Metric</Th>
                        <Th align="right">Value</Th>
                        <Th align="right">Target</Th>
                        <Th className="w-44">Attainment vs target</Th>
                        <Th>Status</Th>
                      </tr>
                    </thead>
                    <tbody>
                      {g.rows.map((e) => (
                        <tr key={e.id} className="border-b border-line-soft align-top last:border-0">
                          <td className="px-3 py-2.5">
                            <div className="font-medium text-slate-100">{e.metricName}</div>
                            <div className="mt-0.5 max-w-md text-[11px] leading-snug text-slate-500">{e.interpretation}</div>
                          </td>
                          <td className={`px-3 py-2.5 text-right font-mono text-xs tabular-nums ${VAL_COLOR[e.status]}`}>
                            {fmtVal(e.value, e.unit)}
                          </td>
                          <td className="px-3 py-2.5 text-right">
                            <span className="inline-flex items-center gap-1 font-mono text-xs tabular-nums text-slate-400">
                              <Icon name={e.higherIsBetter ? 'ArrowUp' : 'ArrowDown'} size={10} className="text-slate-600" />
                              {fmtVal(e.target, e.unit)}
                            </span>
                          </td>
                          <td className="w-44 px-3 py-2.5">
                            <TargetBar e={e} />
                          </td>
                          <td className="px-3 py-2.5">
                            <StatusBadge s={e.status} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>
            ))}
          </div>
        </>
      )}
    </div>
  )
}
