import React from 'react'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  StatCard,
  ModeBadge,
  SourceBadge,
  Disclaimer,
  EmptyState,
  PageHeader,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { REPORT_META } from '@/lib/reportTemplates'
import type { Report, ReportType, AppMode } from '@/types'

// Fixed presentation order + per-type visual identity.
const REPORT_TYPES: ReportType[] = [
  'judge_demo',
  'technical_architecture',
  'candidate_package',
  'ethics_safety',
  'evaluation_benchmark',
  'business_value',
  'full_proposal',
]

const REPORT_UI: Record<ReportType, { icon: string; tone: string }> = {
  judge_demo: { icon: 'Gavel', tone: 'cyan' },
  technical_architecture: { icon: 'Cpu', tone: 'blue' },
  candidate_package: { icon: 'Atom', tone: 'green' },
  ethics_safety: { icon: 'ShieldCheck', tone: 'red' },
  evaluation_benchmark: { icon: 'Gauge', tone: 'violet' },
  business_value: { icon: 'TrendingUp', tone: 'amber' },
  full_proposal: { icon: 'Layers', tone: 'pink' },
}

function fmt(iso: string): string {
  try {
    return new Date(iso).toLocaleString()
  } catch {
    return iso
  }
}

function download(filename: string, content: string, mime: string) {
  const blob = new Blob([content], { type: mime })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

export function Reports() {
  const reports = useAppStore((s) => s.reports)
  const buildReport = useAppStore((s) => s.buildReport)
  const removeReport = useAppStore((s) => s.removeReport)
  const mode = useAppStore((s) => s.settings.mode)

  const [selectedType, setSelectedType] = React.useState<ReportType | null>(() => reports[0]?.type ?? null)

  const byType = React.useMemo(() => {
    const m = new Map<ReportType, Report>()
    for (const r of reports) if (!m.has(r.type)) m.set(r.type, r)
    return m
  }, [reports])

  const selected = selectedType ? byType.get(selectedType) ?? null : null

  const generate = (type: ReportType) => {
    buildReport(type)
    setSelectedType(type)
  }

  const selectType = (type: ReportType) => {
    if (byType.has(type)) setSelectedType(type)
    else generate(type)
  }

  const generateAll = () => {
    for (const t of REPORT_TYPES) buildReport(t)
    setSelectedType('judge_demo')
  }

  const coverage = Math.round((byType.size / REPORT_TYPES.length) * 100)
  const mostRecent = reports[0]

  return (
    <div className="space-y-4">
      {/* Print-only styling: isolate the report document, drop dark chrome for paper. */}
      <style>{`
        @media print {
          body * { visibility: hidden !important; }
          .report-print-area, .report-print-area * { visibility: visible !important; }
          .report-print-area {
            position: absolute; left: 0; top: 0; width: 100%;
            padding: 0; margin: 0; border: none; box-shadow: none; background: #fff !important;
          }
          .report-print-area pre {
            max-height: none !important; overflow: visible !important;
            color: #111 !important; background: #fff !important; border: none !important;
          }
          .report-print-area .report-doc-title { color: #111 !important; }
          .report-print-hide { display: none !important; }
        }
      `}</style>

      <PageHeader
        title="Report Studio"
        subtitle="심사위원·기술·후보·윤리·평가·사업 리포트를 실행 상태에서 즉시 생성. Compose judge-ready deliverables from the live workflow state — export as Markdown, JSON audit, or PDF."
        icon="FileText"
        actions={
          <Button variant="primary" icon="Sparkles" onClick={generateAll}>
            Generate All
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Reports generated" value={byType.size} sub={`of ${REPORT_TYPES.length} templates`} icon="FileCheck" tone="green" />
        <StatCard label="Templates" value={REPORT_TYPES.length} sub="judge · tech · candidate · ethics · eval · business · full" icon="LayoutList" tone="cyan" />
        <StatCard label="Coverage" value={`${coverage}%`} sub="of the report suite" icon="PieChart" tone="violet" />
        <StatCard
          label="Last generated"
          value={mostRecent ? <span className="text-base font-mono tabular-nums">{fmt(mostRecent.createdAt).split(',')[1]?.trim() ?? fmt(mostRecent.createdAt)}</span> : '—'}
          sub={mostRecent ? REPORT_META[mostRecent.type].title : 'none yet'}
          icon="Clock"
          tone="amber"
        />
      </div>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,340px)_1fr]">
        {/* Template list */}
        <div className="space-y-2">
          <SectionTitle icon="Files">리포트 템플릿 · Templates</SectionTitle>
          {REPORT_TYPES.map((type) => {
            const meta = REPORT_META[type]
            const ui = REPORT_UI[type]
            const existing = byType.get(type)
            const isSelected = selectedType === type
            return (
              <div
                key={type}
                role="button"
                tabIndex={0}
                onClick={() => selectType(type)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault()
                    selectType(type)
                  }
                }}
                className={`panel cursor-pointer p-3 transition-colors ${
                  isSelected ? 'ring-1 ring-helix-cyan/50 bg-bg-hover/40' : 'hover:bg-bg-hover/20'
                }`}
              >
                <div className="flex items-start gap-3">
                  <div className={`shrink-0 rounded-lg border p-2 ${
                    ui.tone === 'cyan' ? 'border-helix-cyan/30 bg-helix-cyan/10 text-helix-cyan'
                    : ui.tone === 'blue' ? 'border-helix-blue/30 bg-helix-blue/10 text-blue-300'
                    : ui.tone === 'green' ? 'border-brand-500/30 bg-brand-500/10 text-brand-300'
                    : ui.tone === 'red' ? 'border-helix-red/30 bg-helix-red/10 text-red-300'
                    : ui.tone === 'violet' ? 'border-helix-violet/30 bg-helix-violet/10 text-violet-300'
                    : ui.tone === 'amber' ? 'border-helix-amber/30 bg-helix-amber/10 text-amber-300'
                    : 'border-helix-pink/30 bg-helix-pink/10 text-pink-300'
                  }`}>
                    <Icon name={ui.icon} size={18} />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-white">{meta.subtitle}</div>
                    <div className="truncate text-[11px] text-slate-400">{meta.title}</div>
                    <div className="mt-1.5">
                      {existing ? (
                        <Badge tone="green" icon="CircleCheck" className="text-[10px]">
                          Generated · {fmt(existing.createdAt).split(',')[1]?.trim() ?? 'ready'}
                        </Badge>
                      ) : (
                        <Badge tone="slate" icon="Circle" className="text-[10px]">
                          Not generated
                        </Badge>
                      )}
                    </div>
                  </div>
                </div>
                <span onClick={(e) => e.stopPropagation()} className="mt-2.5 flex items-center gap-2">
                  <Button
                    variant={existing ? 'secondary' : 'primary'}
                    icon={existing ? 'RefreshCw' : 'Play'}
                    onClick={() => generate(type)}
                    className="flex-1 !justify-center text-xs"
                  >
                    {existing ? 'Regenerate' : 'Generate'}
                  </Button>
                  {existing && (
                    <Button
                      variant="ghost"
                      icon="Trash2"
                      title="Remove report"
                      className="!px-2"
                      onClick={() => {
                        removeReport(existing.id)
                        if (selectedType === type) setSelectedType(null)
                      }}
                    />
                  )}
                </span>
              </div>
            )
          })}
          <Disclaimer tone="slate">
            모든 리포트에는 인간 책임·임상·합성경로 비표시 고지가 자동 포함됩니다. Every report embeds the human-responsibility
            statement, clinical disclaimer, and no-synthesis-route policy.
          </Disclaimer>
        </div>

        {/* Preview */}
        <div>
          {selected ? (
            <ReportPreview report={selected} mode={mode} onRegenerate={() => generate(selected.type)} />
          ) : (
            <Panel className="p-6">
              <EmptyState
                icon="FileText"
                title="No report selected"
                desc="Pick a template on the left, or generate the judge-facing demo report to preview and export it. Reports are built from the current project's live workflow state."
                action={
                  <Button variant="primary" icon="Sparkles" onClick={() => generate('judge_demo')}>
                    Generate Judge Demo Report
                  </Button>
                }
              />
            </Panel>
          )}
        </div>
      </div>
    </div>
  )
}

