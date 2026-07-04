import React from 'react'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  SourceBadge,
  Drawer,
  KeyVal,
  Disclaimer,
  PageHeader,
  StatCard,
  ScoreBar,
  ConfidenceMeter,
  Th,
  useSort,
  EmptyState,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { DEFAULT_TARGET_WEIGHTS, targetScoreBreakdown } from '@/lib/scoring'
import type { EvidenceItem, TargetCandidate, TargetWeights } from '@/types'

// ---------------------------------------------------------------------------
// Static presentation helpers
// ---------------------------------------------------------------------------
const STATUS_TONE: Record<TargetCandidate['status'], { tone: string; label: string; icon: string }> = {
  selected: { tone: 'green', label: 'Selected', icon: 'CircleCheck' },
  ranked: { tone: 'cyan', label: 'Ranked', icon: 'ListOrdered' },
  exploratory: { tone: 'violet', label: 'Exploratory', icon: 'Compass' },
  deprioritized: { tone: 'slate', label: 'Deprioritized', icon: 'ArrowDown' },
}

const WEIGHT_FIELDS: { key: keyof TargetWeights; label: string; ko: string; penalty?: boolean }[] = [
  { key: 'diseaseRelevance', label: 'Disease relevance', ko: '질환 연관성' },
  { key: 'tractability', label: 'Tractability', ko: '약물 표적성' },
  { key: 'clinicalPrecedent', label: 'Clinical precedent', ko: '임상 선례' },
  { key: 'biomarkerAvailability', label: 'Biomarker availability', ko: '바이오마커' },
  { key: 'novelty', label: 'Novelty', ko: '신규성' },
  { key: 'evidenceConfidence', label: 'Evidence confidence', ko: '근거 신뢰도' },
  { key: 'safetyConcern', label: 'Safety concern', ko: '안전성 우려', penalty: true },
]

// Knowledge-graph context (Disease → Pathway → Target → Biomarker) per target.
const TARGET_GRAPH: Record<string, { pathway: string; biomarker: string }> = {
  EGFR: { pathway: 'RTK · MAPK / PI3K signaling', biomarker: 'EGFR alteration status · ctDNA' },
  MET: { pathway: 'MET bypass-resistance signaling', biomarker: 'MET amplification · exon14 skip' },
  KRAS: { pathway: 'RAS · MAPK signaling', biomarker: 'KRAS allele genotype' },
  ERBB2: { pathway: 'ERBB-family signaling node', biomarker: 'HER2 / ERBB2 exon status' },
  ALK: { pathway: 'ALK fusion signaling', biomarker: 'ALK rearrangement' },
}
function graphFor(symbol: string) {
  return TARGET_GRAPH[symbol] ?? { pathway: `${symbol} pathway`, biomarker: `${symbol} status` }
}

