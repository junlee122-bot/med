import { useEffect, useState } from 'react'
import { api, getRememberedRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

const GRADE_TONE: Record<string, string> = {
  A_STRONG: 'green', B_MODERATE: 'cyan', C_PRELIMINARY: 'amber',
  D_WEAK: 'amber', E_UNVERIFIED: 'slate', F_CONTRADICTED: 'red',
}
const GRADE_LABEL: Record<string, string> = {
  A_STRONG: 'A · Strong', B_MODERATE: 'B · Moderate', C_PRELIMINARY: 'C · Preliminary',
  D_WEAK: 'D · Weak', E_UNVERIFIED: 'E · Unverified', F_CONTRADICTED: 'F · Contradicted',
}

const pendingGradeRequests = new Map<string, Promise<any>>()

function requestEvidenceGrades(runId: string): Promise<any> {
  const key = runId || '__latest__'
  const existing = pendingGradeRequests.get(key)
  if (existing) return existing
  const request = api.evidenceGradesRun(runId || undefined)
    .finally(() => pendingGradeRequests.delete(key))
  pendingGradeRequests.set(key, request)
  return request
}

function ClaimTable({ claims }: { claims: any[] }) {
  const [filter, setFilter] = useState('all')
  const shown = filter === 'all' ? claims : claims.filter((c) => c.claim_type === filter)
  const types = Array.from(new Set(claims.map((c) => c.claim_type)))
  if (!claims.length) return <Empty>No claims graded — run the pipeline first.</Empty>
  return (
    <div>
      <div className="mb-2 flex flex-wrap gap-1.5">
        <button className={`badge ${filter === 'all' ? 'ring-1 ring-brand-400' : ''}`} onClick={() => setFilter('all')}>all ({claims.length})</button>
        {types.map((t) => (
          <button key={t} className={`badge ${filter === t ? 'ring-1 ring-brand-400' : ''}`} onClick={() => setFilter(t)}>{t}</button>
        ))}
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="text-left text-slate-500">
            <th className="py-1 pr-2">Claim</th><th className="pr-2">Type</th><th className="pr-2">Grade</th>
            <th className="pr-2">Levels</th><th className="pr-2">Sup/Con</th><th>Uncertainty</th>
          </tr></thead>
          <tbody>
            {shown.map((c) => (
              <tr key={c.id} className="border-t border-white/5 align-top">
                <td className="py-1.5 pr-2 text-slate-200 max-w-[280px]">{c.claim_text || '—'}</td>
                <td className="pr-2 text-slate-400">{c.claim_type}</td>
                <td className="pr-2"><Badge tone={GRADE_TONE[c.evidence_grade]}>{GRADE_LABEL[c.evidence_grade] || c.evidence_grade}</Badge></td>
                <td className="pr-2 text-slate-500">{(c.evidence_levels || []).map((l: string) => l.replace(/^LEVEL_\d+_/, '').replace(/_/g, ' ').slice(0, 14)).join(', ') || '—'}</td>
                <td className="pr-2 text-slate-400">{c.support_count}/{c.contradiction_count}</td>
                <td className="text-slate-500">{(c.uncertainty_reasons || []).join('; ') || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function EvidenceGrading() {
  const [runId] = useState(getRememberedRunId)
  const [data, setData] = useState<any | null>(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [lintText, setLintText] = useState('Our system proved the molecule is clinically validated and cures the disease.')
  const [lint, setLint] = useState<any | null>(null)
  const [linting, setLinting] = useState(false)

  async function load() {
    setLoading(true); setErr('')
    try { setData(await requestEvidenceGrades(runId)) }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : 'Evidence grading failed.') }
    finally { setLoading(false) }
  }
  useEffect(() => {
    let active = true
    setData(null); setErr(''); setLoading(true)
    requestEvidenceGrades(runId)
      .then((result) => { if (active) setData(result) })
      .catch((reason: unknown) => { if (active) setErr(reason instanceof Error ? reason.message : 'Evidence grading failed.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [runId])
  async function runLint() {
    setLinting(true); setErr('')
    try { setLint(await api.evidenceGradeLint(lintText)) }
    catch (e: unknown) { setErr(e instanceof Error ? e.message : 'Evidence lint failed.') }
    finally { setLinting(false) }
  }

  const dist = data?.grade_distribution || {}
  const all = data ? [...(data.hypotheses?.graded_claims || []), ...(data.targets?.graded_claims || []), ...(data.molecules?.graded_claims || [])] : []

  return (
    <div>
      <PageHeader
        icon={<Icon name="Scale" size={22} />}
        title="Evidence Grading"
        subtitle="Every claim graded by evidence STRENGTH (9-level hierarchy → A–F). Assay evidence is not efficacy, clinical precedent is not proof, failed citations force E, contradictions force F."
        actions={<button className="btn-secondary" onClick={load} disabled={loading}><Icon name="RefreshCw" size={14} /> Recompute</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Grading claims…" /> : (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-6">
            <StatCard label="Total claims" value={data?.total_claims ?? 0} tone="cyan" />
            {['A_STRONG', 'B_MODERATE', 'C_PRELIMINARY', 'E_UNVERIFIED', 'F_CONTRADICTED'].map((g) => (
              <StatCard key={g} label={GRADE_LABEL[g]} value={dist[g] || 0} tone={GRADE_TONE[g]} />
            ))}
          </div>
          <Panel><div className="mb-2 section-title">Graded claims</div><ClaimTable claims={all} /></Panel>

          <Panel>
            <div className="mb-2 section-title">Unsupported strong-claim linter</div>
            <textarea className="input min-h-[80px] font-mono text-xs" value={lintText} onChange={(e) => setLintText(e.target.value)} />
            <div className="mt-2 flex items-center gap-2">
              <button className="btn-primary" onClick={runLint} disabled={linting}><Icon name="Search" size={14} /> {linting ? 'Linting…' : 'Lint claim language'}</button>
              {lint && <Badge tone={lint.status === 'BLOCKED' ? 'red' : lint.status === 'REVIEW_REQUIRED' ? 'amber' : 'green'}>{lint.status}</Badge>}
            </div>
            {lint && lint.findings?.length > 0 && (
              <ul className="mt-2 space-y-1 text-xs">
                {lint.findings.map((f: any, i: number) => (
                  <li key={i} className="text-slate-400"><Badge tone={f.severity === 'BLOCKED' ? 'red' : 'amber'}>{f.severity}</Badge> <span className="text-slate-300">{f.phrase}</span> — {f.reason}</li>
                ))}
              </ul>
            )}
          </Panel>
          {data?.disclaimer && <div className="text-[11px] text-slate-500">{data.disclaimer}</div>}
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}
