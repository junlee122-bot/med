import { useEffect, useState } from 'react'
import { api, getRememberedRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

type Tab = 'release' | 'biology' | 'translational' | 'clinical' | 'pareto' | 'redteam'

const CAT_TONE: Record<string, string> = { READY: 'green', PARTIAL: 'amber', NOT_READY: 'red', PASS: 'green', REVIEW_REQUIRED: 'amber', BLOCKED: 'red' }

const pendingReviews = new Map<string, Promise<any>>()

function requestReview(tab: Tab, runId: string): Promise<any> {
  const key = tab === 'redteam' ? 'redteam' : `${runId || '__latest__'}:${tab}`
  const existing = pendingReviews.get(key)
  if (existing) return existing
  const request = (tab === 'release' ? api.professionalReleaseCompute(runId || undefined)
    : tab === 'biology' ? api.targetBiologyRun(runId || undefined)
    : tab === 'translational' ? api.translationalRun(runId || undefined)
    : tab === 'clinical' ? api.clinicalPrecedentRun(runId || undefined)
    : tab === 'pareto' ? api.paretoRun(runId || undefined)
    : api.redTeamProfessional())
    .finally(() => pendingReviews.delete(key))
  pendingReviews.set(key, request)
  return request
}

export function ProfessionalReview() {
  const [runId] = useState(getRememberedRunId)
  const [tab, setTab] = useState<Tab>('release')
  const [data, setData] = useState<Record<string, any>>({})
  const [pending, setPending] = useState<Record<Tab, boolean>>({ release: false, biology: false, translational: false, clinical: false, pareto: false, redteam: false })
  const [errors, setErrors] = useState<Record<Tab, string>>({ release: '', biology: '', translational: '', clinical: '', pareto: '', redteam: '' })

  async function load(t: Tab) {
    setTab(t); setErrors((current) => ({ ...current, [t]: '' }))
    if (data[t] || pending[t]) return
    setPending((current) => ({ ...current, [t]: true }))
    try {
      const res = await requestReview(t, runId)
      setData((d) => ({ ...d, [t]: res }))
    } catch (e: unknown) {
      setErrors((current) => ({ ...current, [t]: e instanceof Error ? e.message : 'Professional review failed.' }))
    } finally { setPending((current) => ({ ...current, [t]: false })) }
  }

  useEffect(() => {
    let active = true
    setData({})
    setErrors({ release: '', biology: '', translational: '', clinical: '', pareto: '', redteam: '' })
    setPending({ release: true, biology: false, translational: false, clinical: false, pareto: false, redteam: false })
    requestReview('release', runId)
      .then((result) => { if (active) setData((current) => ({ ...current, release: result })) })
      .catch((reason: unknown) => { if (active) setErrors((current) => ({ ...current, release: reason instanceof Error ? reason.message : 'Professional review failed.' })) })
      .finally(() => { if (active) setPending((current) => ({ ...current, release: false })) })
    return () => { active = false }
  }, [runId])

  const cur = data[tab]
  const loading = pending[tab]
  const err = errors[tab]
  const tabs: [Tab, string][] = [
    ['release', 'Release Scorecard'], ['biology', 'Target Biology'], ['translational', 'Translational'],
    ['clinical', 'Clinical Precedent'], ['pareto', 'Pareto Front'], ['redteam', 'Scientific Red-Team'],
  ]
  return (
    <div>
      <PageHeader icon={<Icon name="Microscope" size={22} />} title="Professional Review"
        subtitle="Expert-grade review layer: 16-category release scorecard, target biology plausibility, translational readiness (capped without wet-lab), clinical precedent (precedent ≠ efficacy), Pareto trade-offs, and a scientific red-team." />
      <div className="mb-4 flex flex-wrap gap-2">
        {tabs.map(([t, label]) => (
          <button key={t} aria-pressed={tab === t} className={`btn-secondary ${tab === t ? 'ring-1 ring-brand-400' : ''}`} disabled={pending[t]} onClick={() => load(t)}>{label}</button>
        ))}
      </div>
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Loading review…" /> : !cur ? <Empty>No data.</Empty> : (
        <div className="space-y-4">
          {tab === 'release' && <ReleaseView d={cur} />}
          {tab === 'biology' && <BiologyView d={cur} />}
          {tab === 'translational' && <TranslationalView d={cur} />}
          {tab === 'clinical' && <ClinicalView d={cur} />}
          {tab === 'pareto' && <ParetoView d={cur} />}
          {tab === 'redteam' && <RedTeamView d={cur} />}
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}

function ReleaseView({ d }: { d: any }) {
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard label="Overall" value={`${d.overall_score}/100`} sub={<Badge tone={CAT_TONE[d.status] || 'slate'}>{d.status?.replace(/_/g, ' ')}</Badge>} tone="cyan" />
        <StatCard label="Blocking issues" value={d.blocking_count} tone={d.blocking_count ? 'red' : 'green'} />
        <StatCard label="Categories" value={d.categories?.length ?? 0} tone="violet" />
      </div>
      <Panel>
        <div className="overflow-x-auto"><table className="w-full text-xs">
          <thead><tr className="text-left text-slate-500"><th className="py-1 pr-2">#</th><th className="pr-2">Category</th><th className="pr-2">Score</th><th className="pr-2">Status</th><th>Action</th></tr></thead>
          <tbody>{d.categories?.map((c: any) => (
            <tr key={c.key} className="border-t border-white/5">
              <td className="py-1 pr-2 text-slate-500">{c.key}</td>
              <td className="pr-2 text-slate-200">{c.label}</td>
              <td className="pr-2 text-slate-300">{c.score}</td>
              <td className="pr-2"><Badge tone={CAT_TONE[c.status] || 'slate'}>{c.status}</Badge></td>
              <td className="text-slate-500">{c.recommended_action}</td>
            </tr>
          ))}</tbody>
        </table></div>
      </Panel>
    </>
  )
}

function BiologyView({ d }: { d: any }) {
  return (
    <Panel><div className="mb-2 section-title">Target biology reviews ({d.count ?? 0})</div>
      {!d.reviews?.length ? <Empty>No targets in the latest run.</Empty> : d.reviews.map((r: any, i: number) => (
        <div key={i} className="mb-2 rounded border border-white/8 p-2 text-xs">
          <div className="flex items-center justify-between"><span className="text-slate-200">{r.target_symbol || r.target_name}</span>
            <Badge tone={r.review_status === 'PASS' ? 'green' : r.review_status === 'NOT_RECOMMENDED' ? 'red' : 'amber'}>{r.review_status}</Badge></div>
          <div className="mt-1 grid gap-1 sm:grid-cols-2">
            {(r.dimensions || []).map((dm: any, j: number) => (
              <div key={j} className="text-slate-500">{dm.name}: <span className="text-slate-300">{dm.score}/5</span></div>
            ))}
          </div>
          {r.expert_next_steps?.length > 0 && <div className="mt-1 text-brand-300">next: {r.expert_next_steps.join(' · ')}</div>}
        </div>
      ))}
    </Panel>
  )
}

function TranslationalView({ d }: { d: any }) {
  return (
    <Panel><div className="mb-2 section-title">Translational readiness</div>
      <div className="mb-2"><Badge tone="cyan">{d.readiness_level}</Badge> <span className="text-[11px] text-slate-500">(capped at TRL_4 — no wet-lab)</span></div>
      {d.blocking_gaps?.length > 0 && <div className="text-xs text-helix-amber">Blocking gaps: {d.blocking_gaps.join('; ')}</div>}
      {d.recommended_next_actions?.length > 0 && <div className="mt-1 text-xs text-slate-400">Next: {d.recommended_next_actions.join(' · ')}</div>}
      <div className="mt-2 text-[11px] text-slate-500">{d.disclaimer}</div>
    </Panel>
  )
}

function ClinicalView({ d }: { d: any }) {
  return (
    <Panel><div className="mb-2 section-title">Clinical precedent review</div>
      <div className="flex flex-wrap gap-2 text-xs">
        <Badge tone="cyan">{d.precedent_strength}</Badge>
        <span className="text-slate-400">{d.trial_count} trials</span>
      </div>
      {d.endpoint_categories && <div className="mt-2 flex flex-wrap gap-1.5 text-xs">{Object.entries(d.endpoint_categories).map(([k, v]: any) => <Badge key={k} tone="slate">{k}: {v}</Badge>)}</div>}
      {d.failure_or_termination_signals?.length > 0 && <div className="mt-1 text-xs text-helix-amber">⚠ termination signals: {d.failure_or_termination_signals.length}</div>}
      <div className="mt-2 text-[11px] text-slate-500">{d.disclaimer}</div>
    </Panel>
  )
}

function ParetoView({ d }: { d: any }) {
  return (
    <Panel><div className="mb-2 flex items-center justify-between"><div className="section-title">Pareto front</div>
      <Badge tone={d.no_single_best ? 'amber' : 'green'}>{d.no_single_best ? 'trade-offs — no single best' : 'clear leader'}</Badge></div>
      {!d.all_candidates?.length ? <Empty>No molecules.</Empty> : (
        <div className="overflow-x-auto"><table className="w-full text-xs">
          <thead><tr className="text-left text-slate-500"><th className="py-1 pr-2">Molecule</th><th className="pr-2">Rank</th><th className="pr-2">Role</th><th className="pr-2">Conf.</th><th>Trade-off</th></tr></thead>
          <tbody>{d.all_candidates.slice(0, 60).map((c: any, i: number) => (
            <tr key={i} className="border-t border-white/5"><td className="py-1 pr-2 text-slate-300">{c.label || c.molecule_id}</td>
              <td className="pr-2 text-slate-400">{c.pareto_rank}{c.pareto_rank === 1 ? ' ★' : ''}</td>
              <td className="pr-2"><Badge tone="slate">{c.recommended_role}</Badge></td>
              <td className="pr-2 text-slate-400">{c.confidence}</td>
              <td className="text-slate-500">{c.tradeoff_summary}</td></tr>
          ))}</tbody>
        </table></div>
      )}
    </Panel>
  )
}

function RedTeamView({ d }: { d: any }) {
  return (
    <Panel><div className="mb-2 flex items-center justify-between"><div className="section-title">Scientific red-team ({d.total})</div>
      <Badge tone={d.status === 'PASS' ? 'green' : 'red'}>{d.passed}/{d.total} {d.status}</Badge></div>
      <div className="grid gap-1.5 sm:grid-cols-2">
        {d.results?.map((r: any) => (
          <div key={r.id} className="flex items-center gap-2 rounded border border-white/5 px-2 py-1 text-xs">
            <Icon name={r.defended ? 'ShieldCheck' : 'ShieldAlert'} size={14} className={r.defended ? 'text-brand-300' : 'text-helix-red'} />
            <span className="text-slate-500">{r.id}</span><span className="text-slate-300">{r.name}</span>
            <Badge tone="slate" className="ml-auto">{r.module}</Badge>
          </div>
        ))}
      </div>
    </Panel>
  )
}
