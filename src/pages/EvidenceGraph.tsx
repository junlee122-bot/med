import React from 'react'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  StatCard,
  ConfidenceMeter,
  Toggle,
  Tabs,
  SearchInput,
  EmptyState,
  Disclaimer,
  PageHeader,
  SourceBadge,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import type { EvidenceItem, EvidenceDirection, VerificationStatus, TargetCandidate } from '@/types'

// ============================================================================
// Direction / verification presentation maps
// ============================================================================
const DIRECTION_META: Record<EvidenceDirection, { tone: string; label: string; icon: string; color: string }> = {
  supports: { tone: 'green', label: 'Supports', icon: 'TrendingUp', color: '#16b884' },
  contradicts: { tone: 'red', label: 'Contradicts', icon: 'TrendingDown', color: '#ef4444' },
  neutral: { tone: 'slate', label: 'Neutral', icon: 'Minus', color: '#64748b' },
}

const VERIFY_META: Record<VerificationStatus, { tone: string; label: string; icon: string }> = {
  verified: { tone: 'green', label: 'Verified', icon: 'BadgeCheck' },
  demo: { tone: 'cyan', label: 'Demo record', icon: 'FlaskConical' },
  failed: { tone: 'red', label: 'Rejected', icon: 'XCircle' },
  unverified: { tone: 'slate', label: 'Unverified', icon: 'CircleHelp' },
}

const STRUCTURAL_COLOR = '#38bdf8'

// SVG layout constants (fixed coordinate space, scaled responsively)
const VW = 880
const DISEASE = { x: 24, w: 132, h: 64 }
const TARGET = { cx: 430, w: 104, h: 34 }
const EVIDENCE = { x: 690, w: 168, h: 42 }
const DISEASE_RIGHT = DISEASE.x + DISEASE.w // 156
const TARGET_LEFT = TARGET.cx - TARGET.w / 2 // 378
const TARGET_RIGHT = TARGET.cx + TARGET.w / 2 // 482
const EV_DOT_X = EVIDENCE.x + 10 // 700

function truncate(s: string, n: number) {
  return s.length > n ? s.slice(0, n - 1) + '…' : s
}

function twoLine(str: string, maxLen: number): string[] {
  const words = str.split(/\s+/)
  const lines = ['', '']
  let li = 0
  for (const w of words) {
    if (li > 1) break
    const test = lines[li] ? `${lines[li]} ${w}` : w
    if (test.length <= maxLen) lines[li] = test
    else if (li < 1) {
      li++
      lines[li] = w
    } else {
      lines[1] = truncate(`${lines[1]} ${w}`, maxLen)
      break
    }
  }
  return lines.filter(Boolean)
}

function edgePath(x1: number, y1: number, x2: number, y2: number) {
  const mx = (x1 + x2) / 2
  return `M ${x1} ${y1} C ${mx} ${y1}, ${mx} ${y2}, ${x2} ${y2}`
}

