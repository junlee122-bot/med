import { useEffect, useState } from 'react'
import { api, getRememberedRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

const BAND_TONE: Record<string, string> = { STRONG: 'green', COMPETITIVE: 'amber', NEEDS_WORK: 'red' }
const VERDICT_TONE: Record<string, string> = {
  PASS: 'green', REVIEW_REQUIRED: 'amber', BLOCKED: 'red', FAIL: 'red', NO_RUN: 'slate',
}

export function PeerReview() {
  const [runId] = useState(getRememberedRunId)
  const [scorecard, setScorecard] = useState<any | null>(null)
  const [redTeam, setRedTeam] = useState<any | null>(null)
  const [plaus, setPlaus] = useState<any | null>(null)
  const [gov, setGov] = useState<any | null>(null)
  const [rights, setRights] = useState<any | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  async function load() {
    setLoading(true); setErr('')
    try {
      const results = await Promise.allSettled([
        api.rubricScorecard(), api.redTeamRun(), api.plausibilityCheck(runId || undefined),
        api.sourceTypeAudit(runId || undefined), api.dataRights(),
      ])
      const setters = [setScorecard, setRedTeam, setPlaus, setGov, setRights]
      results.forEach((result, index) => {
        setters[index](result.status === 'fulfilled' ? result.value : null)
      })
      const failures = results.filter((result): result is PromiseRejectedResult => result.status === 'rejected')
      if (failures.length) setErr(failures.map((failure) => failure.reason instanceof Error ? failure.reason.message : String(failure.reason)).join('; '))
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [runId])

  return (
    <div>
      <PageHeader
        icon={<Icon name="ClipboardCheck" size={22} />}
        title="Peer Review Mode"
        subtitle="A reviewer's-eye pass: self-assessed rubric score, adversarial red-team results, molecule plausibility, source-type governance, and data rights — all in one view. Every panel is honest about gaps."
        actions={<button className="btn-secondary" onClick={load} disabled={loading}><Icon name="RefreshCw" size={14} /> Re-run</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Running peer-review checks…" /> : (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-4">
            <StatCard label="Self-assessed score" value={scorecard ? `${scorecard.total_score}/100` : '—'}
              sub={scorecard && <Badge tone={BAND_TONE[scorecard.band]}>{scorecard.band}</Badge>} tone="cyan" />
            <StatCard label="Red-team defended" value={redTeam ? `${redTeam.passed}/${redTeam.total}` : '—'}
              sub={redTeam && <Badge tone={VERDICT_TONE[redTeam.status]}>{redTeam.status}</Badge>} tone="green" />
            <StatCard label="Molecule plausibility" value={plaus ? (plaus.plausible_fraction != null ? `${Math.round(plaus.plausible_fraction * 100)}%` : 'n/a') : '—'}
              sub={plaus && <Badge tone={VERDICT_TONE[plaus.status] || 'slate'}>{plaus.status}</Badge>} tone="violet" />
            <StatCard label="Source governance" value={gov ? gov.status : '—'}
              sub={gov && <Badge tone={VERDICT_TONE[gov.status] || 'slate'}>{gov.status}</Badge>} tone="amber" />
          </div>

          {/* Rubric scorecard */}
          <Panel>
            <div className="mb-2 flex items-center justify-between">
              <div className="section-title">Rubric Scorecard <span className="text-slate-500">(self-assessment)</span></div>
              {scorecard && <Badge tone="slate">HEURISTIC_ANALYSIS</Badge>}
            </div>
            {!scorecard ? <Empty>No scorecard.</Empty> : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-slate-500">
                    <th className="py-1 pr-2">Criterion</th><th className="pr-2">Weight</th>
                    <th className="pr-2">Self-score</th><th className="pr-2">Points</th><th>Honest gap</th>
                  </tr></thead>
                  <tbody>
                    {scorecard.criteria.map((c: any) => (
                      <tr key={c.key} className="border-t border-white/5 align-top">
                        <td className="py-1.5 pr-2 text-slate-200">{c.label_ko}{c.capped && <span className="ml-1 text-helix-amber" title={c.cap_reason}>▲cap</span>}</td>
                        <td className="pr-2 text-slate-400">{c.weight}</td>
                        <td className="pr-2 text-slate-300">{c.self_score}</td>
                        <td className="pr-2 text-slate-300">{c.weighted_points}</td>
                        <td className="text-slate-500">{c.gap}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="mt-2 text-[11px] text-slate-500">{scorecard.disclaimer}</div>
              </div>
            )}
          </Panel>

          {/* Red-team */}
          <Panel>
            <div className="mb-2 section-title">Adversarial Red-Team ({redTeam?.total ?? 0} scenarios)</div>
            {!redTeam ? <Empty>No results.</Empty> : (
              <div className="grid gap-1.5 sm:grid-cols-2">
                {redTeam.results.map((r: any) => (
                  <div key={r.id} className="flex items-center gap-2 rounded border border-white/5 px-2 py-1 text-xs">
                    <Icon name={r.defended ? 'ShieldCheck' : 'ShieldAlert'} size={14} className={r.defended ? 'text-brand-300' : 'text-helix-red'} />
                    <span className="text-slate-500">{r.id}</span>
                    <span className="text-slate-300">{r.name}</span>
                    <Badge tone={r.defended ? 'green' : 'red'} className="ml-auto">{r.defended ? 'defended' : 'FAIL'}</Badge>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            {/* Plausibility */}
            <Panel>
              <div className="mb-2 section-title">Scientific Plausibility</div>
              {!plaus ? <Empty>No run.</Empty> : plaus.status === 'NO_RUN' ? (
                <Empty>{plaus.note}</Empty>
              ) : (
                <div className="space-y-2 text-xs">
                  <div className="text-slate-400">Molecules checked: <span className="text-slate-200">{plaus.molecule_count}</span></div>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(plaus.verdict_counts || {}).map(([k, v]: any) => (
                      <Badge key={k} tone={k === 'PLAUSIBLE' ? 'green' : k === 'IMPLAUSIBLE' ? 'red' : 'amber'}>{k}: {v}</Badge>
                    ))}
                  </div>
                  {plaus.warnings?.map((w: string, i: number) => <div key={i} className="text-helix-amber">⚠ {w}</div>)}
                  {plaus.target_flags?.map((w: string, i: number) => <div key={i} className="text-slate-500">• {w}</div>)}
                  <div className="text-[11px] text-slate-500">{plaus.disclaimer}</div>
                </div>
              )}
            </Panel>

            {/* Data rights */}
            <Panel>
              <div className="mb-2 section-title">Data Rights & Attribution</div>
              {!rights ? <Empty>No data.</Empty> : (
                <div className="space-y-2 text-xs">
                  <div className="text-slate-400">{rights.records.length} sources · {rights.review_required_sources.length} REVIEW_REQUIRED</div>
                  <div className="max-h-52 overflow-y-auto">
                    {rights.records.map((r: any) => (
                      <div key={r.source} className="flex items-center gap-2 border-t border-white/5 py-1">
                        <span className="flex-1 text-slate-300">{r.source}</span>
                        <Badge tone={r.status === 'PASS' ? 'green' : 'amber'}>{r.status}</Badge>
                      </div>
                    ))}
                  </div>
                  <div className="text-[11px] text-slate-500">{rights.third_party_notice}</div>
                </div>
              )}
            </Panel>
          </div>

          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}