function PctBar({ v, invert }: { v: number; invert?: boolean }) {
  const pct = Math.round(v * 100)
  const tone = invert
    ? pct > 50
      ? 'bg-helix-red'
      : pct > 30
        ? 'bg-helix-amber'
        : 'bg-brand-500'
    : pct >= 70
      ? 'bg-brand-500'
      : pct >= 45
        ? 'bg-helix-amber'
        : 'bg-helix-red'
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-14 overflow-hidden rounded-full bg-bg-soft">
        <div className={`h-full rounded-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="w-8 text-right font-mono text-[11px] tabular-nums text-slate-300">{pct}%</span>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------
export function Targets() {
  const targets = useAppStore((s) => s.targets)
  const evidence = useAppStore((s) => s.evidence)
  const hypotheses = useAppStore((s) => s.hypotheses)
  const targetWeights = useAppStore((s) => s.targetWeights)
  const setTargetWeights = useAppStore((s) => s.setTargetWeights)
  const recomputeScores = useAppStore((s) => s.recomputeScores)
  const disease = useAppStore((s) => s.activeProject()?.disease ?? 'Disease')

  const [openId, setOpenId] = React.useState<string | null>(null)
  const [weightsOpen, setWeightsOpen] = React.useState(false)

  const { sorted, key, dir, toggle } = useSort<TargetCandidate>(targets, 'score', 'desc')
  const open = targets.find((t) => t.id === openId) ?? null

  const selectedCount = targets.filter((t) => t.status === 'selected').length
  const topTarget = targets.find((t) => t.rank === 1) ?? sorted[0]
  const posWeightSum =
    targetWeights.diseaseRelevance +
    targetWeights.tractability +
    targetWeights.clinicalPrecedent +
    targetWeights.biomarkerAvailability +
    targetWeights.novelty +
    targetWeights.evidenceConfidence
  const isDefault = WEIGHT_FIELDS.every((f) => Math.abs(targetWeights[f.key] - DEFAULT_TARGET_WEIGHTS[f.key]) < 1e-9)

  const setWeight = (field: keyof TargetWeights, value: number) =>
    setTargetWeights({ ...targetWeights, [field]: value })

  return (
    <div className="space-y-4">
      <PageHeader
        title="Target Prioritization Board · 표적 우선순위"
        subtitle="Evidence-grounded target ranking with a transparent, editable opportunity score. 근거 기반으로 표적을 순위화하고, 가중치를 직접 조정해 점수 산식을 투명하게 검증합니다."
        icon="Crosshair"
        actions={
          <>
            <Button variant="secondary" icon="SlidersHorizontal" onClick={() => setWeightsOpen((v) => !v)}>
              Scoring weights
            </Button>
            <Button variant="ghost" icon="RefreshCw" onClick={recomputeScores} title="Re-run the opportunity score with current weights">
              Recompute
            </Button>
          </>
        }
      />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Targets ranked" value={targets.length} sub={`${selectedCount} selected · ${targets.filter((t) => t.status === 'exploratory').length} exploratory`} icon="Crosshair" tone="cyan" />
        <StatCard label="Top opportunity" value={topTarget?.symbol ?? '—'} sub={`Score ${topTarget?.score ?? '—'}/100`} icon="Trophy" tone="green" />
        <StatCard label="Evidence linked" value={evidence.length} sub={`${evidence.filter((e) => e.evidenceDirection === 'contradicts').length} contradictory on record`} icon="BookOpen" tone="violet" />
        <StatCard label="Positive weight Σ" value={posWeightSum.toFixed(2)} sub={`Safety penalty −${targetWeights.safetyConcern.toFixed(2)}`} icon="Scale" tone="amber" />
      </div>

      {/* Scoring weights (collapsible) */}
      {weightsOpen && (
        <Panel className="p-5">
          <SectionTitle
            icon="SlidersHorizontal"
            right={
              <div className="flex items-center gap-2">
                <Badge tone={isDefault ? 'slate' : 'amber'} icon={isDefault ? 'Check' : 'Pencil'}>
                  {isDefault ? 'Default weights' : 'Custom weights'}
                </Badge>
                <Button
                  variant="ghost"
                  icon="RotateCcw"
                  onClick={() => setTargetWeights({ ...DEFAULT_TARGET_WEIGHTS })}
                  disabled={isDefault}
                >
                  Reset
                </Button>
              </div>
            }
          >
            Scoring weights · 가중치 조정 (live)
          </SectionTitle>

          <div className="grid gap-x-8 gap-y-4 md:grid-cols-2">
            {WEIGHT_FIELDS.map((f) => (
              <div key={f.key}>
                <div className="mb-1 flex items-center justify-between text-xs">
                  <span className="flex items-center gap-1.5 text-slate-300">
                    {f.penalty && <Icon name="TriangleAlert" size={12} className="text-helix-red" />}
                    {f.label} <span className="text-slate-500">· {f.ko}</span>
                    {f.penalty && <span className="text-[10px] text-helix-red">(subtracted)</span>}
                  </span>
                  <span className="font-mono tabular-nums text-slate-200">{targetWeights[f.key].toFixed(2)}</span>
                </div>
                <input
                  type="range"
                  min={0}
                  max={0.5}
                  step={0.01}
                  value={targetWeights[f.key]}
                  onChange={(e) => setWeight(f.key, Number(e.target.value))}
                  className={`w-full ${f.penalty ? 'accent-helix-red' : 'accent-brand-500'}`}
                  aria-label={`${f.label} weight`}
                />
              </div>
            ))}
          </div>

          <div className="mt-5 rounded-lg border border-line bg-bg-raised/50 p-3">
            <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
              <Icon name="Sigma" size={13} className="text-helix-cyan" /> Opportunity score formula
            </div>
            <code className="block whitespace-pre-wrap font-mono text-[11px] leading-relaxed text-slate-300">
              score = ( wDR·DR + wTR·Tract + wCP·Clin + wBM·Bio + wNOV·Novelty + wEV·Evidence − wSAFE·Safety )
              {'\n'}          ÷ Σ(positive weights = {posWeightSum.toFixed(2)}) × 100 → clamped to 0–100
            </code>
          </div>

          {topTarget && (
            <div className="mt-4">
              <div className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                Worked example · {topTarget.symbol} (rank #{topTarget.rank})
              </div>
              <ScoreBreakdown t={topTarget} weights={targetWeights} posSum={posWeightSum} />
            </div>
          )}
        </Panel>
      )}

      {/* Rank table */}
      <Panel className="overflow-hidden">
        {targets.length === 0 ? (
          <div className="p-6">
            <EmptyState icon="Crosshair" title="No ranked targets" desc="Run the workflow to mine evidence and prioritize disease targets." />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1080px] border-collapse text-sm">
              <thead className="border-b border-line bg-bg-soft/50">
                <tr>
                  <Th sortKey="rank" active={key === 'rank'} dir={dir} onSort={() => toggle('rank')}>#</Th>
                  <Th sortKey="symbol" active={key === 'symbol'} dir={dir} onSort={() => toggle('symbol')}>Target</Th>
                  <Th sortKey="diseaseRelevance" active={key === 'diseaseRelevance'} dir={dir} onSort={() => toggle('diseaseRelevance')}>Disease rel.</Th>
                  <Th sortKey="tractability" active={key === 'tractability'} dir={dir} onSort={() => toggle('tractability')}>Tractability</Th>
                  <Th sortKey="novelty" active={key === 'novelty'} dir={dir} onSort={() => toggle('novelty')}>Novelty</Th>
                  <Th sortKey="safetyConcern" active={key === 'safetyConcern'} dir={dir} onSort={() => toggle('safetyConcern')}>Safety concern</Th>
                  <Th sortKey="biomarkerAvailability" active={key === 'biomarkerAvailability'} dir={dir} onSort={() => toggle('biomarkerAvailability')}>Biomarker</Th>
                  <Th sortKey="clinicalPrecedent" active={key === 'clinicalPrecedent'} dir={dir} onSort={() => toggle('clinicalPrecedent')}>Clin. precedent</Th>
                  <Th sortKey="evidenceCount" active={key === 'evidenceCount'} dir={dir} onSort={() => toggle('evidenceCount')} align="right">Evidence</Th>
                  <Th sortKey="confidence" active={key === 'confidence'} dir={dir} onSort={() => toggle('confidence')} align="right">Conf.</Th>
                  <Th sortKey="score" active={key === 'score'} dir={dir} onSort={() => toggle('score')} className="w-32">Score</Th>
                  <Th>Status</Th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((t) => {
                  const st = STATUS_TONE[t.status]
                  return (
                    <tr
                      key={t.id}
                      onClick={() => setOpenId(t.id)}
                      className="cursor-pointer border-b border-line-soft transition-colors hover:bg-bg-hover/40"
                    >
                      <td className="px-3 py-2.5">
                        <span className="grid h-6 w-6 place-items-center rounded-full border border-line bg-bg-soft font-mono text-[11px] font-semibold tabular-nums text-helix-cyan">
                          {t.rank}
                        </span>
                      </td>
                      <td className="px-3 py-2.5">
                        <div className="font-semibold text-white">{t.symbol}</div>
                        <div className="text-[11px] text-slate-500">{t.name}</div>
                      </td>
                      <td className="px-3 py-2.5"><PctBar v={t.diseaseRelevance} /></td>
                      <td className="px-3 py-2.5"><PctBar v={t.tractability} /></td>
                      <td className="px-3 py-2.5"><PctBar v={t.novelty} /></td>
                      <td className="px-3 py-2.5"><PctBar v={t.safetyConcern} invert /></td>
                      <td className="px-3 py-2.5"><PctBar v={t.biomarkerAvailability} /></td>
                      <td className="px-3 py-2.5"><PctBar v={t.clinicalPrecedent} /></td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-slate-300">{t.evidenceCount}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums text-slate-300">{(t.confidence * 100).toFixed(0)}%</td>
                      <td className="px-3 py-2.5"><ScoreBar value={t.score} /></td>
                      <td className="px-3 py-2.5"><Badge tone={st.tone} icon={st.icon}>{st.label}</Badge></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <div className="flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
        <SourceBadge source="demo" />
        <span>
          Ranking is decision-support only, computed from a transparent weighted score over demo-labeled evidence — not a
          determination of clinical validity. Safety concern is subtracted; higher = worse.
        </span>
      </div>

      <TargetDrawer
        target={open}
        evidence={evidence}
        hypotheses={hypotheses}
        weights={targetWeights}
        posSum={posWeightSum}
        disease={disease}
        onClose={() => setOpenId(null)}
      />
    </div>
  )
}

// ---------------------------------------------------------------------------
// Score breakdown (shared by weights panel + drawer)
// ---------------------------------------------------------------------------
function ScoreBreakdown({ t, weights, posSum }: { t: TargetCandidate; weights: TargetWeights; posSum: number }) {
  const rows = targetScoreBreakdown(t, weights)
  return (
    <div className="space-y-1.5">
      {rows.map((b) => {
        const contribution = b.sign * b.weight * b.value
        return (
          <div key={b.key} className="flex items-center gap-2 text-xs">
            <span className="w-40 shrink-0 text-slate-400">{b.key}</span>
            <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-bg-soft">
              <div
                className={`h-full rounded-full ${b.sign < 0 ? 'bg-helix-red' : 'bg-helix-cyan'}`}
                style={{ width: `${Math.min(100, b.value * 100)}%` }}
              />
            </div>
            <span className="w-24 shrink-0 text-right font-mono tabular-nums text-slate-500">
              {(b.value * 100).toFixed(0)}% × {b.weight.toFixed(2)}
            </span>
            <span className={`w-14 shrink-0 text-right font-mono tabular-nums ${b.sign < 0 ? 'text-helix-red' : 'text-brand-300'}`}>
              {b.sign < 0 ? '−' : '+'}
              {(Math.abs(contribution) * 100).toFixed(1)}
            </span>
          </div>
        )
      })}
      <div className="mt-2 flex items-center justify-between border-t border-line pt-2">
        <span className="text-xs text-slate-400">÷ Σ positive weights ({posSum.toFixed(2)}) × 100 → opportunity score</span>
        <span className="font-mono text-lg font-semibold text-brand-300">{t.score}/100</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Evidence card
// ---------------------------------------------------------------------------
function EvidenceCard({ e }: { e: EvidenceItem }) {
  const dirTone = e.evidenceDirection === 'supports' ? 'green' : e.evidenceDirection === 'contradicts' ? 'red' : 'slate'
  const dirIcon = e.evidenceDirection === 'supports' ? 'ThumbsUp' : e.evidenceDirection === 'contradicts' ? 'ThumbsDown' : 'Minus'
  return (
    <div className="rounded-lg border border-line bg-bg-raised/40 p-3">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-xs font-medium text-slate-200">{e.title}</div>
          <div className="mt-0.5 text-[11px] text-slate-500">
            {e.authors} · {e.year} · <span className="font-mono">{e.identifierType}:{e.identifier}</span>
          </div>
        </div>
        <Badge tone={dirTone} icon={dirIcon} className="shrink-0 text-[10px]">{e.evidenceDirection}</Badge>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-slate-400">“{e.claim}”</p>
      <div className="mt-2 flex items-center gap-2">
        <SourceBadge source={e.sourceType} />
        <span className="font-mono text-[10px] tabular-nums text-slate-500">conf {(e.confidence * 100).toFixed(0)}%</span>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Drawer
// ---------------------------------------------------------------------------
function TargetDrawer({
  target,
  evidence,
  hypotheses,
  weights,
  posSum,
  disease,
  onClose,
}: {
  target: TargetCandidate | null
  evidence: EvidenceItem[]
  hypotheses: ReturnType<typeof useAppStore.getState>['hypotheses']
  weights: TargetWeights
  posSum: number
  disease: string
  onClose: () => void
}) {
  if (!target) return null
  const t = target
  const st = STATUS_TONE[t.status]
  const g = graphFor(t.symbol)

  const related = evidence.filter((e) => t.evidenceIds.includes(e.id) || e.relatedTarget === t.symbol)
  const supporting = related.filter((e) => e.evidenceDirection === 'supports')
  const contradictory = related.filter((e) => e.evidenceDirection === 'contradicts')
  const neutral = related.filter((e) => e.evidenceDirection === 'neutral')
  const linkedHyp = hypotheses.filter((h) => h.targetSymbol === t.symbol || h.targetId === t.id)

  const chips = [
    { label: disease, icon: 'Microscope', tone: 'blue' },
    { label: g.pathway, icon: 'Waypoints', tone: 'violet' },
    { label: t.symbol, icon: 'Crosshair', tone: 'cyan' },
    { label: g.biomarker, icon: 'Dna', tone: 'green' },
  ]

  return (
    <Drawer
      open={!!target}
      onClose={onClose}
      title={
        <span className="flex items-center gap-2">
          {t.symbol}
          <Badge tone={st.tone} icon={st.icon}>{st.label}</Badge>
          <Badge tone="slate" icon="Target">#{t.rank}</Badge>
        </span>
      }
      subtitle={t.name}
    >
      <div className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <SourceBadge source="demo" />
          <Badge tone="cyan" icon="Gauge">Opportunity {t.score}/100</Badge>
          <Badge tone="slate" icon="BookOpen">{t.evidenceCount} evidence</Badge>
        </div>

        {/* Knowledge graph path */}
        <Panel className="p-3">
          <SectionTitle icon="Waypoints">Knowledge graph path · 지식 그래프 경로</SectionTitle>
          <div className="flex flex-wrap items-center gap-1.5">
            {chips.map((c, i) => (
              <React.Fragment key={c.label}>
                <Badge tone={c.tone} icon={c.icon}>{c.label}</Badge>
                {i < chips.length - 1 && <Icon name="ArrowRight" size={13} className="text-slate-600" />}
              </React.Fragment>
            ))}
          </div>
        </Panel>

        {/* Rationale */}
        <Panel className="p-3">
          <SectionTitle icon="FileText">Prioritization rationale · 우선순위 근거</SectionTitle>
          <p className="text-xs leading-relaxed text-slate-300">{t.rationale}</p>
          <div className="mt-3">
            <ConfidenceMeter value={t.confidence} label="Target confidence" reasons={['demo-labeled evidence', contradictory.length > 0 ? 'contradictory subgroup evidence' : ''].filter(Boolean)} />
          </div>
        </Panel>

        {/* Score composition */}
        <Panel className="p-3">
          <SectionTitle icon="Calculator" right={<Badge tone="slate">Editable weights</Badge>}>Score composition</SectionTitle>
          <ScoreBreakdown t={t} weights={weights} posSum={posSum} />
        </Panel>

        {/* Supporting evidence */}
        <Panel className="p-3">
          <SectionTitle icon="ThumbsUp" right={<Badge tone="green">{supporting.length}</Badge>}>Supporting evidence</SectionTitle>
          {supporting.length === 0 ? (
            <div className="text-xs text-slate-500">No supporting evidence linked to this target.</div>
          ) : (
            <div className="space-y-2">
              {supporting.map((e) => (
                <EvidenceCard key={e.id} e={e} />
              ))}
            </div>
          )}
        </Panel>

        {/* Contradictory evidence */}
        <Panel className="p-3">
          <SectionTitle icon="ThumbsDown" right={<Badge tone={contradictory.length ? 'red' : 'slate'}>{contradictory.length}</Badge>}>Contradictory evidence</SectionTitle>
          {contradictory.length === 0 ? (
            <div className="text-xs text-slate-500">No contradictory evidence on record for this target.</div>
          ) : (
            <div className="space-y-2">
              {contradictory.map((e) => (
                <EvidenceCard key={e.id} e={e} />
              ))}
            </div>
          )}
          {neutral.length > 0 && (
            <div className="mt-2 text-[11px] text-slate-500">+ {neutral.length} neutral / contextual record(s) linked.</div>
          )}
        </Panel>

        {/* Linked hypotheses */}
        {linkedHyp.length > 0 && (
          <Panel className="p-3">
            <SectionTitle icon="Lightbulb">Linked hypotheses</SectionTitle>
            <div className="space-y-2">
              {linkedHyp.map((h) => (
                <div key={h.id} className="rounded-lg border border-line bg-bg-raised/40 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-xs leading-relaxed text-slate-300">{h.statement}</p>
                    <Badge tone={h.status === 'verified' ? 'green' : h.status === 'rejected' ? 'red' : 'slate'} className="shrink-0 text-[10px]">{h.status}</Badge>
                  </div>
                  <div className="mt-1.5 font-mono text-[10px] tabular-nums text-slate-500">testability {(h.testability * 100).toFixed(0)}% · confidence {(h.confidence * 100).toFixed(0)}%</div>
                </div>
              ))}
            </div>
          </Panel>
        )}

        {/* Molecule strategy */}
        <Panel className="p-3">
          <SectionTitle icon="Atom">Suggested molecule strategy</SectionTitle>
          <p className="text-xs leading-relaxed text-slate-300">{t.moleculeStrategy}</p>
        </Panel>

        {/* Next actions */}
        <Panel className="p-3">
          <SectionTitle icon="ListChecks">Next actions · 다음 단계</SectionTitle>
          {t.nextActions.length === 0 ? (
            <div className="text-xs text-slate-500">No next actions defined.</div>
          ) : (
            <ul className="space-y-1.5">
              {t.nextActions.map((a, i) => (
                <li key={i} className="flex gap-2 text-xs text-slate-300">
                  <Icon name="ChevronRight" size={13} className="mt-0.5 shrink-0 text-helix-cyan" />
                  {a}
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Disclaimer tone="slate">
          Target prioritization is an evidence-grounded, human-in-the-loop planning aid. Scores are recomputed live from
          editable weights and do not assert clinical validity; all downstream steps require expert review.
        </Disclaimer>
      </div>
    </Drawer>
  )
}
