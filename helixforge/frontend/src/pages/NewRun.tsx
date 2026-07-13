import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, rememberRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, ErrorNote, Field, PageHeader, Panel, Spinner } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

export function NewRun() {
  const nav = useNavigate()
  const [cfg, setCfg] = useState<any | null>(null)
  const [target, setTarget] = useState('EGFR')
  const [condition, setCondition] = useState('non-small cell lung cancer')
  const [maxResults, setMaxResults] = useState(8)
  const [mode, setMode] = useState('retrospective_rediscovery')
  const [injections, setInjections] = useState<Record<string, boolean>>({})
  const [validation, setValidation] = useState<any | null>(null)
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [err, setErr] = useState('')

  useEffect(() => {
    let active = true
    api.runConfigs()
      .then((result) => { if (active) setCfg(result) })
      .catch((error: unknown) => { if (active) setErr(error instanceof Error ? error.message : 'Failed to load run presets.') })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  function applyPreset(p: any) {
    setTarget(p.target_query); setCondition(p.condition); setValidation(null)
  }
  function toggleInjection(id: string) {
    setInjections((s) => ({ ...s, [id]: !s[id] })); setValidation(null)
  }

  async function validate() {
    setErr('')
    try {
      setValidation(await api.runConfigValidate({
        target_query: target, condition, max_results: maxResults,
        evaluation_mode: mode, error_injections: injections,
      }))
    } catch (e: any) { setErr(e.message) }
  }

  async function launch() {
    setRunning(true); setErr('')
    try {
      const v = await api.runConfigValidate({
        target_query: target, condition, max_results: maxResults,
        evaluation_mode: mode, error_injections: injections,
      })
      setValidation(v)
      if (!v.valid) { setRunning(false); return }
      const result = await api.runAgentic(v.normalized_payload)
      rememberRunId(result.run_id)
      nav(`/cockpit?run=${result.run_id}`)
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : 'Failed to launch run.')
    } finally {
      setRunning(false)
    }
  }

  if (loading) return <Spinner label="Loading run presets…" />

  return (
    <div>
      <PageHeader
        icon={<Icon name="Rocket" size={22} />}
        title="New Run"
        subtitle="Configure and launch a multi-agent pipeline. Pick a validated preset or enter a custom target/indication, choose an evaluation mode, and optionally inject errors to demo self-correction."
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
        <div className="space-y-4">
          <Panel>
            <div className="mb-2 section-title">1 · Presets <span className="text-slate-500">(real target/indication pairs)</span></div>
            <div className="grid gap-2 sm:grid-cols-2">
              {cfg?.presets.map((p: any) => (
                <button key={p.id} onClick={() => applyPreset(p)}
                  className={`rounded-lg border px-3 py-2 text-left text-xs transition ${target === p.target_query && condition === p.condition ? 'border-brand-400 bg-brand-400/10' : 'border-white/8 hover:border-white/20'}`}>
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-slate-200">{p.label}</span>
                    {p.recommended && <Badge tone="green">권장</Badge>}
                  </div>
                  <div className="mt-0.5 text-slate-500">{p.rationale}</div>
                </button>
              ))}
            </div>
          </Panel>

          <Panel>
            <div className="mb-2 section-title">2 · Configuration</div>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="Target (gene/protein)"><input className="input" value={target} onChange={(e) => { setTarget(e.target.value); setValidation(null) }} /></Field>
              <Field label="Condition / indication"><input className="input" value={condition} onChange={(e) => { setCondition(e.target.value); setValidation(null) }} /></Field>
              <Field label="Max molecule candidates"><input type="number" min={1} max={50} className="input" value={maxResults} onChange={(e) => { setMaxResults(Number(e.target.value)); setValidation(null) }} /></Field>
              <Field label="Evaluation mode">
                <select className="input" value={mode} onChange={(e) => { setMode(e.target.value); setValidation(null) }}>
                  {cfg?.modes.map((m: any) => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              </Field>
            </div>
          </Panel>

          <Panel>
            <div className="mb-2 section-title">3 · Error injections <span className="text-slate-500">(optional — demonstrates self-correction)</span></div>
            <div className="flex flex-wrap gap-2">
              {cfg?.error_injection_options.map((o: any) => (
                <button key={o.id} aria-pressed={Boolean(injections[o.id])} onClick={() => toggleInjection(o.id)}
                  className={`rounded-full border px-3 py-1 text-xs transition ${injections[o.id] ? 'border-helix-amber bg-helix-amber/10 text-helix-amber' : 'border-white/8 text-slate-400 hover:border-white/20'}`}>
                  {injections[o.id] ? '✓ ' : ''}{o.label}
                </button>
              ))}
            </div>
          </Panel>
        </div>

        <div className="space-y-4">
          <Panel>
            <div className="mb-2 section-title">Launch</div>
            <div className="space-y-2 text-xs text-slate-400">
              <div>Target: <span className="text-slate-200">{target || '—'}</span></div>
              <div>Condition: <span className="text-slate-200">{condition || '—'}</span></div>
              <div>Mode: <span className="text-slate-200">{mode}</span></div>
              <div>Injections: <span className="text-slate-200">{Object.values(injections).filter(Boolean).length}</span></div>
            </div>
            <div className="mt-3 flex flex-col gap-2">
              <button className="btn-secondary" onClick={validate} disabled={running}><Icon name="CheckCircle2" size={14} /> Validate</button>
              <button className="btn-primary" onClick={launch} disabled={running}>
                {running ? <><Icon name="Loader2" size={14} className="animate-spin" /> Running…</> : <><Icon name="Play" size={14} /> Launch run</>}
              </button>
            </div>
            {validation && (
              <div className="mt-3 space-y-1 text-xs">
                <Badge tone={validation.valid ? 'green' : 'red'}>{validation.valid ? 'VALID' : 'INVALID'}</Badge>
                {validation.errors?.map((e: string, i: number) => <div key={i} className="text-helix-red">✕ {e}</div>)}
                {validation.warnings?.map((w: string, i: number) => <div key={i} className="text-helix-amber">⚠ {w}</div>)}
              </div>
            )}
          </Panel>
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      </div>
    </div>
  )
}
