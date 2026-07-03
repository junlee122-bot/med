import React from 'react'
import { Radar, RadarChart, PolarGrid, PolarAngleAxis, ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Cell } from 'recharts'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  SafetyBadge,
  SourceBadge,
  Drawer,
  KeyVal,
  Disclaimer,
  PageHeader,
  Tabs,
  SearchInput,
  ScoreBar,
  ConfidenceMeter,
  Th,
  useSort,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { RECOMMENDATION_LABEL, moleculeScoreBreakdown } from '@/lib/scoring'
import { NO_SYNTHESIS_NOTICE } from '@/lib/constants'
import type { MoleculeCandidate, SafetyStatus } from '@/types'

function RiskCell({ v }: { v: number }) {
  const tone = v > 0.6 ? 'text-helix-red' : v > 0.4 ? 'text-helix-amber' : 'text-brand-300'
  return <span className={`font-mono text-xs tabular-nums ${tone}`}>{v.toFixed(2)}</span>
}

function RecoBadge({ r }: { r: MoleculeCandidate['recommendation'] }) {
  const meta = RECOMMENDATION_LABEL[r]
  return <Badge tone={meta.tone}>{meta.label}</Badge>
}

export function MoleculeLab() {
  const molecules = useAppStore((s) => s.molecules)
  const runSafetyAudit = useAppStore((s) => s.runSafetyAudit)
  const [safetyFilter, setSafetyFilter] = React.useState<'all' | SafetyStatus | 'valid' | 'invalid'>('all')
  const [query, setQuery] = React.useState('')
  const [openId, setOpenId] = React.useState<string | null>(null)

  const filtered = molecules.filter((m) => {
    if (query && !m.label.toLowerCase().includes(query.toLowerCase())) return false
    if (safetyFilter === 'all') return true
    if (safetyFilter === 'valid') return m.validityStatus === 'valid'
    if (safetyFilter === 'invalid') return m.validityStatus === 'invalid'
    return m.safetyStatus === safetyFilter
  })
  const { sorted, key, dir, toggle } = useSort<MoleculeCandidate>(filtered, 'compositeScore', 'desc')
  const open = molecules.find((m) => m.id === openId) ?? null

  const counts = {
    all: molecules.length,
    valid: molecules.filter((m) => m.validityStatus === 'valid').length,
    invalid: molecules.filter((m) => m.validityStatus === 'invalid').length,
    PASS: molecules.filter((m) => m.safetyStatus === 'PASS').length,
    REVIEW_REQUIRED: molecules.filter((m) => m.safetyStatus === 'REVIEW_REQUIRED').length,
    BLOCKED: molecules.filter((m) => m.safetyStatus === 'BLOCKED').length,
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Molecule Optimization Lab"
        subtitle="Candidate leaderboard & multi-objective optimization loop. 생성/도입된 후보 분자와 다목적 최적화 결과 — 실행 가능한 합성 경로는 정책상 미표시."
        icon="Atom"
        actions={<Button variant="secondary" icon="ShieldCheck" onClick={runSafetyAudit}>Re-run Safety Audit</Button>}
      />

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          active={safetyFilter}
          onChange={(id) => setSafetyFilter(id as typeof safetyFilter)}
          tabs={[
            { id: 'all', label: 'All', icon: 'List', count: counts.all },
            { id: 'valid', label: 'Valid', icon: 'CircleCheck', count: counts.valid },
            { id: 'PASS', label: 'PASS', icon: 'ShieldCheck', count: counts.PASS },
            { id: 'REVIEW_REQUIRED', label: 'Review', icon: 'ShieldAlert', count: counts.REVIEW_REQUIRED },
            { id: 'BLOCKED', label: 'Blocked', icon: 'ShieldX', count: counts.BLOCKED },
            { id: 'invalid', label: 'Invalid', icon: 'XCircle', count: counts.invalid },
          ]}
        />
        <div className="w-full max-w-xs">
          <SearchInput value={query} onChange={setQuery} placeholder="Filter candidates…" />
        </div>
      </div>

      <Panel className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] border-collapse text-sm">
            <thead className="border-b border-line bg-bg-soft/50">
              <tr>
                <Th sortKey="label" active={key === 'label'} dir={dir} onSort={() => toggle('label')}>Candidate</Th>
                <Th>Source</Th>
                <Th>Valid</Th>
                <Th sortKey="bindingScore" active={key === 'bindingScore'} dir={dir} onSort={() => toggle('bindingScore')} align="right">Binding</Th>
                <Th sortKey="admetScore" active={key === 'admetScore'} dir={dir} onSort={() => toggle('admetScore')} align="right">ADMET</Th>
                <Th sortKey="qed" active={key === 'qed'} dir={dir} onSort={() => toggle('qed')} align="right">QED</Th>
                <Th align="right">hERG</Th>
                <Th align="right">DILI</Th>
                <Th>Safety</Th>
                <Th sortKey="compositeScore" active={key === 'compositeScore'} dir={dir} onSort={() => toggle('compositeScore')}>Composite</Th>
                <Th>Recommendation</Th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((m) => (
                <tr
                  key={m.id}
                  onClick={() => setOpenId(m.id)}
                  className="cursor-pointer border-b border-line-soft transition-colors hover:bg-bg-hover/40"
                >
                  <td className="px-3 py-2.5">
                    <div className="font-medium text-white">{m.label}</div>
                    <div className="font-mono text-[10px] text-slate-500">{m.smiles.slice(0, 22)}{m.smiles.length > 22 ? '…' : ''}</div>
                  </td>
                  <td className="px-3 py-2.5"><SourceBadge source={m.sourceType} /></td>
                  <td className="px-3 py-2.5">
                    {m.validityStatus === 'valid' ? (
                      <Icon name="CircleCheck" size={16} className="text-brand-400" />
                    ) : (
                      <span title={m.validityReason}><Icon name="XCircle" size={16} className="text-helix-red" /></span>
                    )}
                  </td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-slate-300">{m.bindingScore ? m.bindingScore.toFixed(1) : '—'}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-slate-300">{m.validityStatus === 'valid' ? `${(m.admetScore * 100).toFixed(0)}%` : '—'}</td>
                  <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-slate-300">{m.validityStatus === 'valid' ? m.qed.toFixed(2) : '—'}</td>
                  <td className="px-3 py-2.5 text-right">{m.validityStatus === 'valid' ? <RiskCell v={m.hERG} /> : '—'}</td>
                  <td className="px-3 py-2.5 text-right">{m.validityStatus === 'valid' ? <RiskCell v={m.DILI} /> : '—'}</td>
                  <td className="px-3 py-2.5"><SafetyBadge status={m.safetyStatus} small /></td>
                  <td className="px-3 py-2.5 w-28">{m.validityStatus === 'valid' ? <ScoreBar value={m.compositeScore} /> : <span className="text-xs text-slate-600">rejected</span>}</td>
                  <td className="px-3 py-2.5"><RecoBadge r={m.recommendation} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Disclaimer tone="amber">{NO_SYNTHESIS_NOTICE}</Disclaimer>

      <MoleculeDrawer molecule={open} onClose={() => setOpenId(null)} />
    </div>
  )
}

function MoleculeDrawer({ molecule, onClose }: { molecule: MoleculeCandidate | null; onClose: () => void }) {
  const [tab, setTab] = React.useState('properties')
  if (!molecule) return null
  const m = molecule
  const valid = m.validityStatus === 'valid'
  const radar = [
    { k: 'Binding', v: Math.round(m.bindingNormalized * 100) },
    { k: 'ADMET', v: Math.round(m.admetScore * 100) },
    { k: 'QED', v: Math.round(m.qed * 100) },
    { k: 'Novelty', v: Math.round(m.novelty * 100) },
    { k: 'Feasibility', v: m.synthesisFeasibility === 'High' ? 90 : m.synthesisFeasibility === 'Medium' ? 60 : 30 },
    { k: 'Certainty', v: Math.round((1 - m.uncertainty) * 100) },
  ]
  const admet = [
    { k: 'hERG', v: m.hERG }, { k: 'Ames', v: m.Ames }, { k: 'DILI', v: m.DILI }, { k: 'CYP', v: m.cyp },
    { k: 'BBB', v: m.bbb }, { k: 'Solubility', v: m.solubility }, { k: 'Clearance', v: m.clearance }, { k: 'Bioavail.', v: m.bioavailability },
  ]
  const breakdown = valid ? moleculeScoreBreakdown(m) : []

  return (
    <Drawer
      open={!!molecule}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          {m.label}
          <SafetyBadge status={m.safetyStatus} small />
        </span>
      }
      subtitle={<span className="font-mono">{m.smiles}</span>}
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge source={m.sourceType} />
          <Badge tone={valid ? 'green' : 'red'} icon={valid ? 'CircleCheck' : 'XCircle'}>
            {valid ? 'SMILES valid' : `Invalid: ${m.validityReason}`}
          </Badge>
          <Badge tone={RECOMMENDATION_LABEL[m.recommendation].tone}>{RECOMMENDATION_LABEL[m.recommendation].label}</Badge>
          <Badge tone="slate" icon="Beaker">Composite {valid ? m.compositeScore : '—'}/100</Badge>
        </div>

        {!valid && (
          <Disclaimer tone="red">
            This structure was rejected by the Cheminformatics Validator ({m.validityReason}) and looped back to the Molecular
            Design Agent for regeneration. It cannot enter ranking or the recommended package.
          </Disclaimer>
        )}

        <Tabs
          active={tab}
          onChange={setTab}
          tabs={[
            { id: 'properties', label: 'Properties', icon: 'Ruler' },
            { id: 'admet', label: 'ADMET', icon: 'Activity' },
            { id: 'scoring', label: 'Scoring', icon: 'Calculator' },
            { id: 'safety', label: 'Safety', icon: 'ShieldCheck' },
            { id: 'history', label: 'Optimization', icon: 'GitBranch' },
          ]}
        />

        {tab === 'properties' && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Panel className="p-3">
              <SectionTitle icon="Radar">Property Radar</SectionTitle>
              <ResponsiveContainer width="100%" height={200}>
                <RadarChart data={radar} outerRadius={78}>
                  <PolarGrid stroke="#1f2b48" />
                  <PolarAngleAxis dataKey="k" tick={{ fontSize: 10, fill: '#94a3b8' }} />
                  <Radar dataKey="v" stroke="#22d3ee" fill="#22d3ee" fillOpacity={0.3} />
                </RadarChart>
              </ResponsiveContainer>
            </Panel>
            <Panel className="p-3">
              <SectionTitle icon="Ruler">Descriptors (RDKit)</SectionTitle>
              <KeyVal k="Molecular weight" v={`${m.descriptors.mw} g/mol`} mono />
              <KeyVal k="logP" v={m.descriptors.logP} mono />
              <KeyVal k="H-bond donors" v={m.descriptors.hbd} mono />
              <KeyVal k="H-bond acceptors" v={m.descriptors.hba} mono />
              <KeyVal k="TPSA" v={`${m.descriptors.tpsa} Å²`} mono />
              <KeyVal k="Rotatable bonds" v={m.descriptors.rotatableBonds} mono />
              <KeyVal k="Lipinski" v={m.lipinskiPass ? 'Pass' : `${m.lipinskiViolations} violation(s)`} />
              <KeyVal k="QED" v={m.qed.toFixed(2)} mono />
              <KeyVal k="SA score" v={m.saScore} mono />
            </Panel>
            <Panel className="p-3 sm:col-span-2">
              <SectionTitle icon="Magnet">Binding & Structure (Demo Simulation)</SectionTitle>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg border border-line bg-bg-raised/50 p-2">
                  <div className="text-[10px] uppercase text-slate-500">Binding</div>
                  <div className="font-mono text-sm text-white">{m.bindingScore} kcal/mol</div>
                </div>
                <div className="rounded-lg border border-line bg-bg-raised/50 p-2">
                  <div className="text-[10px] uppercase text-slate-500">Pose conf.</div>
                  <div className="font-mono text-sm text-white">{(m.poseConfidence * 100).toFixed(0)}%</div>
                </div>
                <div className="rounded-lg border border-line bg-bg-raised/50 p-2">
                  <div className="text-[10px] uppercase text-slate-500">Novelty / IP</div>
                  <div className="font-mono text-sm text-white">{(m.novelty * 100).toFixed(0)}% / {(m.ipDistance * 100).toFixed(0)}%</div>
                </div>
              </div>
            </Panel>
          </div>
        )}

        {tab === 'admet' && (
          <Panel className="p-3">
            <SectionTitle icon="Activity" right={<Badge tone="cyan">Demo Simulation</Badge>}>ADMET & Toxicology</SectionTitle>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={admet} margin={{ top: 4, right: 8, bottom: 0, left: -20 }}>
                <XAxis dataKey="k" tick={{ fontSize: 10, fill: '#94a3b8' }} axisLine={false} tickLine={false} />
                <YAxis domain={[0, 1]} tick={{ fontSize: 10, fill: '#64748b' }} axisLine={false} tickLine={false} />
                <Bar dataKey="v" radius={[3, 3, 0, 0]}>
                  {admet.map((d, i) => (
                    <Cell key={i} fill={['hERG', 'Ames', 'DILI', 'CYP'].includes(d.k) ? (d.v > 0.6 ? '#ef4444' : d.v > 0.4 ? '#f59e0b' : '#16b884') : '#22d3ee'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
            <div className="mt-2 text-[11px] text-slate-500">
              Risk endpoints (hERG/Ames/DILI/CYP): lower is better. Uncertainty {m.uncertainty.toFixed(2)}. High-risk candidates are escalated to the Safety Auditor.
            </div>
          </Panel>
        )}

        {tab === 'scoring' && (
          <Panel className="p-3">
            <SectionTitle icon="Calculator">Composite Score Breakdown</SectionTitle>
            {valid ? (
              <div className="space-y-2">
                {breakdown.map((b) => (
                  <div key={b.key} className="flex items-center gap-2 text-xs">
                    <span className="w-36 text-slate-400">{b.key}</span>
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg-soft">
                      <div className="h-full rounded-full bg-helix-cyan" style={{ width: `${b.value * 100}%` }} />
                    </div>
                    <span className="w-24 text-right font-mono text-slate-400">
                      {(b.value * 100).toFixed(0)}% × {b.weight}
                    </span>
                  </div>
                ))}
                <div className="mt-2 flex items-center justify-between border-t border-line pt-2">
                  <span className="text-sm text-slate-300">Composite (after safety & uncertainty penalties)</span>
                  <span className="font-mono text-lg font-semibold text-brand-300">{m.compositeScore}/100</span>
                </div>
                <ConfidenceMeter value={1 - m.uncertainty} label="Confidence (1 − uncertainty)" reasons={['demo simulation', m.safetyStatus === 'REVIEW_REQUIRED' ? 'safety review' : '', m.dockingFailed ? 'docking failed' : ''].filter(Boolean)} />
              </div>
            ) : (
              <div className="text-xs text-slate-500">Not scored — invalid structure.</div>
            )}
          </Panel>
        )}

        {tab === 'safety' && (
          <div className="space-y-3">
            <Panel className="p-3">
              <SectionTitle icon="ShieldCheck">Safety Gate</SectionTitle>
              <KeyVal k="Status" v={<SafetyBadge status={m.safetyStatus} small />} />
              <KeyVal k="Requires expert review" v={m.requiresExpertReview ? 'Yes' : 'No'} />
              {m.safetyStatus === 'BLOCKED' && (
                <Disclaimer tone="red">
                  Quarantined by the Safety Auditor under hazardous-material policy. Recommendation forced to “Do not advance”.
                  Reason category is shown without actionable detail.
                </Disclaimer>
              )}
            </Panel>
            <Panel className="p-3">
              <SectionTitle icon="Wrench">Synthetic Feasibility Summary</SectionTitle>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="rounded-lg border border-line bg-bg-raised/50 p-2">
                  <div className="text-[10px] uppercase text-slate-500">Feasibility</div>
                  <div className="text-sm font-semibold text-white">{m.synthesisFeasibility}</div>
                </div>
                <div className="rounded-lg border border-line bg-bg-raised/50 p-2">
                  <div className="text-[10px] uppercase text-slate-500">Route conf.</div>
                  <div className="font-mono text-sm text-white">{(m.routeConfidence * 100).toFixed(0)}%</div>
                </div>
                <div className="rounded-lg border border-line bg-bg-raised/50 p-2">
                  <div className="text-[10px] uppercase text-slate-500">Complexity</div>
                  <div className="font-mono text-sm text-white">{(m.estimatedComplexity * 100).toFixed(0)}%</div>
                </div>
              </div>
              <Disclaimer tone="slate">{NO_SYNTHESIS_NOTICE}</Disclaimer>
            </Panel>
            {m.criticComments.length > 0 && (
              <Panel className="p-3">
                <SectionTitle icon="SearchCheck">Critic Comments</SectionTitle>
                <ul className="space-y-1.5">
                  {m.criticComments.map((c, i) => (
                    <li key={i} className="flex gap-2 text-xs text-slate-300">
                      <Icon name="ChevronRight" size={13} className="mt-0.5 shrink-0 text-helix-amber" />
                      {c}
                    </li>
                  ))}
                </ul>
              </Panel>
            )}
          </div>
        )}

        {tab === 'history' && (
          <Panel className="p-3">
            <SectionTitle icon="GitBranch">Optimization History</SectionTitle>
            {m.optimizationHistory.length === 0 ? (
              <div className="text-xs text-slate-500">No optimization iterations (invalid structure).</div>
            ) : (
              <div className="space-y-2">
                {m.optimizationHistory.map((h) => (
                  <div key={h.iteration} className="flex items-center gap-3 rounded-lg border border-line bg-bg-raised/40 p-2.5">
                    <div className="grid h-7 w-7 place-items-center rounded-full border border-line bg-bg-soft font-mono text-xs text-helix-cyan">
                      {h.iteration}
                    </div>
                    <div className="min-w-0 flex-1">
                      <div className="text-xs font-medium text-slate-200">{h.action}</div>
                      <div className="text-[11px] text-slate-500">{h.note}</div>
                    </div>
                    <div className="text-right font-mono text-xs">
                      <span className="text-slate-500">{h.compositeScoreBefore.toFixed(0)}</span>
                      <Icon name="ArrowRight" size={11} className="mx-1 inline text-slate-600" />
                      <span className="text-brand-300">{h.compositeScoreAfter.toFixed(0)}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>
        )}
      </div>
    </Drawer>
  )
}
