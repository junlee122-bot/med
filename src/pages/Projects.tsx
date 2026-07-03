import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  StatCard,
  ModeBadge,
  SafetyBadge,
  PageHeader,
  EmptyState,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import type { DiscoveryGoal, Project, ProjectStatus } from '@/types'

const DEMO_ID = 'proj-nsclc-egfr-demo'

const GOAL_LABEL: Record<DiscoveryGoal, { label: string; icon: string }> = {
  target_discovery: { label: 'Target Discovery', icon: 'Crosshair' },
  repurposing: { label: 'Repurposing', icon: 'Recycle' },
  de_novo: { label: 'De Novo Design', icon: 'Atom' },
  optimization: { label: 'Lead Optimization', icon: 'Sliders' },
  clinical_strategy: { label: 'Clinical Strategy', icon: 'Stethoscope' },
  full_pipeline: { label: 'Full Pipeline', icon: 'Workflow' },
}

const STATUS_TONE: Record<ProjectStatus, { tone: string; icon: string; label: string }> = {
  draft: { tone: 'slate', icon: 'PencilLine', label: 'Draft' },
  ready: { tone: 'blue', icon: 'CircleDot', label: 'Ready' },
  running: { tone: 'cyan', icon: 'Loader', label: 'Running' },
  complete: { tone: 'green', icon: 'CircleCheck', label: 'Complete' },
  blocked: { tone: 'red', icon: 'ShieldX', label: 'Blocked' },
  error: { tone: 'red', icon: 'TriangleAlert', label: 'Error' },
}

function fmtDate(iso: string) {
  const d = new Date(iso)
  return isNaN(d.getTime()) ? '—' : d.toLocaleDateString()
}

