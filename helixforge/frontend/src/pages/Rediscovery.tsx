import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

type Tab = 'rediscovery' | 'library' | 'suitability'

const CONCLUSION_TONE: Record<string, string> = {
  STRONG_RECOVERY: 'green', RECOVERED: 'green', PARTIAL_RECOVERY: 'amber', WEAK_RECOVERY: 'amber',
  NO_RECOVERY: 'red', NOT_APPLICABLE: 'slate', MODALITY_MISMATCH: 'amber',
}

export function Rediscovery() {
  const [tab, setTab] = useState<Tab>('rediscovery')
  const [scenarios, setScenarios] = useState<any | null>(null)
  const [scenarioId, setScenarioId] = useState('')
  const [comparators, setComparators] = useState<any | null>(null)
  const [result, setResult] = useState<any | null>(null)
  const [report, setReport] = useState<string>('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')

  useEffect(() => { (async () => {
    setLoading(true); setErr('')
    try {
      const s = await api.rediscoveryScenarios()
      setScenarios(s)
      const first = s?.scenarios?.[0]?.id
      if (first) setScenarioId(first)
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  })() }, [])

  async function loadComparators(id: string) {
    setBusy('comparators'); setErr('')
    try { setComparators(await api.rediscoveryComparators(id)) }
    catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  function pickScenario(id: string) {
    setScenarioId(id); setResult(null); setReport(''); setComparators(null)
    if (tab === 'library') loadComparators(id)
  }

  function selectTab(t: Tab) {
    setTab(t)
    if (t === 'library' && scenarioId && !comparators) loadComparators(scenarioId)
  }

  async function run() {
    setBusy('run'); setErr(''); setReport('')
    try { setResult(await api.rediscoveryRun({ scenario_id: scenarioId })) }
    catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  async function viewReport() {
    if (!result?.id) return
    setBusy('report'); setErr('')
    try {
      const r = await api.rediscoveryReport(result.id)
      setReport(r?.markdown || r?.report || '')
    } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  const scenarioList = scenarios?.scenarios || []
  const cmpList = comparators?.comparators || []
  const tabs: [Tab, string][] = [
    ['rediscovery', 'Known-drug rediscovery'], ['library', 'Comparator library'], ['suitability', 'Scenario suitability'],
  ]

  return (
    <div>
      <PageHeader
        icon={<Icon name="Target" size={22} />}
        title="Known-Drug Rediscovery"
        subtitle="Retrospective recovery / sanity check against known drug classes — does not prove de novo discovery or clinical efficacy."
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Loading scenarios…" /> : (
        <div className="space-y-4">
          {/* Scenario picker */}
          <Panel>
            <div className="mb-2 flex items-center justify-between">
              <div className="section-title">Scenarios</div>
              <Badge tone={scenarios?.library_valid ? 'green' : 'amber'}>{scenarios?.library_valid ? 'library valid' : 'library check'}</Badge>
            </div>
            {!scenarioList.length ? <Empty>No rediscovery scenarios available.</Empty> : (
              <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                {scenarioList.map((s: any) => (
                  <button key={s.id} onClick={() => pickScenario(s.id)}
                    className={`rounded-lg border px-3 py-2 text-left text-xs transition ${scenarioId === s.id ? 'border-brand-400 bg-brand-400/10' : 'border-white/8 hover:border-white/20'}`}>
                    <div className="font-medium text-slate-200">{s.id}</div>
                    <div className="mt-0.5 text-slate-500">{s.target} · {s.condition}</div>
                    <div className="mt-1 flex items-center gap-2">
                      <Badge tone="slate">{s.modality}</Badge>
                      <span className="text-slate-500">{s.comparator_count} comparators</span>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </Panel>

          {/* Tabs */}
          <div className="flex flex-wrap gap-2">
            {tabs.map(([t, label]) => (
              <button key={t} className={`btn-secondary ${tab === t ? 'ring-1 ring-brand-400' : ''}`} onClick={() => selectTab(t)}>{label}</button>
            ))}
          </div>

          {tab === 'rediscovery' && (
            <Panel>
              <div className="mb-3 flex items-center justify-between">
                <div className="section-title">Known-drug rediscovery</div>
                <button className="btn-primary" disabled={!scenarioId || !!busy} onClick={run}>
                  <Icon name="Play" size={14} /> {busy === 'run' ? 'Running…' : 'Run rediscovery'}
                </button>
              </div>
              {!result ? <Empty>Pick a scenario and run rediscovery.</Empty> : (
                <div className="space-y-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs">
                    <Badge tone={CONCLUSION_TONE[result.conclusion] || 'slate'}>{(result.conclusion || '—').replace(/_/g, ' ')}</Badge>
                    {result.sample_size_warning && <Badge tone="amber">small sample</Badge>}
                    {result.modality_mismatch && <Badge tone="amber">modality mismatch</Badge>}
                  </div>
                  <div className="grid gap-3 sm:grid-cols-3 lg:grid-cols-4">
                    <StatCard label="Best similarity" value={fmtNum(result.best_similarity)} tone="cyan" />
                    <StatCard label="Exact matches" value={result.exact_match_count ?? 0} tone="green" />
                    <StatCard label="Hit@1" value={fmtHit(result.hit_at_1)} tone="slate" />
                    <StatCard label="Hit@5" value={fmtHit(result.hit_at_5)} tone="slate" />
                    <StatCard label="Hit@10" value={fmtHit(result.hit_at_10)} tone="slate" />
                    <StatCard label="Scaffold recovery" value={fmtNum(result.scaffold_recovery_rate)} tone="violet" />
                    <StatCard label="Enrichment factor" value={fmtNum(result.enrichment_factor)} tone="violet" />
                  </div>
                  {(result.limitations || []).length > 0 && (
                    <div className="rounded border border-white/8 p-2 text-xs">
                      <div className="mb-1 text-slate-500">Limitations</div>
                      <ul className="space-y-0.5 text-slate-400">
                        {result.limitations.map((l: string, i: number) => <li key={i}>· {l}</li>)}
                      </ul>
                    </div>
                  )}
                  <div>
                    <button className="btn-secondary" disabled={!!busy} onClick={viewReport}><Icon name="FileText" size={14} /> {busy === 'report' ? '…' : 'View report'}</button>
                    {report && <pre className="mt-3 max-h-[480px] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-black/30 p-4 font-mono text-[11px] leading-relaxed text-slate-300">{report}</pre>}
                  </div>
                </div>
              )}
            </Panel>
          )}

          {tab === 'library' && (
            <Panel>
              <div className="mb-2 section-title">Comparator library {scenarioId && <span className="text-slate-500">· {scenarioId}</span>}</div>
              {busy === 'comparators' ? <Spinner label="Loading comparators…" /> : !cmpList.length ? <Empty>No comparators for this scenario.</Empty> : (
                <div className="flex flex-wrap gap-2">
                  {cmpList.map((c: any, i: number) => (
                    <Badge key={i} tone="slate">{c.name || '—'}</Badge>
                  ))}
                </div>
              )}
              <div className="mt-2 text-[11px] text-slate-500">Known-drug names shown for reference only.</div>
            </Panel>
          )}

          {tab === 'suitability' && (
            <Panel>
              <div className="mb-2 section-title">Scenario suitability</div>
              <div className="space-y-2 text-xs text-slate-400">
                <p>Small-molecule scenarios (e.g. EGFR/NSCLC) are well suited to structural similarity-based rediscovery: known inhibitors share scaffolds that a fingerprint search can recover.</p>
                <p><span className="text-slate-300">PCSK9</span> and <span className="text-slate-300">TNF</span> scenarios are flagged as a <Badge tone="amber">modality mismatch</Badge>: their validated therapeutics are antibodies / biologics (or siRNA), not small molecules. Structural small-molecule similarity cannot meaningfully "rediscover" a biologic, so recovery metrics for these scenarios are not applicable and are reported honestly rather than inflated.</p>
              </div>
            </Panel>
          )}

          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}

function fmtNum(v: any): string {
  const n = typeof v === 'number' ? v : Number(v)
  if (!isFinite(n)) return '—'
  return n.toFixed(3)
}
function fmtHit(v: any): string {
  if (v === true) return 'yes'
  if (v === false) return 'no'
  const n = Number(v)
  if (!isFinite(n)) return '—'
  return n.toFixed(3)
}
