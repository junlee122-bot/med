import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  StatCard,
  ModeBadge,
  SourceBadge,
  ConfidenceMeter,
  KeyVal,
  Disclaimer,
  PageHeader,
  Tabs,
  EmptyState,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { CLINICAL_DISCLAIMER } from '@/lib/constants'
import type { SafetySeverity } from '@/types'

// Severity styling for the risk matrix (higher = worse).
const SEV: Record<SafetySeverity, { tone: string; label: string; icon: string; border: string; rank: number }> = {
  info: { tone: 'blue', label: 'Info', icon: 'Info', border: 'border-l-helix-blue', rank: 0 },
  low: { tone: 'green', label: 'Low', icon: 'ArrowDown', border: 'border-l-brand-500', rank: 1 },
  medium: { tone: 'amber', label: 'Medium', icon: 'Minus', border: 'border-l-helix-amber', rank: 2 },
  high: { tone: 'red', label: 'High', icon: 'ArrowUp', border: 'border-l-helix-red', rank: 3 },
  critical: { tone: 'pink', label: 'Critical', icon: 'TriangleAlert', border: 'border-l-helix-pink', rank: 4 },
}

const REG_STATUS: Record<'met' | 'partial' | 'gap' | 'not_assessed', { tone: string; icon: string; label: string }> = {
  met: { tone: 'green', icon: 'CheckCircle2', label: 'Met' },
  partial: { tone: 'amber', icon: 'CircleDot', label: 'Partial' },
  gap: { tone: 'red', icon: 'CircleAlert', label: 'Gap' },
  not_assessed: { tone: 'slate', icon: 'Circle', label: 'Not assessed' },
}

const JURIS: Record<'FDA' | 'MFDS' | 'EMA' | 'ICH', { tone: string; icon: string }> = {
  FDA: { tone: 'blue', icon: 'Landmark' },
  MFDS: { tone: 'cyan', icon: 'Building2' },
  EMA: { tone: 'violet', icon: 'Scale' },
  ICH: { tone: 'slate', icon: 'Globe' },
}

// RAG adapters — connected in demo mode against a bundled reference corpus.
const RAG_ADAPTERS = [
  {
    name: 'FDA Guidance RAG',
    icon: 'Landmark',
    corpus: 'Oncology IND-enabling, endpoint & CDx guidance',
    note: 'Retrieval over a bundled demo corpus. No live FDA connection in demo mode.',
  },
  {
    name: 'MFDS Guidance RAG',
    icon: 'Building2',
    corpus: 'KR IND dossier alignment & GCP references',
    note: 'Local-only reference set for Korean submission planning (demo).',
  },
  {
    name: 'ICH / EMA Reference RAG',
    icon: 'Scale',
    corpus: 'ICH E6(R2) GCP, E9 statistics references',
    note: 'High-level harmonization references (demo corpus).',
  },
]

// ClinicalTrials.gov precedent scan — clearly synthetic identifiers.
const PRECEDENTS = [
  {
    nct: 'DEMO-NCT-01',
    phase: 'Phase III',
    status: 'Completed',
    statusTone: 'green',
    title: 'Mutant-selective EGFR inhibitor vs standard-of-care in EGFR-altered advanced NSCLC',
    readout: 'Illustrative precedent: durable PFS benefit in biomarker-selected population.',
  },
  {
    nct: 'DEMO-NCT-02',
    phase: 'Phase II',
    status: 'Recruiting',
    statusTone: 'cyan',
    title: 'CNS-penetrant EGFR TKI in the brain-metastatic resistance cohort',
    readout: 'Illustrative precedent: CNS response endpoint in a resistance-stratified design.',
  },
]

function ListCard({ icon, tone, title, items }: { icon: string; tone: string; title: string; items: string[] }) {
  return (
    <div className="rounded-lg border border-line bg-bg-raised/40 p-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-medium text-slate-200">
        <Icon name={icon} size={15} className={`text-helix-${tone === 'green' ? 'cyan' : 'amber'}`} />
        {title}
      </div>
      <ul className="space-y-1.5">
        {items.map((it, i) => (
          <li key={i} className="flex gap-2 text-xs leading-relaxed text-slate-300">
            <Icon
              name={tone === 'green' ? 'Check' : 'X'}
              size={13}
              className={`mt-0.5 shrink-0 ${tone === 'green' ? 'text-brand-400' : 'text-helix-red'}`}
            />
            {it}
          </li>
        ))}
      </ul>
    </div>
  )
}

