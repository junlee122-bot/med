import { useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, Field, PageHeader, Panel, SourceBadge, Spinner } from '@/components/ui'

const WEIGHT_KEYS = ['qed', 'rdkit_validity', 'admet', 'novelty', 'safety_penalty'] as const

export function ReinventStudio() {
  const [target, setTarget] = useState('EGFR')
  const [objective, setObjective] = useState('optimize small molecule candidates')
  const [maxMol, setMaxMol] = useState(100)
  const [weights, setWeights] = useState<Record<string, number>>({ qed: 0.2, rdkit_validity: 0.2, admet: 0.2, novelty: 0.2, safety_penalty: 0.2 })
  const [cfg, setCfg] = useState<any | null>(null)
  const [runRes, setRunRes] = useState<any | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const [err, setErr] = useState('')

  async function createConfig() {
    setLoading('cfg'); setErr(''); setRunRes(null)
    try { setCfg(await api.reinventCreateConfig({ target_name: target, objective, scoring_weights: weights, max_molecules: maxMol })) }
    catch (e: any) { setErr(e.message) } finally { setLoading(null) }
  }
  async function runJob() {
    if (!cfg?.config_path) return
    setLoading('run'); setErr('')
    try { setRunRes(await api.reinventRun(cfg.config_path)) } catch (e: any) { setErr(e.message) } finally { setLoading(null) }
  }

  const total = WEIGHT_KEYS.reduce((s, k) => s + (weights[k] || 0), 0)

  return (
    <div>
      <PageHeader
        icon={<Icon name="Boxes" size={22} />}
        title="REINVENT4 Job Studio"
        subtitle="Generate a real REINVENT4 TOML config from a scoring profile, then run it if a REINVENT4 runtime is configured. Generated SMILES are re-validated by RDKit. If not installed, the job reports CONFIGURED_BUT_NOT_RUN."
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <div className="section-title mb-3">Scoring profile</div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Target name"><input className="input" value={target} onChange={(e) => setTarget(e.target.value)} /></Field>
            <Field label="Max molecules"><input type="number" className="input" value={maxMol} onChange={(e) => setMaxMol(+e.target.value)} /></Field>
          </div>
          <div className="mt-3"><Field label="Objective"><input className="input" value={objective} onChange={(e) => setObjective(e.target.value)} /></Field></div>
          <div className="mt-4">
            <div className="mb-2 flex items-center justify-between"><span className="label !mb-0">Scoring weights</span><Badge tone={Math.abs(total - 1) < 0.001 ? 'green' : 'amber'}>Σ {total.toFixed(2)}</Badge></div>
            <div className="space-y-3">
              {WEIGHT_KEYS.map((k) => (
                <div key={k}>
                  <div className="mb-1 flex items-center justify-between text-xs text-slate-400"><span>{k}</span><span className="font-mono text-slate-300">{weights[k].toFixed(2)}</span></div>
                  <input type="range" min={0} max={1} step={0.05} value={weights[k]} onChange={(e) => setWeights((w) => ({ ...w, [k]: +e.target.value }))} className="w-full accent-helix-cyan" />
                </div>
              ))}
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <button className="btn-primary" onClick={createConfig} disabled={!!loading}><Icon name="FileCog" size={15} /> Create config</button>
            <button className="btn-secondary" onClick={runJob} disabled={!!loading || !cfg?.config_path}><Icon name="Play" size={15} /> Run job</button>
          </div>
        </Panel>

        <Panel>
          <div className="section-title mb-3">Job result</div>
          {loading && <Spinner label={loading === 'cfg' ? 'Writing REINVENT4 config…' : 'Attempting REINVENT4 run…'} />}
          {!loading && !cfg && <Empty>Create a config to generate a real REINVENT4 TOML file, then run it.</Empty>}
          {cfg && (
            <div>
              <div className="mb-3 flex flex-wrap items-center gap-2"><SourceBadge type={cfg.source_type} /><span className="text-sm text-slate-300">Config</span></div>
              {cfg.config_path && <div className="rounded-lg border border-line bg-black/40 p-2 font-mono text-[10px] text-slate-400">{cfg.config_path}</div>}
              <div className="mt-2 text-xs text-slate-400">{cfg.output_summary}</div>
            </div>
          )}
          {runRes && (
            <div className="mt-4 border-t border-line pt-4">
              <div className="mb-3 flex flex-wrap items-center gap-2"><SourceBadge type={runRes.source_type} /><Badge tone={runRes.status === 'complete' ? 'green' : runRes.status === 'error' ? 'red' : 'amber'}>{runRes.status || 'not_run'}</Badge>{runRes.valid_count != null && <Badge tone="cyan">{runRes.valid_count} RDKit-valid</Badge>}</div>
              <div className="text-xs text-slate-400">{runRes.output_summary}</div>
              {runRes.errors?.length > 0 && <div className="mt-2"><ErrorNote error={runRes.errors.join('; ')} /></div>}
              {runRes.generated_smiles?.length > 0 && (
                <div className="mt-3 max-h-48 overflow-auto rounded-lg border border-line bg-bg-soft/40 p-2 font-mono text-[10px] text-slate-400">
                  {runRes.generated_smiles.slice(0, 40).map((s: string, i: number) => <div key={i}>{s}</div>)}
                </div>
              )}
              {runRes.logs?.length > 0 && <pre className="mt-3 max-h-40 overflow-auto rounded-lg border border-line bg-black/40 p-2 font-mono text-[10px] text-slate-500">{runRes.logs.join('\n')}</pre>}
            </div>
          )}
          <div className="mt-4 text-xs text-slate-500">Install REINVENT4 from its repo and set <span className="mono">REINVENT4_PYTHON</span> / <span className="mono">REINVENT4_BIN</span> in Settings to enable real runs. No RL training happens inside this app.</div>
        </Panel>
      </div>
    </div>
  )
}
