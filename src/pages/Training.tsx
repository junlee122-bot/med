import React from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  StatCard,
  ProgressBar,
  Disclaimer,
  PageHeader,
  Tabs,
  KeyVal,
  EmptyState,
  Th,
  useSort,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { DEFAULT_MOLECULE_WEIGHTS } from '@/lib/scoring'
import type {
  TrainingJob,
  TrainingJobType,
  DatasetEntry,
  CheckpointEntry,
  MoleculeWeights,
} from '@/types'

// ---------------------------------------------------------------------------
// Local helpers
// ---------------------------------------------------------------------------

const JOB_TYPE_META: Record<TrainingJobType, { label: string; icon: string; tone: string }> = {
  reinvent_rl: { label: 'REINVENT4 · RL generation', icon: 'Atom', tone: 'green' },
  admet_finetune: { label: 'ADMET fine-tune', icon: 'Activity', tone: 'cyan' },
  reward_model: { label: 'Reward model', icon: 'Scale', tone: 'violet' },
  tool_router: { label: 'Tool router distillation', icon: 'Route', tone: 'amber' },
}

const JOB_STATUS_META: Record<TrainingJob['status'], { label: string; tone: string; icon: string }> = {
  queued: { label: 'QUEUED', tone: 'slate', icon: 'Clock' },
  running: { label: 'RUNNING', tone: 'cyan', icon: 'Loader' },
  complete: { label: 'COMPLETE', tone: 'green', icon: 'CircleCheck' },
  failed: { label: 'FAILED', tone: 'red', icon: 'XCircle' },
}

function JobStatusBadge({ status }: { status: TrainingJob['status'] }) {
  const m = JOB_STATUS_META[status]
  return (
    <Badge tone={m.tone} icon={m.icon}>
      {m.label}
    </Badge>
  )
}

const CHECKPOINT_STATUS_TONE: Record<CheckpointEntry['status'], string> = {
  staged: 'amber',
  validated: 'green',
  archived: 'slate',
}

function fmtMetric(v: number): string {
  return Math.abs(v) < 1 && v !== 0 ? v.toFixed(2) : v.toLocaleString()
}

const CHART_GRID = '#172038'
const CHART_AXIS = '#64748b'
const TOOLTIP_STYLE = {
  background: '#0b1120',
  border: '1px solid #1f2b48',
  borderRadius: 8,
  fontSize: 11,
  color: '#e2e8f0',
}

// ---------------------------------------------------------------------------
// Training Jobs
// ---------------------------------------------------------------------------