export function EvidenceGraph() {
  const evidence = useAppStore((s) => s.evidence)
  const targets = useAppStore((s) => s.targets)
  const projects = useAppStore((s) => s.projects)
  const activeProjectId = useAppStore((s) => s.activeProjectId)

  const [direction, setDirection] = React.useState<'all' | 'supports' | 'contradicts'>('all')
  const [verify, setVerify] = React.useState<'all' | VerificationStatus>('all')
  const [verifiedOnly, setVerifiedOnly] = React.useState(false)
  const [query, setQuery] = React.useState('')
  const [hoverId, setHoverId] = React.useState<string | null>(null)
  const [selectedId, setSelectedId] = React.useState<string | null>(null)

  const diseaseProject =
    projects.find((p) => p.id === evidence[0]?.projectId) ??
    projects.find((p) => p.id === activeProjectId) ??
    projects[0]
  const disease = diseaseProject?.disease ?? 'Disease'

  const counts = {
    total: evidence.length,
    supports: evidence.filter((e) => e.evidenceDirection === 'supports').length,
    contradicts: evidence.filter((e) => e.evidenceDirection === 'contradicts').length,
    neutral: evidence.filter((e) => e.evidenceDirection === 'neutral').length,
    failed: evidence.filter((e) => e.verificationStatus === 'failed').length,
    verified: evidence.filter((e) => e.verificationStatus === 'verified').length,
    demo: evidence.filter((e) => e.verificationStatus === 'demo').length,
    unverified: evidence.filter((e) => e.verificationStatus === 'unverified').length,
  }

  const filtered = evidence.filter((e) => {
    if (verifiedOnly && e.verificationStatus !== 'verified') return false
    if (direction !== 'all' && e.evidenceDirection !== direction) return false
    if (verify !== 'all' && e.verificationStatus !== verify) return false
    if (query) {
      const q = query.toLowerCase()
      const hay = `${e.title} ${e.claim} ${e.sourceName} ${e.identifier} ${e.authors} ${e.relatedTarget ?? ''}`.toLowerCase()
      if (!hay.includes(q)) return false
    }
    return true
  })

  const filtersActive = direction !== 'all' || verify !== 'all' || verifiedOnly || query.length > 0
  const resetFilters = () => {
    setDirection('all')
    setVerify('all')
    setVerifiedOnly(false)
    setQuery('')
  }

  const focusCard = (id: string) => {
    setSelectedId(id)
    const el = typeof document !== 'undefined' ? document.getElementById(`ev-card-${id}`) : null
    el?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Evidence Graph"
        subtitle="질병 → 타깃 → 근거 관계를 시각화하고, 인용을 검증합니다. Disease–target association and evidence provenance, with contradictory records retained and fabricated citations demoted by the Citation Verifier."
        icon="Waypoints"
        actions={<Badge tone="violet" icon="BookOpen">{evidence.length} evidence sources</Badge>}
      />

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Evidence items" value={counts.total} sub="Across mining sources" icon="BookOpen" tone="violet" />
        <StatCard label="Supporting" value={counts.supports} sub="Direction · supports" icon="TrendingUp" tone="green" />
        <StatCard label="Contradictory" value={counts.contradicts} sub="Retained, not hidden" icon="TrendingDown" tone="amber" />
        <StatCard label="Rejected citations" value={counts.failed} sub="Failed verifier check" icon="ShieldX" tone="red" />
      </div>

      {/* ---- (A) Network overview ---- */}
      <Panel className="p-5">
        <SectionTitle
          icon="Share2"
          right={
            <div className="hidden items-center gap-3 text-[11px] text-slate-400 sm:flex">
              <LegendEdge color={DIRECTION_META.supports.color} label="Supports" />
              <LegendEdge color={DIRECTION_META.contradicts.color} label="Contradicts" />
              <LegendEdge color={DIRECTION_META.neutral.color} label="Neutral" />
              <LegendEdge color={STRUCTURAL_COLOR} label="Disease→Target" />
            </div>
          }
        >
          Disease–Target–Evidence network · 근거 네트워크
        </SectionTitle>

        {evidence.length === 0 ? (
          <EmptyState icon="Waypoints" title="No evidence to graph" desc="Run the workflow to mine evidence and build the disease–target–evidence network." />
        ) : (
          <>
            <div className="overflow-x-auto">
              <NetworkSvg
                disease={disease}
                targets={targets}
                evidence={evidence}
                hoverId={hoverId}
                selectedId={selectedId}
                onHover={setHoverId}
                onPick={focusCard}
              />
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[11px] text-slate-400">
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-3 w-3 rounded-sm border border-blue-400/70 bg-blue-500/20" /> Disease
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-3 w-3 rounded-sm border border-helix-cyan/70 bg-helix-cyan/15" /> Target
              </span>
              <span className="flex items-center gap-1.5">
                <span className="inline-block h-3 w-3 rounded-full border border-slate-400/70 bg-slate-500/20" /> Evidence
              </span>
              <span className="flex items-center gap-1.5 text-red-300">
                <svg width="22" height="8">
                  <line x1="1" y1="4" x2="21" y2="4" stroke="#ef4444" strokeWidth="2" strokeDasharray="3 3" />
                </svg>
                Rejected citation (dashed)
              </span>
              <span className="text-slate-500">Hover a node to trace links · click an evidence node to jump to its card.</span>
            </div>
          </>
        )}
      </Panel>

      <Disclaimer tone="slate">
        Every record is labeled by provenance via a source badge. Contradictory evidence is retained deliberately so
        uncertainty is represented, not hidden. Fabricated or unverifiable citations are demoted to{' '}
        <span className="text-red-300">Rejected</span> by the Citation Verifier and excluded from downstream reasoning.
      </Disclaimer>

      {/* ---- (B) Filters + evidence cards ---- */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          active={direction}
          onChange={(id) => setDirection(id as typeof direction)}
          tabs={[
            { id: 'all', label: 'All directions', icon: 'List', count: counts.total },
            { id: 'supports', label: 'Supports', icon: 'TrendingUp', count: counts.supports },
            { id: 'contradicts', label: 'Contradicts', icon: 'TrendingDown', count: counts.contradicts },
          ]}
        />
        <div className="w-full max-w-xs">
          <SearchInput value={query} onChange={setQuery} placeholder="Search claim, source, identifier…" />
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs
          active={verify}
          onChange={(id) => setVerify(id as typeof verify)}
          tabs={[
            { id: 'all', label: 'Any verification', icon: 'ShieldQuestion', count: counts.total },
            { id: 'verified', label: 'Verified', icon: 'BadgeCheck', count: counts.verified },
            { id: 'demo', label: 'Demo', icon: 'FlaskConical', count: counts.demo },
            { id: 'failed', label: 'Rejected', icon: 'XCircle', count: counts.failed },
            { id: 'unverified', label: 'Unverified', icon: 'CircleHelp', count: counts.unverified },
          ]}
        />
        <div className="rounded-lg border border-line bg-bg-soft/60 px-3 py-1.5">
          <Toggle checked={verifiedOnly} onChange={setVerifiedOnly} label="Verified only" />
        </div>
      </div>

      {filtered.length === 0 ? (
        <EmptyState
          icon="SearchX"
          title="No evidence matches these filters"
          desc="No records satisfy the current direction / verification / search criteria. Verified-only can be empty in the demo dataset, where records are labeled as Demo Simulation rather than externally verified."
          action={filtersActive ? <Button variant="secondary" icon="RotateCcw" onClick={resetFilters}>Reset filters</Button> : undefined}
        />
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {filtered.map((e) => (
            <EvidenceCard key={e.id} e={e} selected={selectedId === e.id} onSelect={() => setSelectedId(e.id)} />
          ))}
        </div>
      )}
    </div>
  )
}

// ============================================================================
// Legend helper
// ============================================================================
function LegendEdge({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <svg width="20" height="8">
        <line x1="1" y1="4" x2="19" y2="4" stroke={color} strokeWidth="2.5" strokeLinecap="round" />
      </svg>
      {label}
    </span>
  )
}

// ============================================================================
// SVG network
// ============================================================================
function NetworkSvg({
  disease,
  targets,
  evidence,
  hoverId,
  selectedId,
  onHover,
  onPick,
}: {
  disease: string
  targets: TargetCandidate[]
  evidence: EvidenceItem[]
  hoverId: string | null
  selectedId: string | null
  onHover: (id: string | null) => void
  onPick: (id: string) => void
}) {
  const H = Math.max(targets.length, evidence.length, 3) * 54 + 40
  const top = 44
  const bottom = H - 32
  const dY = H / 2

  const spread = (n: number) =>
    n <= 1 ? [(top + bottom) / 2] : Array.from({ length: n }, (_, i) => top + (i * (bottom - top)) / (n - 1))

  const tYs = spread(targets.length)
  const eYs = spread(evidence.length)
  const targetPos = new Map(targets.map((t, i) => [t.id, tYs[i]]))
  const evPos = new Map(evidence.map((e, i) => [e.id, eYs[i]]))

  // Resolve which node each evidence attaches to.
  const anchorFor = (e: EvidenceItem) => {
    const t = targets.find((tg) => tg.symbol === e.relatedTarget)
    if (t) return { id: t.id, x: TARGET_RIGHT, y: targetPos.get(t.id)! }
    return { id: 'disease', x: DISEASE_RIGHT, y: dY }
  }

  // Adjacency for hover highlighting.
  const neighbors = React.useMemo(() => {
    const m = new Map<string, Set<string>>()
    const link = (a: string, b: string) => {
      if (!m.has(a)) m.set(a, new Set())
      if (!m.has(b)) m.set(b, new Set())
      m.get(a)!.add(b)
      m.get(b)!.add(a)
    }
    targets.forEach((t) => link('disease', t.id))
    evidence.forEach((e) => link(anchorFor(e).id, e.id))
    return m
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [targets, evidence])

  const isLit = (id: string) => !hoverId || id === hoverId || (neighbors.get(hoverId)?.has(id) ?? false)
  const edgeLit = (a: string, b: string) => !hoverId || hoverId === a || hoverId === b

  return (
    <svg viewBox={`0 0 ${VW} ${H}`} width="100%" style={{ minWidth: 820 }} role="img" aria-label="Evidence network">
      {/* Structural edges: disease -> target */}
      {targets.map((t) => {
        const ty = targetPos.get(t.id)!
        const lit = edgeLit('disease', t.id)
        return (
          <path
            key={`edge-d-${t.id}`}
            d={edgePath(DISEASE_RIGHT, dY, TARGET_LEFT, ty)}
            fill="none"
            stroke={STRUCTURAL_COLOR}
            strokeWidth={lit ? 1.6 : 1}
            strokeOpacity={lit ? 0.55 : 0.1}
          />
        )
      })}

      {/* Evidence edges: target -> evidence */}
      {evidence.map((e) => {
        const a = anchorFor(e)
        const ey = evPos.get(e.id)!
        const meta = DIRECTION_META[e.evidenceDirection]
        const failed = e.verificationStatus === 'failed'
        const color = failed ? '#ef4444' : meta.color
        const lit = edgeLit(a.id, e.id)
        return (
          <path
            key={`edge-e-${e.id}`}
            d={edgePath(a.x, a.y, EV_DOT_X, ey)}
            fill="none"
            stroke={color}
            strokeWidth={lit ? 2 : 1.2}
            strokeOpacity={lit ? (failed ? 0.85 : 0.7) : 0.1}
            strokeDasharray={failed ? '5 4' : undefined}
          />
        )
      })}

      {/* Disease node */}
      <g
        onMouseEnter={() => onHover('disease')}
        onMouseLeave={() => onHover(null)}
        opacity={isLit('disease') ? 1 : 0.28}
        style={{ transition: 'opacity 120ms' }}
      >
        <rect
          x={DISEASE.x}
          y={dY - DISEASE.h / 2}
          width={DISEASE.w}
          height={DISEASE.h}
          rx={10}
          fill="rgba(59,130,246,0.14)"
          stroke="#3b82f6"
          strokeWidth={1.5}
        />
        <text x={DISEASE.x + DISEASE.w / 2} y={dY - DISEASE.h / 2 + 15} textAnchor="middle" fontSize={8} fill="#93c5fd" style={{ letterSpacing: '0.08em' }}>
          DISEASE
        </text>
        {twoLine(disease, 18).map((ln, i, arr) => (
          <text
            key={i}
            x={DISEASE.x + DISEASE.w / 2}
            y={dY + 2 + (i - (arr.length - 1) / 2) * 12}
            textAnchor="middle"
            fontSize={11}
            fontWeight={600}
            fill="#e2e8f0"
          >
            {ln}
          </text>
        ))}
        <title>{disease}</title>
      </g>

      {/* Target nodes */}
      {targets.map((t) => {
        const ty = targetPos.get(t.id)!
        const lit = isLit(t.id)
        return (
          <g
            key={`node-t-${t.id}`}
            onMouseEnter={() => onHover(t.id)}
            onMouseLeave={() => onHover(null)}
            opacity={lit ? 1 : 0.24}
            style={{ transition: 'opacity 120ms' }}
          >
            <rect
              x={TARGET.cx - TARGET.w / 2}
              y={ty - TARGET.h / 2}
              width={TARGET.w}
              height={TARGET.h}
              rx={8}
              fill="rgba(34,211,238,0.12)"
              stroke="#22d3ee"
              strokeWidth={1.4}
            />
            <text x={TARGET.cx} y={ty - 1} textAnchor="middle" fontSize={12} fontWeight={700} fill="#e6fbff">
              {t.symbol}
            </text>
            <text x={TARGET.cx} y={ty + 11} textAnchor="middle" fontSize={8} fill="#67e8f9">
              score {Math.round(t.score)} · #{t.rank}
            </text>
            <title>{`${t.symbol} — ${t.name}`}</title>
          </g>
        )
      })}

      {/* Evidence nodes */}
      {evidence.map((e) => {
        const ey = evPos.get(e.id)!
        const meta = DIRECTION_META[e.evidenceDirection]
        const failed = e.verificationStatus === 'failed'
        const dotColor = failed ? '#ef4444' : meta.color
        const lit = isLit(e.id)
        const isSel = selectedId === e.id
        return (
          <g
            key={`node-e-${e.id}`}
            onMouseEnter={() => onHover(e.id)}
            onMouseLeave={() => onHover(null)}
            onClick={() => onPick(e.id)}
            opacity={lit ? 1 : 0.24}
            style={{ transition: 'opacity 120ms', cursor: 'pointer' }}
          >
            <rect
              x={EVIDENCE.x}
              y={ey - EVIDENCE.h / 2}
              width={EVIDENCE.w}
              height={EVIDENCE.h}
              rx={8}
              fill={isSel ? 'rgba(34,211,238,0.12)' : 'rgba(148,163,184,0.08)'}
              stroke={isSel ? '#22d3ee' : failed ? '#ef4444' : 'rgba(148,163,184,0.55)'}
              strokeWidth={isSel ? 1.8 : 1.2}
              strokeDasharray={failed ? '5 4' : undefined}
            />
            <circle cx={EV_DOT_X} cy={ey} r={4} fill={dotColor} />
            <text x={EVIDENCE.x + 24} y={ey - 3} fontSize={9.5} fontWeight={600} fill="#e2e8f0" style={{ fontFamily: 'ui-monospace, monospace' }}>
              {truncate(e.identifier, 20)}
            </text>
            <text x={EVIDENCE.x + 24} y={ey + 9} fontSize={8} fill={failed ? '#fca5a5' : '#94a3b8'}>
              {failed ? 'Rejected · ' : ''}
              {truncate(e.sourceName, 22)}
            </text>
            <title>{`${e.title}\n${e.identifier} · ${meta.label} · ${VERIFY_META[e.verificationStatus].label}`}</title>
          </g>
        )
      })}
    </svg>
  )
}

// ============================================================================
// Evidence card
// ============================================================================
function EvidenceCard({ e, selected, onSelect }: { e: EvidenceItem; selected: boolean; onSelect: () => void }) {
  const dir = DIRECTION_META[e.evidenceDirection]
  const ver = VERIFY_META[e.verificationStatus]
  const failed = e.verificationStatus === 'failed'

  const ring = failed
    ? 'border-helix-red/60 ring-1 ring-helix-red/40'
    : selected
      ? 'border-helix-cyan/60 ring-1 ring-helix-cyan/40'
      : ''

  return (
    <Panel className={`card-hover cursor-pointer p-4 ${ring}`}>
      <div id={`ev-card-${e.id}`} onClick={onSelect}>
        <div className="mb-2 flex flex-wrap items-center gap-2">
          <Badge tone={dir.tone} icon={dir.icon}>{dir.label}</Badge>
          <Badge tone={ver.tone} icon={ver.icon}>{ver.label}</Badge>
          <span className="ml-auto">
            <SourceBadge source={e.sourceType} />
          </span>
        </div>

        <div className="text-sm font-semibold leading-snug text-white">{e.title}</div>
        <div className="mt-0.5 text-[11px] text-slate-500">
          {e.sourceName} · {e.authors} · {e.year}
        </div>

        <p className="mt-2 text-xs leading-relaxed text-slate-300">{e.claim}</p>

        <div className="mt-3 flex flex-wrap items-center gap-2 text-[10px]">
          <span className="rounded border border-line bg-bg-soft px-1.5 py-0.5 font-mono tabular-nums text-slate-400">
            {e.identifierType}: {e.identifier}
          </span>
          {e.relatedTarget && (
            <span className="flex items-center gap-1 rounded border border-helix-cyan/25 bg-helix-cyan/10 px-1.5 py-0.5 text-helix-cyan">
              <Icon name="Crosshair" size={10} />
              {e.relatedTarget}
            </span>
          )}
        </div>

        <div className="mt-3">
          <ConfidenceMeter value={e.confidence} label="Evidence confidence" compact />
        </div>

        {failed ? (
          <div className="mt-3 flex items-start gap-2 rounded-lg border border-helix-red/40 bg-helix-red/10 p-2.5 text-[11px] leading-relaxed text-red-300">
            <Icon name="ShieldX" size={14} className="mt-0.5 shrink-0" />
            <span>
              <span className="font-semibold">Rejected by Citation Verifier.</span> Identifier could not be resolved to a
              real source and the claim was overstated. Demoted and excluded from target ranking and downstream reasoning.
            </span>
          </div>
        ) : e.notes ? (
          <div className="mt-3 flex items-start gap-2 text-[11px] leading-relaxed text-slate-500">
            <Icon name="Info" size={12} className="mt-0.5 shrink-0" />
            <span>{e.notes}</span>
          </div>
        ) : null}
      </div>
    </Panel>
  )
}