export function Clinical() {
  const navigate = useNavigate()
  const clinical = useAppStore((s) => s.clinical)
  const regulatory = useAppStore((s) => s.regulatory)
  const [tab, setTab] = React.useState<'clinical' | 'regulatory'>('clinical')

  const c = clinical[0]

  if (!c) {
    return (
      <div className="space-y-4">
        <PageHeader
          title="Clinical & Regulatory Strategy"
          subtitle="임상 · 규제 전략 초안 — 아직 생성된 프로토콜 드래프트가 없습니다."
          icon="Stethoscope"
        />
        <EmptyState
          icon="Stethoscope"
          title="No clinical draft yet"
          desc="Run the full workflow to generate a high-level clinical protocol draft and a regulatory gap analysis for the recommended candidate."
          action={<Button variant="primary" icon="Play" onClick={() => navigate('/cockpit')}>Open Agent Cockpit</Button>}
        />
      </div>
    )
  }

  const primaryEndpoints = c.endpoints.filter((e) => e.type === 'primary')
  const secondaryEndpoints = c.endpoints.filter((e) => e.type === 'secondary')
  const gaps = regulatory.filter((r) => r.status === 'gap')
  const partials = regulatory.filter((r) => r.status === 'partial')
  const phaseShort = c.phase.replace(/^Phase\s*/i, '').split('(')[0].trim()
  const phaseDetail = (c.phase.match(/\(([^)]+)\)/)?.[1] ?? '').trim()
  const sortedRisks = [...c.risks].sort((a, b) => SEV[b.severity].rank - SEV[a.severity].rank)
  const sortedReg = [...regulatory].sort(
    (a, b) => (REG_STATUS[a.status].tone === 'red' ? 0 : REG_STATUS[a.status].tone === 'amber' ? 1 : 2) -
      (REG_STATUS[b.status].tone === 'red' ? 0 : REG_STATUS[b.status].tone === 'amber' ? 1 : 2),
  )

  return (
    <div className="space-y-4">
      <PageHeader
        title="Clinical & Regulatory Strategy"
        subtitle="임상 개발 계획과 규제 갭 분석 — 권고 후보에 대한 고수준 연구 기획 산출물. Draft trial design, endpoints, biomarker plan, and a jurisdiction-by-jurisdiction checklist."
        icon="Stethoscope"
        actions={
          <div className="flex items-center gap-2">
            <SourceBadge source="demo" />
            <Button variant="secondary" icon="FileText" onClick={() => navigate('/reports')}>
              View in Report
            </Button>
          </div>
        }
      />

      <Disclaimer tone="amber">
        <span className="font-medium text-amber-200">Planning artifact only. </span>
        {CLINICAL_DISCLAIMER} 모든 시험 설계·엔드포인트·규제 판단은 자격을 갖춘 임상/규제 전문가의 검토를 반드시 거쳐야 합니다.
      </Disclaimer>

      {/* Stats */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <StatCard label="Proposed phase" value={phaseShort || c.phase} sub={phaseDetail || 'Adaptive, biomarker-selected'} icon="CalendarClock" tone="pink" />
        <StatCard
          label="Endpoints"
          value={c.endpoints.length}
          sub={`${primaryEndpoints.length} primary · ${secondaryEndpoints.length} secondary`}
          icon="Target"
          tone="cyan"
        />
        <StatCard
          label="Regulatory gaps"
          value={gaps.length}
          sub={`${partials.length} partial · ${regulatory.length} items assessed`}
          icon="AlertTriangle"
          tone={gaps.length > 0 ? 'red' : 'green'}
        />
      </div>

      <Tabs
        active={tab}
        onChange={(id) => setTab(id as typeof tab)}
        tabs={[
          { id: 'clinical', label: 'Clinical plan', icon: 'Stethoscope', count: c.endpoints.length },
          { id: 'regulatory', label: 'Regulatory checklist', icon: 'ClipboardCheck', count: regulatory.length },
        ]}
      />

      {tab === 'clinical' && (
        <div className="space-y-4">
          {/* TPP + confidence */}
          <Panel className="p-4">
            <SectionTitle
              icon="ClipboardList"
              right={
                <div className="flex items-center gap-2">
                  <Badge tone="slate" icon="Beaker">{c.candidateLabel}</Badge>
                  <SourceBadge source="demo" />
                </div>
              }
            >
              Target Product Profile · 목표 제품 프로파일 (Draft)
            </SectionTitle>
            <p className="text-sm leading-relaxed text-slate-300">{c.targetProductProfile}</p>
            <div className="mt-4 max-w-md">
              <ConfidenceMeter
                value={c.confidence}
                label="Draft confidence"
                reasons={['demo simulation', 'in-silico only', 'expert review required']}
              />
            </div>
          </Panel>

          {/* Indication / population / phase / design */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel className="p-4">
              <SectionTitle icon="Crosshair">Indication & population · 적응증 · 대상 환자군</SectionTitle>
              <KeyVal k="Indication" v={c.indication} />
              <KeyVal k="Population" v={<span className="text-right">{c.population}</span>} />
              <KeyVal k="Recommended candidate" v={c.candidateLabel} mono />
            </Panel>
            <Panel className="p-4">
              <SectionTitle icon="Workflow">High-level trial design · 시험 설계 개요</SectionTitle>
              <KeyVal k="Proposed phase" v={<Badge tone="pink" icon="CalendarClock">{c.phase}</Badge>} />
              <KeyVal k="Design" v="Adaptive, biomarker-selected; expansion strata" />
              <KeyVal k="Early-phase arm" v="Single-arm signal-seeking acceptable" />
              <KeyVal k="Statistical plan" v="Expert-led (SAP out of scope)" />
            </Panel>
          </div>

          {/* Endpoints table */}
          <Panel className="overflow-hidden">
            <div className="p-4 pb-0">
              <SectionTitle icon="Target" right={<Badge tone="cyan">Demo Simulation</Badge>}>
                Endpoints · 평가변수
              </SectionTitle>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <thead className="border-y border-line bg-bg-soft/50">
                  <tr>
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">Endpoint</th>
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">Type</th>
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {c.endpoints.map((e, i) => (
                    <tr key={i} className="border-b border-line-soft last:border-0">
                      <td className="px-4 py-2.5 font-medium text-slate-100">{e.name}</td>
                      <td className="px-4 py-2.5">
                        {e.type === 'primary' ? (
                          <Badge tone="cyan" icon="Star">Primary</Badge>
                        ) : (
                          <Badge tone="slate" icon="CircleDot">Secondary</Badge>
                        )}
                      </td>
                      <td className="px-4 py-2.5 text-xs leading-relaxed text-slate-400">{e.description}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Panel>

          {/* Inclusion / exclusion */}
          <Panel className="p-4">
            <SectionTitle icon="ListChecks">Eligibility logic · 선정 · 제외 기준</SectionTitle>
            <div className="grid gap-3 md:grid-cols-2">
              <ListCard icon="UserCheck" tone="green" title="Inclusion logic" items={c.inclusionLogic} />
              <ListCard icon="UserX" tone="red" title="Exclusion logic" items={c.exclusionLogic} />
            </div>
            <div className="mt-2 text-[11px] text-slate-500">
              Eligibility thresholds are expert-defined; the above is a structured planning summary, not a protocol.
            </div>
          </Panel>

          {/* Biomarker + comparator */}
          <div className="grid gap-4 lg:grid-cols-2">
            <Panel className="p-4">
              <SectionTitle icon="Dna">Biomarker strategy · 바이오마커 전략</SectionTitle>
              <p className="text-sm leading-relaxed text-slate-300">{c.biomarkerStrategy}</p>
            </Panel>
            <Panel className="p-4">
              <SectionTitle icon="GitCompare">Comparator strategy · 대조군 전략</SectionTitle>
              <p className="text-sm leading-relaxed text-slate-300">{c.comparator}</p>
            </Panel>
          </div>

          {/* Risk matrix */}
          <Panel className="p-4">
            <SectionTitle
              icon="ShieldAlert"
              right={<Badge tone="slate" icon="Layers">{c.risks.length} risks</Badge>}
            >
              Key risks & mitigations · 주요 리스크 매트릭스
            </SectionTitle>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {sortedRisks.map((r, i) => {
                const sev = SEV[r.severity]
                return (
                  <div key={i} className={`rounded-lg border border-line ${sev.border} border-l-2 bg-bg-raised/40 p-3`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="text-sm font-medium leading-snug text-slate-100">{r.risk}</div>
                      <Badge tone={sev.tone} icon={sev.icon} className="shrink-0">{sev.label}</Badge>
                    </div>
                    <div className="mt-2 text-xs leading-relaxed text-slate-400">
                      <span className="text-slate-500">Mitigation · </span>
                      {r.mitigation}
                    </div>
                  </div>
                )
              })}
            </div>
          </Panel>

          {/* ClinicalTrials.gov precedent scan */}
          <Panel className="p-4">
            <SectionTitle
              icon="Search"
              right={<Badge tone="cyan" icon="FlaskConical">Demo Simulation</Badge>}
            >
              ClinicalTrials.gov precedent scan · 선행 임상 요약
            </SectionTitle>
            <div className="grid gap-3 md:grid-cols-2">
              {PRECEDENTS.map((p) => (
                <div key={p.nct} className="rounded-lg border border-line bg-bg-raised/40 p-3">
                  <div className="mb-1.5 flex items-center justify-between gap-2">
                    <span className="font-mono text-xs font-semibold tabular-nums text-helix-cyan">{p.nct}</span>
                    <div className="flex items-center gap-1.5">
                      <Badge tone="violet">{p.phase}</Badge>
                      <Badge tone={p.statusTone} icon={p.status === 'Completed' ? 'CheckCircle2' : 'CircleDot'}>{p.status}</Badge>
                    </div>
                  </div>
                  <div className="text-sm leading-snug text-slate-200">{p.title}</div>
                  <div className="mt-1.5 text-[11px] leading-relaxed text-slate-500">{p.readout}</div>
                </div>
              ))}
            </div>
            <div className="mt-2 text-[11px] text-slate-500">
              Identifiers are synthetic (DEMO-NCT-*). No live ClinicalTrials.gov query is made in demo mode.
            </div>
          </Panel>
        </div>
      )}

      {tab === 'regulatory' && (
        <div className="space-y-4">
          {/* Regulatory checklist table */}
          <Panel className="overflow-hidden">
            <div className="p-4 pb-0">
              <SectionTitle
                icon="ClipboardCheck"
                right={
                  <div className="flex items-center gap-1.5">
                    <Badge tone="red" icon="CircleAlert">{gaps.length} gap</Badge>
                    <Badge tone="amber" icon="CircleDot">{partials.length} partial</Badge>
                  </div>
                }
              >
                Regulatory checklist · 규제 체크리스트
              </SectionTitle>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px] border-collapse text-sm">
                <thead className="border-y border-line bg-bg-soft/50">
                  <tr>
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">Jurisdiction</th>
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">Checklist item</th>
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">Status</th>
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">Risk</th>
                    <th className="px-4 py-2 text-left text-[11px] font-semibold uppercase tracking-wide text-slate-400">Evidence needed</th>
                  </tr>
                </thead>
                <tbody>
                  {sortedReg.map((r) => {
                    const st = REG_STATUS[r.status]
                    const j = JURIS[r.jurisdiction]
                    const sev = SEV[r.riskLevel]
                    return (
                      <tr key={r.id} className="border-b border-line-soft align-top last:border-0">
                        <td className="px-4 py-3">
                          <Badge tone={j.tone} icon={j.icon}>{r.jurisdiction}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <div className="font-medium text-slate-100">{r.checklistItem}</div>
                          <div className="mt-0.5 text-[11px] leading-relaxed text-slate-500">{r.notes}</div>
                        </td>
                        <td className="px-4 py-3">
                          <Badge tone={st.tone} icon={st.icon}>{st.label}</Badge>
                        </td>
                        <td className="px-4 py-3">
                          <Badge tone={sev.tone} icon={sev.icon}>{sev.label}</Badge>
                        </td>
                        <td className="px-4 py-3 text-xs leading-relaxed text-slate-400">{r.evidenceNeeded}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Panel>

          {/* RAG adapter status */}
          <Panel className="p-4">
            <SectionTitle icon="Database" right={<ModeBadge mode="demo" />}>
              FDA / MFDS RAG adapter status · 규제 검색 어댑터
            </SectionTitle>
            <div className="grid gap-3 md:grid-cols-3">
              {RAG_ADAPTERS.map((a) => (
                <div key={a.name} className="rounded-lg border border-line bg-bg-raised/40 p-3">
                  <div className="mb-2 flex items-center justify-between">
                    <div className="inline-flex rounded-lg border border-line bg-bg-raised p-2 text-helix-cyan">
                      <Icon name={a.icon} size={18} />
                    </div>
                    <span className="inline-flex items-center gap-1.5 text-[11px] font-medium text-brand-300">
                      <span className="h-1.5 w-1.5 rounded-full bg-brand-500" />
                      Connected · Demo
                    </span>
                  </div>
                  <div className="text-sm font-semibold text-white">{a.name}</div>
                  <div className="mt-1 text-xs leading-relaxed text-slate-400">{a.corpus}</div>
                  <div className="mt-2 border-t border-line-soft pt-2 text-[11px] leading-relaxed text-slate-500">{a.note}</div>
                </div>
              ))}
            </div>
          </Panel>

          <Disclaimer tone="slate">
            RAG adapters retrieve from a bundled reference corpus for demonstration. Live regulatory portals are not queried in
            demo mode, and no output constitutes a regulatory determination — all gap/partial calls require qualified regulatory review.
          </Disclaimer>
        </div>
      )}
    </div>
  )
}
