import { useState } from 'react'
import { Link } from 'react-router-dom'
import { api, rememberRunId } from '@/lib/api'
import type { AgenticRunResult, ErrorInjectionResult } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, ErrorNote } from '@/components/ui'

const AGENTS = ['Orchestrator', 'Evidence Miner', 'Citation Verifier', 'Target Scout', 'Hypothesis',
  'Molecule Design', 'Cheminformatics Validator', 'ADMET/TDC', 'Binding', 'Safety Auditor',
  'Clinical Strategy', 'Regulatory Reviewer', 'Critic', 'Evaluation', 'Report Builder']
const TOOLS = ['PubMed', 'ChEMBL', 'ClinicalTrials.gov', 'RDKit', 'TDC', 'AutoDock Vina', 'REINVENT4']

export function Presentation() {
  const [i, setI] = useState(0)
  const [run, setRun] = useState<AgenticRunResult | null>(null)
  const [demo, setDemo] = useState<ErrorInjectionResult | null>(null)
  const [busy, setBusy] = useState('')
  const [koReady, setKoReady] = useState('')
  const [err, setErr] = useState('')

  async function runPipeline() {
    setBusy('pipeline'); setErr('')
    try {
      const next = await api.runAgenticPipeline({ target_query: 'EGFR', max_results: 6, create_reinvent_config: true, error_injections: {} })
      setRun(next); rememberRunId(next.run_id)
    }
    catch (error: unknown) { setErr(error instanceof Error ? error.message : 'Pipeline failed.') }
    finally { setBusy('') }
  }
  async function runDemo(scenario: string) {
    setBusy(scenario); setErr('')
    try {
      const next = await api.runErrorInjectionDemo(scenario)
      setDemo(next); rememberRunId(next.workflow_run_id)
    }
    catch (error: unknown) { setErr(error instanceof Error ? error.message : 'Demo failed.') }
    finally { setBusy('') }
  }
  async function genKo() {
    setBusy('ko'); setErr('')
    try { const r = run ?? await api.runAgenticPipeline({ target_query: 'EGFR', max_results: 6, create_reinvent_config: false }); setRun(r); rememberRunId(r.run_id); setKoReady(r.ko_report_id || '') }
    catch (error: unknown) { setErr(error instanceof Error ? error.message : 'Korean report generation failed.') }
    finally { setBusy('') }
  }

  const m = run?.metrics || {}
  const slides = [
    { title: '1 · Problem', body: (
      <p className="text-lg text-slate-300">신약개발 초기 탐색은 문헌·타깃·분자·독성·임상 선례·규제 리스크가 분리되어 있어 후보 우선순위화에 많은 시간이 듭니다.
        <span className="mt-3 block text-slate-500">Early discovery is fragmented across literature, targets, molecules, toxicity, clinical precedent, and regulatory risk.</span></p>
    )},
    { title: '2 · Solution', body: (
      <p className="text-lg text-slate-300">HelixForge AI connects these steps through a <span className="gradient-text font-semibold">multi-agent, tool-grounded, auditable</span> workflow — real integrations, honest provenance, and visible self-correction.</p>
    )},
    { title: '3 · Architecture', body: (
      <div className="flex flex-wrap gap-2">{AGENTS.map((a) => <span key={a} className="chip border-helix-cyan/30 bg-helix-cyan/10 text-helix-cyan">{a}</span>)}</div>
    )},
    { title: '4 · Real Tool Integration', body: (
      <div className="flex flex-wrap gap-2">{TOOLS.map((t) => <span key={t} className="chip border-brand-500/30 bg-brand-500/10 text-brand-300">{t}</span>)}
        <p className="mt-3 w-full text-sm text-slate-500">Missing tools report CONFIGURED_BUT_NOT_RUN — never a fabricated result.</p></div>
    )},
    { title: '5 · Live Pipeline', body: (
      <div>
        <button className="btn-primary" onClick={runPipeline} disabled={!!busy}><Icon name="Play" size={16} /> {busy === 'pipeline' ? 'Running…' : 'Run EGFR/NSCLC agentic pipeline'}</button>
        {run && (
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[['Agents', run.agent_runs.length], ['Real outputs', m.real_tool_output_count], ['Top target', m.top_target_chembl_id], ['Validity', m.molecule_validity_rate]].map(([l, v]) => (
              <div key={l as string} className="rounded-lg border border-line bg-bg-soft/40 p-3"><div className="text-[10px] uppercase text-slate-500">{l}</div><div className="text-xl font-semibold text-white">{String(v)}</div></div>
            ))}
          </div>
        )}
      </div>
    )},
    { title: '6 · Self-Correction', body: (
      <div>
        <div className="flex flex-wrap gap-2">
          {['invalid_smiles', 'fake_citation', 'overclaim'].map((s) => (
            <button key={s} className="btn-secondary" onClick={() => runDemo(s)} disabled={!!busy}><Icon name="Wand2" size={14} /> {busy === s ? 'Running…' : s.replace('_', ' ')}</button>
          ))}
        </div>
        {demo && (
          <div className="mt-4 grid gap-2 sm:grid-cols-2">
            <div className="rounded-lg border border-helix-red/30 bg-helix-red/5 p-3"><div className="text-[10px] uppercase text-helix-red">Before</div><div className="mt-1 text-sm text-slate-300">{demo.before || '—'}</div></div>
            <div className="rounded-lg border border-brand-500/30 bg-brand-500/5 p-3"><div className="text-[10px] uppercase text-brand-300">After</div><div className="mt-1 text-sm text-slate-300">{demo.after || '—'}</div></div>
          </div>
        )}
      </div>
    )},
    { title: '7 · Candidate Package', body: (
      <p className="text-lg text-slate-300">Real ChEMBL structures, RDKit-validated, ranked by a transparent composite score with safety and uncertainty penalties. <span className="block mt-2 text-slate-500">Open <Link to="/molecules" className="text-helix-cyan">Molecule Lab →</Link></span></p>
    )},
    { title: '8 · Safety Gate', body: (
      <p className="text-lg text-slate-300">Blocked/quarantined candidates show a category only — no actionable hazard detail, no synthesis routes. Reports pass a safety lint before export. <span className="block mt-2 text-slate-500">Open <Link to="/safety" className="text-helix-cyan">Safety Gate →</Link></span></p>
    )},
    { title: '9 · Evaluation', body: (
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        {[['Citation verif.', m.citation_verification_rate], ['Mol. validity', m.molecule_validity_rate], ['Self-correction', m.self_correction_rate], ['Real outputs', m.real_tool_output_count], ['Safety blocked', m.safety_blocked_count], ['Runtime', m.runtime_seconds ? `${m.runtime_seconds}s` : '—']].map(([l, v]) => (
          <div key={l as string} className="rounded-lg border border-line bg-bg-soft/40 p-3"><div className="text-[10px] uppercase text-slate-500">{l}</div><div className="text-xl font-semibold text-white">{v == null ? '—' : String(v)}</div></div>
        ))}
        <p className="col-span-full text-sm text-slate-500">Run the pipeline on slide 5 to populate live metrics.</p>
      </div>
    )},
    { title: '10 · Report Export', body: (
      <div>
        <button className="btn-primary" onClick={genKo} disabled={!!busy}><Icon name="FileText" size={16} /> {busy === 'ko' ? 'Generating…' : 'Generate Korean judge report'}</button>
        {koReady && <div className="mt-3"><Badge tone="green">KO report ready · {koReady}</Badge> <Link to="/reports" className="ml-2 text-sm text-helix-cyan">Open Reports →</Link></div>}
      </div>
    )},
    { title: '11 · Closing', body: (
      <p className="text-lg text-slate-300">AI does not replace expert review. It reduces the search space, documents evidence, and accelerates prioritization — with every step auditable and safety-gated.
        <span className="mt-3 block text-slate-500">본 시스템은 연구 의사결정 보조 도구이며, 최종 판단과 책임은 연구자에게 있습니다.</span></p>
    )},
  ]
  const s = slides[i]

  return (
    <div className="flex min-h-screen flex-col bg-bg grid-bg">
      <div className="flex items-center justify-between border-b border-line px-6 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-white"><span className="text-lg">🧬</span> HelixForge AI · Presentation</div>
        <div className="flex items-center gap-2">
          <Badge tone="cyan">{i + 1}/{slides.length}</Badge>
          <Link to="/" className="btn-ghost !py-1 text-xs"><Icon name="X" size={14} /> Exit</Link>
        </div>
      </div>
      <div className="flex flex-1 items-center justify-center px-8">
        <div className="w-full max-w-4xl">
          {err && <div className="mb-4"><ErrorNote error={err} /></div>}
          <h1 className="mb-6 text-4xl font-bold tracking-tight text-white">{s.title}</h1>
          <div className="min-h-[220px]">{s.body}</div>
        </div>
      </div>
      <div className="flex items-center justify-between border-t border-line px-6 py-4">
        <button className="btn-secondary" onClick={() => setI((v) => Math.max(0, v - 1))} disabled={i === 0}><Icon name="ChevronLeft" size={16} /> Prev</button>
        <div className="flex gap-1">{slides.map((slide, k) => <button key={slide.title} type="button" aria-label={`Go to slide ${k + 1}`} onClick={() => setI(k)} className={`h-2 w-2 rounded-full ${k === i ? 'bg-helix-cyan' : 'bg-line-bright'}`} />)}</div>
        <button className="btn-primary" onClick={() => setI((v) => Math.min(slides.length - 1, v + 1))} disabled={i === slides.length - 1}>Next <Icon name="ChevronRight" size={16} /></button>
      </div>
    </div>
  )
}