function TrainingJobCard({ job }: { job: TrainingJob }) {
  const startTrainingJob = useAppStore((s) => s.startTrainingJob)
  const typeMeta = JOB_TYPE_META[job.jobType]
  const running = job.status === 'running'

  return (
    <Panel className="p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex rounded-lg border border-line bg-bg-raised p-1.5 text-helix-cyan">
              <Icon name={typeMeta.icon} size={16} />
            </span>
            <span className="font-mono text-sm font-semibold text-white">{job.name}</span>
            <Badge tone={typeMeta.tone}>{typeMeta.label}</Badge>
            <Badge tone="cyan" icon="FlaskConical">Demo</Badge>
          </div>
          <div className="mt-1.5 text-xs text-slate-400">{job.objective}</div>
        </div>
        <div className="flex flex-col items-end gap-2">
          <JobStatusBadge status={job.status} />
          <Button
            variant={job.status === 'complete' ? 'secondary' : 'primary'}
            icon={running ? 'Loader' : 'Play'}
            disabled={running}
            onClick={() => startTrainingJob(job.id)}
          >
            {running ? 'Running…' : job.status === 'complete' ? 'Re-run job (demo)' : 'Run job (demo)'}
          </Button>
        </div>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        {/* Left: meta + metrics + logs */}
        <div className="space-y-3">
          <div className="rounded-lg border border-line bg-bg-raised/40 p-3">
            <KeyVal k="Model family" v={job.modelFamily} />
            <KeyVal k="Dataset" v={job.dataset} />
            <KeyVal k="Checkpoint" v={<span className="font-mono text-xs">{job.checkpointName}</span>} />
            <KeyVal
              k="Hyperparameters"
              v={
                <span className="font-mono text-[11px] text-slate-400">
                  {Object.entries(job.hyperparameters)
                    .map(([k, v]) => `${k}=${v}`)
                    .join(' · ')}
                </span>
              }
            />
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between text-xs">
              <span className="text-slate-400">Progress</span>
              <span className="font-mono tabular-nums text-slate-200">{job.progress}%</span>
            </div>
            <ProgressBar
              value={job.progress}
              tone={job.status === 'complete' ? 'bg-brand-500' : job.status === 'failed' ? 'bg-helix-red' : 'bg-helix-cyan'}
            />
          </div>

          <div className="flex flex-wrap gap-2">
            {job.metrics.map((mt) => (
              <div key={mt.name} className="rounded-lg border border-line bg-bg-soft/50 px-2.5 py-1.5">
                <div className="text-[10px] uppercase tracking-wide text-slate-500">{mt.name}</div>
                <div className="font-mono text-sm font-semibold tabular-nums text-white">
                  {fmtMetric(mt.value)}
                  {mt.unit ? <span className="ml-0.5 text-[10px] text-slate-500">{mt.unit}</span> : null}
                  {mt.target !== undefined && (
                    <span className="ml-1 text-[10px] font-normal text-slate-500">/ {fmtMetric(mt.target)}</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right: curve chart */}
        <div className="rounded-lg border border-line bg-bg-raised/40 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-medium text-slate-300">Training curve</span>
            <span className="text-[10px] text-slate-500">loss ↓ · metric ↑</span>
          </div>
          <ResponsiveContainer width="100%" height={180}>
            <LineChart data={job.curve} margin={{ top: 4, right: 6, bottom: 0, left: -18 }}>
              <CartesianGrid stroke={CHART_GRID} strokeDasharray="3 3" />
              <XAxis dataKey="step" tick={{ fontSize: 10, fill: CHART_AXIS }} axisLine={false} tickLine={false} />
              <YAxis
                yAxisId="loss"
                domain={[0, 'auto']}
                tick={{ fontSize: 10, fill: CHART_AXIS }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                yAxisId="metric"
                orientation="right"
                domain={[0, 1]}
                tick={{ fontSize: 10, fill: CHART_AXIS }}
                axisLine={false}
                tickLine={false}
              />
              <Tooltip contentStyle={TOOLTIP_STYLE} labelStyle={{ color: '#94a3b8' }} />
              <Legend wrapperStyle={{ fontSize: 10 }} />
              <Line yAxisId="loss" type="monotone" dataKey="loss" name="loss" stroke="#f59e0b" strokeWidth={2} dot={false} />
              <Line yAxisId="metric" type="monotone" dataKey="metric" name="metric" stroke="#22d3ee" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Logs */}
      <div className="mt-3 rounded-lg border border-line bg-black/30 p-2.5">
        <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-slate-500">
          <Icon name="Terminal" size={12} /> Run logs
        </div>
        <div className="space-y-0.5 font-mono text-[11px] leading-relaxed text-slate-400">
          {job.logs.map((l, i) => (
            <div key={i} className={l.startsWith('Demo Simulation') ? 'text-helix-amber' : ''}>
              {l}
            </div>
          ))}
        </div>
      </div>
    </Panel>
  )
}

function TrainingJobsTab({ jobs }: { jobs: TrainingJob[] }) {
  if (jobs.length === 0) {
    return <EmptyState icon="Cpu" title="No training jobs" desc="Specialized component training jobs will appear here." />
  }
  return (
    <div className="space-y-4">
      {jobs.map((j) => (
        <TrainingJobCard key={j.id} job={j} />
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Dataset Registry
// ---------------------------------------------------------------------------

function DatasetTab({ datasets }: { datasets: DatasetEntry[] }) {
  const { sorted, key, dir, toggle } = useSort<DatasetEntry>(datasets, 'size', 'desc')
  if (datasets.length === 0) {
    return <EmptyState icon="Database" title="No datasets registered" />
  }
  return (
    <div className="space-y-3">
      <Panel className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[960px] border-collapse text-sm">
            <thead className="border-b border-line bg-bg-soft/50">
              <tr>
                <Th sortKey="name" active={key === 'name'} dir={dir} onSort={() => toggle('name')}>Dataset</Th>
                <Th>Source</Th>
                <Th>Task</Th>
                <Th>Endpoint</Th>
                <Th sortKey="size" active={key === 'size'} dir={dir} onSort={() => toggle('size')} align="right">Rows</Th>
                <Th>License</Th>
                <Th>Split</Th>
                <Th>Leakage</Th>
                <Th>Quality notes</Th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((d) => (
                <tr key={d.id} className="border-b border-line-soft transition-colors hover:bg-bg-hover/40">
                  <td className="px-3 py-2.5 font-medium text-white">{d.name}</td>
                  <td className="px-3 py-2.5 text-slate-300">{d.source}</td>
                  <td className="px-3 py-2.5">
                    <Badge tone={d.taskType === 'classification' ? 'blue' : 'violet'}>{d.taskType}</Badge>
                  </td>
                  <td className="px-3 py-2.5 font-mono text-xs text-slate-300">{d.endpoint}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-slate-300">
                    {d.size.toLocaleString()}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-slate-400">{d.licenseStatus}</td>
                  <td className="px-3 py-2.5 font-mono text-[11px] text-slate-400">{d.split}</td>
                  <td className="px-3 py-2.5">
                    {d.leakageWarning ? (
                      <Badge tone="amber" icon="AlertTriangle">Review</Badge>
                    ) : (
                      <Badge tone="green" icon="CheckCircle2">Clean</Badge>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-xs text-slate-500">{d.qualityNotes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Disclaimer tone="amber">
        데이터 누수(leakage) 경고가 있는 데이터셋은 시간/스캐폴드 분할 재검토가 필요합니다. All datasets are demo slices —
        licensing and provenance are illustrative, not production-cleared.
      </Disclaimer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Scoring Function Builder
// ---------------------------------------------------------------------------

const WEIGHT_FIELDS: { key: keyof MoleculeWeights; label: string; labelKo: string; icon: string }[] = [
  { key: 'binding', label: 'Binding affinity', labelKo: '결합력', icon: 'Magnet' },
  { key: 'admet', label: 'ADMET', labelKo: '흡수·대사·독성', icon: 'Activity' },
  { key: 'qed', label: 'QED (drug-likeness)', labelKo: '약물성', icon: 'Pill' },
  { key: 'lipinski', label: 'Lipinski compliance', labelKo: '리핀스키 규칙', icon: 'Ruler' },
  { key: 'syntheticFeasibility', label: 'Synthetic feasibility', labelKo: '합성 용이성', icon: 'Wrench' },
  { key: 'novelty', label: 'Novelty / IP distance', labelKo: '신규성', icon: 'Sparkles' },
  { key: 'targetRationale', label: 'Target rationale', labelKo: '타깃 근거', icon: 'Crosshair' },
  { key: 'confidence', label: 'Confidence', labelKo: '신뢰도', icon: 'Gauge' },
]

function ScoringBuilderTab() {
  const weights = useAppStore((s) => s.moleculeWeights)
  const setMoleculeWeights = useAppStore((s) => s.setMoleculeWeights)

  const sum = WEIGHT_FIELDS.reduce((acc, f) => acc + weights[f.key], 0)
  const isDefault = WEIGHT_FIELDS.every((f) => weights[f.key] === DEFAULT_MOLECULE_WEIGHTS[f.key])

  const update = (k: keyof MoleculeWeights, v: number) => {
    setMoleculeWeights({ ...weights, [k]: v })
  }

  return (
    <div className="space-y-4">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <Panel className="p-4">
            <SectionTitle
              icon="SlidersHorizontal"
              right={
                <Button
                  variant="ghost"
                  icon="RotateCcw"
                  disabled={isDefault}
                  onClick={() => setMoleculeWeights({ ...DEFAULT_MOLECULE_WEIGHTS })}
                >
                  Reset defaults
                </Button>
              }
            >
              Composite scoring weights · 복합 점수 가중치
            </SectionTitle>
            <div className="space-y-3.5">
              {WEIGHT_FIELDS.map((f) => {
                const val = weights[f.key]
                const def = DEFAULT_MOLECULE_WEIGHTS[f.key]
                const contribution = sum > 0 ? (val / sum) * 100 : 0
                return (
                  <div key={f.key}>
                    <div className="mb-1 flex items-center justify-between text-xs">
                      <span className="flex items-center gap-1.5 text-slate-300">
                        <Icon name={f.icon} size={13} className="text-helix-cyan" />
                        {f.label}
                        <span className="text-slate-600">· {f.labelKo}</span>
                      </span>
                      <span className="font-mono tabular-nums text-slate-200">
                        {val.toFixed(2)}
                        <span className="ml-1.5 text-[10px] text-slate-500">{contribution.toFixed(0)}%</span>
                        {val !== def && (
                          <span className="ml-1.5 text-[10px] text-helix-amber">(def {def.toFixed(2)})</span>
                        )}
                      </span>
                    </div>
                    <input
                      type="range"
                      min={0}
                      max={0.4}
                      step={0.01}
                      value={val}
                      onChange={(e) => update(f.key, Number(e.target.value))}
                      className="h-1.5 w-full cursor-pointer appearance-none rounded-full bg-bg-soft accent-brand-500"
                      aria-label={f.label}
                    />
                  </div>
                )
              })}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <StatCard
            label="Weight sum (raw)"
            value={<span className="font-mono tabular-nums">{sum.toFixed(2)}</span>}
            sub="Normalized to 1.0 at scoring time"
            icon="Sigma"
            tone="cyan"
          />
          <Panel className="p-4">
            <SectionTitle icon="Info">How it feeds the pipeline</SectionTitle>
            <p className="text-xs leading-relaxed text-slate-400">
              These weights drive the Molecule Optimization Lab composite score in real time. Raw weights are normalized
              by their positive sum, so relative emphasis is what matters — not the total.
            </p>
            <div className="mt-3 flex items-center gap-2">
              {isDefault ? (
                <Badge tone="slate" icon="Check">Default profile</Badge>
              ) : (
                <Badge tone="amber" icon="PenLine">Custom profile</Badge>
              )}
              <Badge tone="cyan" icon="RefreshCw">Live recompute</Badge>
            </div>
          </Panel>
        </div>
      </div>

      <Disclaimer tone="red">
        안전 페널티는 별도로 적용됩니다 — Safety penalty is applied <strong>separately and after</strong> the weighted
        composite (REVIEW_REQUIRED −15, BLOCKED effectively −100, plus an uncertainty penalty). It is <strong>not</strong> a
        tunable weight and cannot be down-weighted to advance a hazardous candidate.
      </Disclaimer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Checkpoint Registry
// ---------------------------------------------------------------------------

function CheckpointTab({ checkpoints }: { checkpoints: CheckpointEntry[] }) {
  if (checkpoints.length === 0) {
    return <EmptyState icon="Box" title="No checkpoints staged" />
  }
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {checkpoints.map((c) => (
        <Panel key={c.id} className="card-hover p-4">
          <div className="flex items-start justify-between gap-2">
            <div className="min-w-0">
              <div className="font-mono text-sm font-semibold text-white">{c.name}</div>
              <div className="mt-0.5 text-xs text-slate-400">{c.modelFamily}</div>
            </div>
            <Badge tone={CHECKPOINT_STATUS_TONE[c.status]} icon={c.status === 'validated' ? 'CircleCheck' : 'Box'}>
              {c.status}
            </Badge>
          </div>

          <div className="mt-3 rounded-lg border border-line bg-bg-raised/40 p-2.5">
            <KeyVal k="Training data" v={<span className="text-xs">{c.trainingData}</span>} />
            <div className="flex flex-wrap gap-1.5 pt-2">
              {c.metrics.map((mt) => (
                <span
                  key={mt.name}
                  className="rounded-md border border-line bg-bg-soft/50 px-2 py-0.5 font-mono text-[11px] tabular-nums text-slate-300"
                >
                  {mt.name} {fmtMetric(mt.value)}
                </span>
              ))}
            </div>
          </div>

          <p className="mt-3 text-xs leading-relaxed text-slate-500">{c.notes}</p>
          <div className="mt-3 flex items-center gap-2">
            <Badge tone="cyan" icon="FlaskConical">Demo</Badge>
            <span className="text-[10px] text-slate-600">{new Date(c.createdAt).toLocaleDateString()}</span>
          </div>
        </Panel>
      ))}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Evaluation Results
// ---------------------------------------------------------------------------

function EvaluationTab({ jobs }: { jobs: TrainingJob[] }) {
  const rows = jobs.flatMap((j) =>
    j.metrics.map((mt) => ({
      job: j.name,
      jobType: j.jobType,
      name: mt.name,
      value: mt.value,
      target: mt.target,
      unit: mt.unit,
    })),
  )
  if (rows.length === 0) {
    return <EmptyState icon="Gauge" title="No evaluation metrics" />
  }
  return (
    <div className="space-y-3">
      <Panel className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] border-collapse text-sm">
            <thead className="border-b border-line bg-bg-soft/50">
              <tr>
                <Th>Component job</Th>
                <Th>Type</Th>
                <Th>Metric</Th>
                <Th align="right">Value</Th>
                <Th align="right">Target</Th>
                <Th>Status</Th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => {
                const hasTarget = r.target !== undefined
                const met = hasTarget ? r.value >= (r.target as number) : true
                return (
                  <tr key={i} className="border-b border-line-soft transition-colors hover:bg-bg-hover/40">
                    <td className="px-3 py-2.5 font-mono text-xs text-slate-300">{r.job}</td>
                    <td className="px-3 py-2.5">
                      <Badge tone={JOB_TYPE_META[r.jobType].tone}>{JOB_TYPE_META[r.jobType].label}</Badge>
                    </td>
                    <td className="px-3 py-2.5 text-slate-200">{r.name}</td>
                    <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-white">
                      {fmtMetric(r.value)}
                      {r.unit ? <span className="ml-0.5 text-[10px] text-slate-500">{r.unit}</span> : null}
                    </td>
                    <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-slate-400">
                      {hasTarget ? fmtMetric(r.target as number) : '—'}
                    </td>
                    <td className="px-3 py-2.5">
                      {hasTarget ? (
                        met ? (
                          <Badge tone="green" icon="CheckCircle2">meets target</Badge>
                        ) : (
                          <Badge tone="amber" icon="AlertTriangle">below target</Badge>
                        )
                      ) : (
                        <Badge tone="slate" icon="Minus">reported</Badge>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </Panel>
      <Disclaimer tone="cyan">
        Metrics are reused from component training jobs and reflect Demo Simulation values only — targets are illustrative
        acceptance thresholds for the specialized open-source components, not orchestrator (Fable 5) performance.
      </Disclaimer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Deployment Plan
// ---------------------------------------------------------------------------

const DEPLOY_STEPS = [
  {
    icon: 'Server',
    title: 'Python worker services',
    desc: 'Each trained component (REINVENT4, ChemProp, reward model, tool router) runs as an isolated Python worker exposing a versioned inference endpoint — packaged in its own container with pinned dependencies.',
  },
  {
    icon: 'Plug',
    title: 'Uniform adapter interface',
    desc: 'The orchestrator never imports model code directly. It calls a stable adapter contract (predict / generate / score) so a checkpoint can be swapped, or a Demo fallback substituted, without touching agent logic.',
  },
  {
    icon: 'GitBranch',
    title: 'Checkpoint promotion',
    desc: 'Staged → validated → archived. Only validated checkpoints are eligible for the real-tool path; unvalidated ones resolve to Demo Simulation and are labeled as such at the output.',
  },
  {
    icon: 'ShieldCheck',
    title: 'Safety-in-the-loop',
    desc: 'Generation and scoring workers apply the safety penalty and hazardous-space constraints server-side, so no client weighting can bypass the gate. No synthesis routes are ever produced.',
  },
  {
    icon: 'Activity',
    title: 'Observability',
    desc: 'Every worker call is logged with latency, cost estimate, source label (real / fallback) and validation status, feeding the same audit trail the agents use.',
  },
]

function DeploymentTab() {
  return (
    <div className="space-y-4">
      <Panel className="relative overflow-hidden p-6 grid-bg">
        <div className="absolute -right-20 -top-20 h-56 w-56 rounded-full bg-helix-blue/10 blur-3xl" />
        <div className="relative">
          <Badge tone="violet" icon="Boxes">Deployment architecture</Badge>
          <h3 className="mt-3 max-w-2xl text-lg font-semibold text-white">
            Specialized components ship as Python workers behind a stable adapter interface
          </h3>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-slate-400">
            Fable 5 orchestrates; it does not embed model weights. Trained open-source components are served out-of-process
            and reached only through the adapter contract, keeping the planner model-agnostic and letting Demo fallbacks
            stand in transparently whenever a real checkpoint or key is unavailable.
          </p>
        </div>
      </Panel>

      <div className="grid gap-4 md:grid-cols-2">
        {DEPLOY_STEPS.map((s) => (
          <Panel key={s.title} className="p-4">
            <div className="mb-2 inline-flex rounded-lg border border-line bg-bg-raised p-2 text-helix-cyan">
              <Icon name={s.icon} size={18} />
            </div>
            <div className="text-sm font-semibold text-white">{s.title}</div>
            <div className="mt-1 text-xs leading-relaxed text-slate-400">{s.desc}</div>
          </Panel>
        ))}
      </div>

      <Disclaimer tone="slate">
        This describes the intended production topology. In this workbench everything runs as Demo Simulation — no worker
        is actually invoked and no model was trained.
      </Disclaimer>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function Training() {
  const trainingJobs = useAppStore((s) => s.trainingJobs)
  const datasets = useAppStore((s) => s.datasets)
  const checkpoints = useAppStore((s) => s.checkpoints)
  const [tab, setTab] = React.useState('jobs')

  const running = trainingJobs.filter((j) => j.status === 'running').length
  const complete = trainingJobs.filter((j) => j.status === 'complete').length

  return (
    <div className="space-y-4">
      <PageHeader
        title="Model Training Studio"
        subtitle="특화 오픈소스 컴포넌트의 학습/파인튜닝 스튜디오 — 데이터셋, 학습 잡, 점수 함수, 체크포인트, 평가, 배포 계획."
        icon="Cpu"
        actions={<Badge tone="cyan" icon="FlaskConical">Demo Simulation</Badge>}
      />

      {/* Prominent framing banner */}
      <Panel className="relative overflow-hidden p-5 grid-bg">
        <div className="absolute -left-16 -top-16 h-52 w-52 rounded-full bg-brand-500/10 blur-3xl" />
        <div className="relative flex flex-col gap-3 md:flex-row md:items-start">
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-brand-500/30 bg-brand-500/15 text-brand-300">
            <Icon name="Bot" size={20} />
          </span>
          <div className="min-w-0">
            <div className="mb-1 flex flex-wrap items-center gap-2">
              <span className="text-sm font-semibold text-white">Fable 5 is the orchestrator / planner</span>
              <Badge tone="green" icon="Sparkles">not trained here</Badge>
            </div>
            <p className="text-sm leading-relaxed text-slate-300">
              Only specialized open-source components — <strong>REINVENT4</strong> (generation), <strong>ChemProp</strong>{' '}
              (ADMET), the <strong>reward model</strong>, and the <strong>tool router</strong> — are trained or fine-tuned
              in this studio. The orchestrator LLM plans, delegates, and verifies; it is never fine-tuned on this data.
            </p>
            <div className="mt-2 inline-flex items-center gap-1.5 rounded-lg border border-helix-amber/30 bg-helix-amber/15 px-2.5 py-1 text-xs text-amber-300">
              <Icon name="FlaskConical" size={13} />
              Demo Simulation — no model was actually trained.
            </div>
          </div>
        </div>
      </Panel>

      {/* Summary stats */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Component jobs" value={trainingJobs.length} sub={`${complete} complete · ${running} running`} icon="Cpu" tone="cyan" />
        <StatCard label="Datasets" value={datasets.length} sub={`${datasets.filter((d) => d.leakageWarning).length} leakage review`} icon="Database" tone="violet" />
        <StatCard label="Checkpoints" value={checkpoints.length} sub={`${checkpoints.filter((c) => c.status === 'validated').length} validated`} icon="Box" tone="green" />
        <StatCard label="Scoring weights" value={WEIGHT_FIELDS.length} sub="Editable · live recompute" icon="SlidersHorizontal" tone="amber" />
      </div>

      <Tabs
        active={tab}
        onChange={setTab}
        tabs={[
          { id: 'datasets', label: 'Dataset Registry', icon: 'Database', count: datasets.length },
          { id: 'jobs', label: 'Training Jobs', icon: 'Cpu', count: trainingJobs.length },
          { id: 'scoring', label: 'Scoring Function Builder', icon: 'SlidersHorizontal' },
          { id: 'checkpoints', label: 'Checkpoint Registry', icon: 'Box', count: checkpoints.length },
          { id: 'evaluation', label: 'Evaluation Results', icon: 'Gauge' },
          { id: 'deployment', label: 'Deployment Plan', icon: 'Boxes' },
        ]}
      />

      {tab === 'datasets' && <DatasetTab datasets={datasets} />}
      {tab === 'jobs' && <TrainingJobsTab jobs={trainingJobs} />}
      {tab === 'scoring' && <ScoringBuilderTab />}
      {tab === 'checkpoints' && <CheckpointTab checkpoints={checkpoints} />}
      {tab === 'evaluation' && <EvaluationTab jobs={trainingJobs} />}
      {tab === 'deployment' && <DeploymentTab />}
    </div>
  )
}
