import { useState } from 'react'
import { api, SOURCE_META } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

const POOL = ['CCO', 'CCN', 'CCC', 'CCCC', 'c1ccccc1', 'c1ccncc1', 'CC(=O)O', 'CCOC(=O)C', 'CCCCO', 'CCCCN',
  'c1ccc(O)cc1', 'c1ccc(N)cc1', 'CCCCCC', 'CCCCCCO', 'CCCCCCCCO', 'CCCCCCCCCC', 'c1ccc(C)cc1', 'c1ccc(CO)cc1']
  .map((s) => ({ smiles: s, label: /O/.test(s) ? 1 : 0 }))

const STRATEGIES = ['uncertainty', 'top_score', 'uncertainty_x_utility', 'diversity_uncertainty', 'random']

function SBadge({ type }: { type?: string }) {
  if (!type) return null
  const m = SOURCE_META[type] || { label: type, tone: 'slate' }
  return <Badge tone={m.tone}>{m.label}</Badge>
}

export function ActiveLearning() {
  const [strategy, setStrategy] = useState('uncertainty')
  const [res, setRes] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function run() {
    setLoading(true); setErr('')
    try { setRes(await api.activeLearningRun({ pool: POOL, strategy, cycles: 4, batch_size: 2, initial_labeled: 4 })) }
    catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="Radar" size={22} />}
        title="Active Learning"
        subtitle="CPU active-learning simulation: which candidates deserve expensive GPU calculations or future experiments? Compared against a random baseline. Oracle = held-out dataset, NOT experiments."
        actions={<div className="flex gap-2">
          <select className="input" value={strategy} onChange={(e) => setStrategy(e.target.value)}>
            {STRATEGIES.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
          <button className="btn-primary" onClick={run} disabled={loading}>
            {loading ? <Icon name="Loader2" size={14} className="animate-spin" /> : <Icon name="Play" size={14} />} Run simulation
          </button>
        </div>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Running active-learning cycles…" /> : !res ? (
        <Empty>Choose an acquisition strategy and run the simulation.</Empty>
      ) : res.status && res.status !== 'OK' && !res.id ? (
        <Panel><Empty>{res.status}: {res.reason || 'insufficient data for a simulation.'}</Empty></Panel>
      ) : (
        <div className="space-y-4">
          <Panel>
            <div className="mb-2 flex items-center gap-2">
              <div className="section-title">Result</div>
              <SBadge type={res.source_type} />
              <Badge tone={res.beats_random ? 'green' : 'amber'}>{res.beats_random ? 'beats random' : 'vs random'}</Badge>
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
              <div>Strategy: <span className="text-slate-200">{res.strategy}</span></div>
              <div>Mean hit rate: <span className="text-slate-200">{res.mean_hit_rate}</span></div>
              <div>Random baseline: <span className="text-slate-200">{res.random_baseline?.mean_hit_rate}</span></div>
              <div>AUC: <span className="text-slate-200">{res.area_under_learning_curve}</span></div>
            </div>
            <div className="mt-2 rounded bg-white/5 px-2 py-1 text-[11px] text-slate-400">Oracle: {res.oracle_mode} — {res.oracle_note}</div>
          </Panel>

          <Panel>
            <div className="section-title mb-2">Learning curve</div>
            <div className="space-y-1">
              {(res.learning_curve || []).map((c: any) => (
                <div key={c.cycle} className="flex items-center gap-2 text-xs">
                  <span className="w-16 text-slate-500">cycle {c.cycle}</span>
                  <div className="h-3 flex-1 rounded bg-white/5">
                    <div className="h-3 rounded bg-brand-400/60" style={{ width: `${Math.round((c.metric ?? 0) * 100)}%` }} />
                  </div>
                  <span className="w-14 text-right text-slate-300">{c.metric ?? '—'}</span>
                  <span className="w-24 text-right text-slate-500">labeled {c.labeled_count}</span>
                </div>
              ))}
            </div>
          </Panel>

          <Panel>
            <div className="section-title mb-2">GPU escalation candidates</div>
            <div className="flex flex-wrap gap-1">
              {(res.gpu_escalation_candidates || []).map((c: any, i: number) => (
                <Badge key={i} tone="cyan">{c.smiles}</Badge>
              ))}
            </div>
            <div className="mt-2 text-[11px] text-slate-500">{(res.limitations || [])[0]}</div>
          </Panel>
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}
