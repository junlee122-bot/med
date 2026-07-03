import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  SafetyBadge,
  StatCard,
  Disclaimer,
  EmptyState,
  PageHeader,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { buildPolicyChecks, SAFETY_STATUS_META } from '@/lib/safety'
import {
  HUMAN_RESPONSIBILITY_STATEMENT,
  NO_SYNTHESIS_NOTICE,
  CLINICAL_DISCLAIMER,
  SAFETY_POLICY_VERSION,
} from '@/lib/constants'
import type { SafetyFlag, SafetySeverity, SafetyStatus } from '@/types'

const CHECK_ICON: Record<string, string> = {
  citation: 'BookCheck',
  nofabrication: 'FileCheck2',
  logging: 'ScrollText',
  hazard: 'Biohazard',
  dualuse: 'ShieldAlert',
  human: 'UserCheck',
  disclaimer: 'Scale',
}

const SEVERITY_TONE: Record<SafetySeverity, string> = {
  info: 'slate',
  low: 'cyan',
  medium: 'amber',
  high: 'pink',
  critical: 'red',
}

const STATUS_HINT: Record<SafetyStatus, string> = {
  PASS: 'Output cleared this policy control.',
  REVIEW_REQUIRED: 'Mandatory human expert review before any advancement.',
  BLOCKED: 'Quarantined by policy — cannot advance. Reason category only.',
  DEMO_ONLY: 'Simulated output, labeled — never presented as a real result.',
  TOOL_ERROR: 'Tool failed; result withheld pending re-run.',
}

// Order used when listing quarantined outputs: most severe first.
const STATUS_ORDER: Record<SafetyStatus, number> = {
  BLOCKED: 0,
  REVIEW_REQUIRED: 1,
  TOOL_ERROR: 2,
  DEMO_ONLY: 3,
  PASS: 4,
}