export function Projects() {
  const navigate = useNavigate()
  const projects = useAppStore((s) => s.projects)
  const workflows = useAppStore((s) => s.workflows)
  const molecules = useAppStore((s) => s.molecules)
  const evidence = useAppStore((s) => s.evidence)
  const reports = useAppStore((s) => s.reports)
  const activeProjectId = useAppStore((s) => s.activeProjectId)
  const setActiveProject = useAppStore((s) => s.setActiveProject)
  const startWorkflow = useAppStore((s) => s.startWorkflow)
  const deleteProject = useAppStore((s) => s.deleteProject)

  const topCandidate = React.useMemo(
    () =>
      molecules
        .filter((m) => m.recommendation === 'advance')
        .sort((a, b) => b.compositeScore - a.compositeScore)[0],
    [molecules],
  )

  const runningCount = projects.filter((p) => p.status === 'running').length
  const completeCount = projects.filter((p) => p.status === 'complete').length

  const openCockpit = (id: string) => {
    setActiveProject(id)
    navigate('/cockpit')
  }
  const continueWorkflow = (id: string) => {
    startWorkflow(id)
    navigate('/cockpit')
  }
  const exportSummary = (id: string) => {
    setActiveProject(id)
    navigate('/reports')
  }
  const openDemo = () => {
    setActiveProject(DEMO_ID)
    navigate('/cockpit')
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="프로젝트 대시보드 · Project Dashboard"
        subtitle="발견 프로젝트 워크스페이스 — 질환 정의, 워크플로 상태, 안전성 게이트, 리포트 준비 상태를 한 곳에서 관리합니다. Every scientific readout is provenance-labeled; the seeded NSCLC/EGFR project is a Demo Simulation."
        icon="FolderKanban"
        actions={
          <>
            <Button variant="secondary" icon="FlaskConical" onClick={openDemo}>
              Open Demo Project
            </Button>
            <Button variant="primary" icon="Plus" onClick={() => navigate('/projects/new')}>
              New Project
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <StatCard label="Total projects" value={projects.length} sub="1 seeded demo workspace" icon="FolderKanban" tone="cyan" />
        <StatCard label="Running" value={runningCount} sub="Active workflow executions" icon="Loader" tone="blue" />
        <StatCard label="Complete" value={completeCount} sub="Full-pipeline runs finished" icon="CircleCheck" tone="green" />
      </div>

      {projects.length === 0 ? (
        <EmptyState
          icon="FolderPlus"
          title="No projects yet"
          desc="Create a discovery project to define a disease, indication, and evaluation plan — or open the seeded demo workspace."
          action={
            <div className="flex gap-2">
              <Button variant="secondary" icon="FlaskConical" onClick={openDemo}>Open Demo Project</Button>
              <Button variant="primary" icon="Plus" onClick={() => navigate('/projects/new')}>New Project</Button>
            </div>
          }
        />
      ) : (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <ProjectCard
              key={p.id}
              p={p}
              isDemo={p.id === DEMO_ID}
              isActive={p.id === activeProjectId}
              workflow={workflows.find((w) => w.projectId === p.id)}
              evidenceConf={avgEvidenceConf(evidence, p.id)}
              reportCount={reports.filter((r) => r.projectId === p.id).length}
              topLabel={p.id === activeProjectId || p.seeded ? topCandidate?.label : undefined}
              onOpen={() => openCockpit(p.id)}
              onContinue={() => continueWorkflow(p.id)}
              onExport={() => exportSummary(p.id)}
              onDelete={() => deleteProject(p.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function avgEvidenceConf(evidence: { projectId: string; confidence: number }[], projectId: string) {
  const rows = evidence.filter((e) => e.projectId === projectId)
  if (rows.length === 0) return null
  return rows.reduce((a, e) => a + e.confidence, 0) / rows.length
}

function ProjectCard({
  p,
  isDemo,
  isActive,
  workflow,
  evidenceConf,
  reportCount,
  topLabel,
  onOpen,
  onContinue,
  onExport,
  onDelete,
}: {
  p: Project
  isDemo: boolean
  isActive: boolean
  workflow?: { safetyStatus: import('@/types').SafetyStatus; confidence: number } | undefined
  evidenceConf: number | null
  reportCount: number
  topLabel?: string
  onOpen: () => void
  onContinue: () => void
  onExport: () => void
  onDelete: () => void
}) {
  const goal = GOAL_LABEL[p.discoveryGoal]
  const status = STATUS_TONE[p.status]

  return (
    <Panel className={`card-hover flex flex-col p-5 ${isActive ? 'ring-1 ring-helix-cyan/40' : ''}`}>
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="truncate text-base font-semibold text-white">{p.name}</h3>
            {isActive && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-helix-cyan" title="Active project" />}
          </div>
          <div className="mt-0.5 truncate text-xs text-slate-400">
            {p.disease} · {p.indication}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <ModeBadge mode={p.mode} small />
          {!isDemo && (
            <Button variant="ghost" icon="Trash2" onClick={onDelete} className="!px-2 text-slate-500 hover:!text-helix-red" title="Delete project" />
          )}
        </div>
      </div>

      {/* Meta badges */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5">
        <Badge tone={status.tone} icon={status.icon}>{status.label}</Badge>
        <Badge tone="violet" icon={goal.icon}>{goal.label}</Badge>
        {isDemo && <Badge tone="cyan" icon="Sparkles">Seeded Demo</Badge>}
      </div>

      {/* Summary */}
      <p className="mt-3 line-clamp-2 text-xs leading-relaxed text-slate-500">{p.summary}</p>

      {/* Stat grid */}
      <div className="mt-4 grid grid-cols-2 gap-2">
        <CardStat label="Safety gate">
          {workflow ? (
            <SafetyBadge status={workflow.safetyStatus} small />
          ) : (
            <span className="text-xs text-slate-600">Not yet run</span>
          )}
        </CardStat>
        <CardStat label="Evidence conf.">
          {evidenceConf === null ? (
            <span className="text-xs text-slate-600">—</span>
          ) : (
            <span className="font-mono text-sm tabular-nums text-slate-200">{(evidenceConf * 100).toFixed(0)}%</span>
          )}
        </CardStat>
        <CardStat label="Top candidate">
          {topLabel ? (
            <span className="flex items-center gap-1 truncate font-mono text-xs text-brand-300">
              <Icon name="Atom" size={12} className="shrink-0" />
              {topLabel}
            </span>
          ) : (
            <span className="text-xs text-slate-600">Run workflow</span>
          )}
        </CardStat>
        <CardStat label="Reports">
          <span className="flex items-center gap-1 text-xs text-slate-200">
            <Icon name="FileText" size={12} className={reportCount > 0 ? 'text-helix-amber' : 'text-slate-600'} />
            {reportCount > 0 ? `${reportCount} ready` : 'None built'}
          </span>
        </CardStat>
      </div>

      {/* Footer */}
      <div className="mt-4 flex items-center justify-between border-t border-line-soft pt-3 text-[11px] text-slate-500">
        <span className="flex items-center gap-1">
          <Icon name="Clock" size={11} />
          Updated {fmtDate(p.updatedAt)}
        </span>
        <span className="truncate font-mono">{p.owner}</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-2">
        <Button variant="primary" icon="Cpu" onClick={onOpen} className="flex-1">Open Cockpit</Button>
        <Button variant="secondary" icon="Play" onClick={onContinue} title="Launch a fresh workflow run for this project">Continue Workflow</Button>
        <Button variant="ghost" icon="FileDown" onClick={onExport} title="Go to reports" className="!px-2.5" />
      </div>
    </Panel>
  )
}

function CardStat({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-line bg-bg-raised/40 px-2.5 py-2">
      <div className="text-[10px] uppercase tracking-wide text-slate-500">{label}</div>
      <div className="mt-1 flex items-center">{children}</div>
    </div>
  )
}