function ReportPreview({
  report,
  mode,
  onRegenerate,
}: {
  report: Report
  mode: AppMode
  onRegenerate: () => void
}) {
  const meta = REPORT_META[report.type]
  const ui = REPORT_UI[report.type]
  const lines = report.markdown.split('\n').length

  return (
    <Panel className="report-print-area overflow-hidden">
      {/* Document header / toolbar */}
      <div className="border-b border-line p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="report-doc-title flex items-center gap-2 text-lg font-semibold text-white">
              <Icon name={ui.icon} size={18} className="text-helix-cyan" />
              {meta.title}
            </div>
            <div className="mt-0.5 text-xs text-slate-400">{meta.subtitle}</div>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <Badge tone={ui.tone} icon="Tag">{report.type}</Badge>
              <ModeBadge mode={mode} small />
              <SourceBadge source={mode === 'real' ? 'real' : 'demo'} />
              <Badge tone="slate" icon="Clock">Generated {fmt(report.createdAt)}</Badge>
              <Badge tone="slate" icon="AlignLeft">{lines.toLocaleString()} lines</Badge>
            </div>
          </div>
          <div className="report-print-hide flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              icon="FileDown"
              onClick={() => download(`helixforge-${report.type}.md`, report.markdown, 'text/markdown;charset=utf-8')}
            >
              Download .md
            </Button>
            <Button
              variant="secondary"
              icon="Braces"
              onClick={() => download(`helixforge-${report.type}-audit.json`, report.jsonAudit, 'application/json')}
            >
              Download JSON
            </Button>
            <Button variant="secondary" icon="Printer" onClick={() => window.print()}>
              Print / PDF
            </Button>
            <Button variant="ghost" icon="RefreshCw" title="Regenerate from current state" onClick={onRegenerate} className="!px-2" />
          </div>
        </div>
      </div>

      {/* Rendered markdown (source view — no markdown lib) */}
      <div className="p-4">
        <pre className="max-h-[68vh] overflow-y-auto rounded-lg border border-line bg-bg-raised/60 p-4 font-mono text-[12.5px] leading-relaxed text-slate-200 whitespace-pre-wrap break-words">
          {report.markdown}
        </pre>
      </div>

      <div className="report-print-hide space-y-2 border-t border-line p-4">
        <Disclaimer tone="cyan">
          이 리포트에는 인간 최종 책임·임상 고지·합성 경로 비표시 정책이 이미 포함되어 있습니다. This document already embeds the
          required disclaimers. PDF export opens your browser's print dialog — choose "Save as PDF" as the destination.
        </Disclaimer>
      </div>
    </Panel>
  )
}