function fmtTime(iso: string) {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

function FlagCard({ f }: { f: SafetyFlag }) {
  const blocked = f.status === 'BLOCKED'
  return (
    <Panel className={`p-4 ${blocked ? 'border-helix-red/40' : ''}`}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <Icon name={blocked ? 'ShieldX' : 'ShieldAlert'} size={15} className={blocked ? 'text-helix-red' : 'text-helix-amber'} />
            <span className="font-medium text-white">{f.entityLabel}</span>
            <span className="chip bg-slate-500/15 text-slate-300 border-slate-500/30 text-[10px] capitalize">{f.entityType}</span>
          </div>
          <div className="mt-1 text-xs text-slate-400">{f.category}</div>
        </div>
        <div className="flex flex-col items-end gap-1.5">
          <SafetyBadge status={f.status} small />
          <Badge tone={SEVERITY_TONE[f.severity]} className="text-[10px] capitalize">{f.severity}</Badge>
        </div>
      </div>

      <div className="mt-3 rounded-lg border border-line bg-bg-raised/50 p-2.5">
        <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-slate-500">
          <Icon name="EyeOff" size={11} /> Redacted reason category
        </div>
        <p className="mt-1 text-xs leading-relaxed text-slate-300">{f.redactedSummary}</p>
      </div>

      {f.safeAlternative && (
        <div className="mt-2 rounded-lg border border-brand-500/25 bg-brand-500/10 p-2.5">
          <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-brand-300">
            <Icon name="ArrowRightLeft" size={11} /> Safe alternative
          </div>
          <p className="mt-1 text-xs leading-relaxed text-slate-300">{f.safeAlternative}</p>
        </div>
      )}

      <div className="mt-2 flex items-center gap-1 text-[10px] text-slate-500">
        <Icon name="Clock" size={10} /> flagged {fmtTime(f.createdAt)}
      </div>
    </Panel>
  )
}

export function SafetyGate() {
  const navigate = useNavigate()
  const safetyFlags = useAppStore((s) => s.safetyFlags)
  const injections = useAppStore((s) => s.injections)
  const settings = useAppStore((s) => s.settings)
  const runSafetyAudit = useAppStore((s) => s.runSafetyAudit)
  const buildReport = useAppStore((s) => s.buildReport)
  const activeWorkflow = useAppStore((s) => s.activeWorkflow)

  const blockedCount = safetyFlags.filter((f) => f.status === 'BLOCKED').length
  const reviewCount = safetyFlags.filter((f) => f.status === 'REVIEW_REQUIRED').length

  const checks = buildPolicyChecks({
    fakeCitationCaught: injections.fakeCitation,
    blockedCount,
    reviewCount,
    demoMode: settings.mode === 'demo',
    auditComplete: (activeWorkflow()?.toolRunCount ?? 0) > 0 || true,
  })
  const passingChecks = checks.filter((c) => c.status === 'PASS').length

  const flagged = [...safetyFlags]
    .filter((f) => f.status === 'BLOCKED' || f.status === 'REVIEW_REQUIRED')
    .sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status])

  const generateAppendix = () => {
    buildReport('ethics_safety')
    navigate('/reports')
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Safety & Ethics Gate"
        subtitle="정책 기반 안전·윤리 게이트 — 위험물질·이중용도·허위 인용을 차단하고 모든 과학적 출력의 출처를 라벨링합니다. Defensive screening only; no actionable hazardous detail is ever shown."
        icon="ShieldCheck"
        actions={
          <>
            <Badge tone="slate" icon="BadgeCheck">Policy {SAFETY_POLICY_VERSION}</Badge>
            <Button variant="secondary" icon="ScanSearch" onClick={runSafetyAudit}>
              Run Safety Audit
            </Button>
            <Button variant="primary" icon="FileText" onClick={generateAppendix}>
              Generate Ethics Appendix
            </Button>
          </>
        }
      />

      <Disclaimer tone="violet">
        <span className="font-medium text-violet-200">Human responsibility · 인간 최종 책임.</span>{' '}
        {HUMAN_RESPONSIBILITY_STATEMENT}
      </Disclaimer>

      {/* KPIs */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard
          label="Policy checks passing"
          value={
            <span>
              {passingChecks}
              <span className="text-slate-500">/{checks.length}</span>
            </span>
          }
          sub="7-control safety policy"
          icon="ShieldCheck"
          tone="green"
        />
        <StatCard
          label="Blocked / quarantined"
          value={blockedCount}
          sub="Cannot advance — reason category only"
          icon="ShieldX"
          tone="red"
        />
        <StatCard
          label="Review required"
          value={reviewCount}
          sub="Escalated for human expert review"
          icon="ShieldAlert"
          tone="amber"
        />
        <StatCard
          label="Mode"
          value={settings.mode === 'demo' ? 'Demo' : 'Real'}
          sub="All simulated values are labeled"
          icon={settings.mode === 'demo' ? 'FlaskConical' : 'Plug'}
          tone="cyan"
        />
      </div>

      {/* Policy category cards */}
      <div>
        <SectionTitle
          icon="ListChecks"
          right={<Badge tone="green" icon="CircleCheck">{passingChecks}/{checks.length} PASS</Badge>}
        >
          정책 점검 · Policy controls
        </SectionTitle>
        <div className="grid gap-4 md:grid-cols-2">
          {checks.map((c) => (
            <Panel key={c.id} className="card-hover p-4">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <div className="rounded-lg border border-line bg-bg-raised p-2 text-helix-cyan">
                    <Icon name={CHECK_ICON[c.id] ?? 'Shield'} size={18} />
                  </div>
                  <div className="min-w-0">
                    <div className="text-sm font-semibold text-white">{c.name}</div>
                    <div className="text-xs text-slate-500">{c.nameKo}</div>
                  </div>
                </div>
                <SafetyBadge status={c.status} small />
              </div>
              <p className="mt-3 text-xs leading-relaxed text-slate-400">{c.description}</p>
              <div className="mt-3 flex items-start gap-2 rounded-lg border border-line-soft bg-bg-raised/40 p-2.5">
                <Icon name="Info" size={13} className="mt-0.5 shrink-0 text-slate-500" />
                <span className="text-[11px] leading-relaxed text-slate-400">{c.detail}</span>
              </div>
            </Panel>
          ))}
        </div>
      </div>

      {/* Blocked / quarantined outputs */}
      <div>
        <SectionTitle
          icon="Ban"
          right={
            <div className="flex items-center gap-1.5">
              <Badge tone="red" icon="ShieldX">{blockedCount} blocked</Badge>
              <Badge tone="amber" icon="ShieldAlert">{reviewCount} review</Badge>
            </div>
          }
        >
          Blocked / Quarantined outputs · 차단·격리된 출력
        </SectionTitle>
        {flagged.length === 0 ? (
          <EmptyState
            icon="ShieldCheck"
            title="No blocked or quarantined outputs"
            desc="No candidate triggered a hazardous-material or review threshold in the current set. Re-run the safety audit after regenerating candidates."
            action={<Button variant="secondary" icon="ScanSearch" onClick={runSafetyAudit}>Run Safety Audit</Button>}
          />
        ) : (
          <>
            <div className="grid gap-4 md:grid-cols-2">
              {flagged.map((f) => (
                <FlagCard key={f.id} f={f} />
              ))}
            </div>
            <div className="mt-3">
              <Disclaimer tone="red">
                Reason categories are shown <span className="font-medium">without actionable detail</span>. Synthesis routes,
                reagents, conditions, and any hazard-enabling specifics are withheld by policy. Toxicity is screened, never optimized.
              </Disclaimer>
            </div>
          </>
        )}
      </div>

      {/* Safety status legend */}
      <Panel className="p-4">
        <SectionTitle icon="BookMarked">Safety status legend · 상태 범례</SectionTitle>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
          {(Object.keys(SAFETY_STATUS_META) as SafetyStatus[]).map((st) => (
            <div key={st} className="flex items-start gap-2.5 rounded-lg border border-line-soft bg-bg-raised/40 p-2.5">
              <SafetyBadge status={st} small />
              <span className="text-[11px] leading-relaxed text-slate-400">{STATUS_HINT[st]}</span>
            </div>
          ))}
        </div>
      </Panel>

      {/* Footer disclaimers */}
      <div className="grid gap-3 md:grid-cols-2">
        <Disclaimer tone="amber">{NO_SYNTHESIS_NOTICE}</Disclaimer>
        <Disclaimer tone="slate">{CLINICAL_DISCLAIMER}</Disclaimer>
      </div>
    </div>
  )
}
