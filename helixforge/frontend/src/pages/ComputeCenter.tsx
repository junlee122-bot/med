import { useEffect, useState } from 'react'
import { api, SOURCE_META } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner, StatCard } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

const PROFILE_TONE: Record<string, string> = {
  CPU_ONLY: 'cyan', CPU_WITH_OPTIONAL_LOCAL_TOOLS: 'green', REMOTE_GPU_READY: 'amber',
  REMOTE_GPU_ENABLED: 'green', RECORDED_GPU_REPLAY: 'violet', COMPUTE_DEGRADED: 'red',
}

function SBadge({ type }: { type?: string }) {
  if (!type) return null
  const m = SOURCE_META[type] || { label: type, tone: 'slate' }
  return <Badge tone={m.tone}>{m.label}</Badge>
}

export function ComputeCenter() {
  const [cap, setCap] = useState<any>(null)
  const [providers, setProviders] = useState<any>(null)
  const [costs, setCosts] = useState<any>(null)
  const [contracts, setContracts] = useState<any>(null)
  const [security, setSecurity] = useState<any>(null)
  const [demo, setDemo] = useState<any>(null)
  const [dryRun, setDryRun] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')

  async function load(mode: 'local' | 'deep' = 'local') {
    setLoading(true); setErr('')
    try {
      const [c, p, co, wc, se] = await Promise.all([
        api.computeCapabilities(mode), api.computeProviders(), api.computeCosts(),
        api.computeWorkerContracts(), api.computeSecurityAudit(),
      ])
      setCap(c); setProviders(p); setCosts(co); setContracts(wc); setSecurity(se)
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function runDemo() {
    setBusy('demo'); setErr('')
    try { setDemo(await api.cpuScientificDemo('EGFR')) } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }
  async function runDryRun() {
    setBusy('dry'); setErr('')
    try { setDryRun(await api.gpuReadinessDryRun('EGFR')) } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="Cpu" size={22} />}
        title="Compute Center"
        subtitle="CPU-first compute with an optional, safety-gated external-GPU gateway. CPU-only is a complete scientific mode; missing GPU is never an error."
        actions={<div className="flex gap-2">
          <button className="btn-secondary" onClick={() => load('local')} disabled={loading}><Icon name="RefreshCw" size={14} /> Refresh</button>
          <button className="btn-secondary" onClick={() => load('deep')} disabled={loading}><Icon name="Search" size={14} /> Deep check</button>
        </div>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Detecting compute capabilities…" /> : !cap ? <Empty>No data.</Empty> : (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-4">
            <StatCard label="Compute profile" value={<Badge tone={PROFILE_TONE[cap.profile] || 'slate'}>{cap.profile}</Badge>}
              sub={`recommended: ${cap.recommended_mode}`} tone="cyan" />
            <StatCard label="Logical cores" value={cap.cpu?.logical_cores ?? '—'}
              sub={cap.cpu?.memory_gb_estimate ? `${cap.cpu.memory_gb_estimate} GB` : ''} />
            <StatCard label="Local GPU" value={cap.gpu_present_locally ? 'present' : 'none'}
              sub={cap.torch?.available ? `torch cuda: ${cap.torch.cuda_available}` : 'torch: n/a'}
              tone={cap.gpu_present_locally ? 'green' : 'slate'} />
            <StatCard label="Remote GPU" value={cap.remote_gpu?.configured ? 'configured' : 'not configured'}
              sub={`recorded artifacts: ${cap.recorded_gpu_artifacts?.count ?? 0}`} tone="amber" />
          </div>

          {cap.warnings?.length > 0 && (
            <Panel><div className="section-title mb-1">Warnings</div>
              {cap.warnings.map((w: string, i: number) => <div key={i} className="text-xs text-helix-amber">⚠ {w}</div>)}
            </Panel>
          )}

          {/* Local tools */}
          <Panel>
            <div className="section-title mb-2">Local scientific tools</div>
            <div className="grid gap-2 sm:grid-cols-3">
              {Object.entries(cap.local_tools || {}).map(([name, t]: any) => (
                <div key={name} className="flex items-center gap-2 rounded border border-white/5 px-2 py-1 text-xs">
                  <Icon name={t.available ? 'CheckCircle2' : 'MinusCircle'} size={14}
                    className={t.available ? 'text-brand-300' : 'text-slate-500'} />
                  <span className="text-slate-200">{name}</span>
                  {t.status && !t.available && <Badge tone="amber" className="ml-auto">{t.status}</Badge>}
                  {t.version && <span className="ml-auto text-slate-500">{t.version}</span>}
                </div>
              ))}
            </div>
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            {/* Providers */}
            <Panel>
              <div className="section-title mb-2">GPU Gateway — providers</div>
              <div className="text-[11px] text-slate-500 mb-2">Live GPU calls enabled: <Badge tone={providers?.live_gpu_calls_enabled ? 'green' : 'slate'}>{String(providers?.live_gpu_calls_enabled)}</Badge></div>
              {(providers?.providers || []).map((p: any) => (
                <div key={p.id} className="flex items-center gap-2 border-t border-white/5 py-1 text-xs">
                  <span className="flex-1 text-slate-300">{p.display_name}</span>
                  <Badge tone={p.enabled ? 'green' : 'slate'}>{p.enabled ? 'enabled' : 'disabled'}</Badge>
                  <span className="text-slate-500">{p.credential_status}</span>
                </div>
              ))}
              <div className="mt-2 text-[11px] text-slate-500">{providers?.note}</div>
            </Panel>

            {/* Cost + security */}
            <Panel>
              <div className="section-title mb-2">Cost guard & security</div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>Run cap: <span className="text-slate-200">${costs?.run_cap_usd}</span></div>
                <div>Daily cap: <span className="text-slate-200">${costs?.daily_cap_usd}</span></div>
                <div>Spent today: <span className="text-slate-200">${costs?.spent_today_usd}</span></div>
                <div>Replay cost: <span className="text-slate-200">${costs?.replay_cost_usd}</span></div>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <span className="text-xs text-slate-400">Security audit:</span>
                <Badge tone={security?.ok ? 'green' : 'red'}>{security?.ok ? 'PASS' : 'REVIEW'}</Badge>
                <span className="text-[11px] text-slate-500">{security?.note}</span>
              </div>
              <div className="mt-1 text-[11px] text-slate-500">{costs?.disclaimer}</div>
            </Panel>
          </div>

          {/* Demos */}
          <Panel>
            <div className="mb-2 flex items-center justify-between">
              <div className="section-title">One-click demos (no GPU, no key, no paid job)</div>
              <div className="flex gap-2">
                <button className="btn-primary" onClick={runDemo} disabled={busy !== ''}>
                  {busy === 'demo' ? <Icon name="Loader2" size={14} className="animate-spin" /> : <Icon name="Play" size={14} />} CPU Scientific Demo
                </button>
                <button className="btn-secondary" onClick={runDryRun} disabled={busy !== ''}>
                  {busy === 'dry' ? <Icon name="Loader2" size={14} className="animate-spin" /> : <Icon name="Rocket" size={14} />} GPU Dry Run
                </button>
              </div>
            </div>
            {demo && (
              <div className="rounded-lg border border-white/8 p-2 text-xs mb-2">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-slate-200 font-medium">CPU demo {demo.demo_id}</span>
                  <SBadge type={demo.source_type} />
                  <Badge tone="green">GPU used: {String(demo.gpu_used)}</Badge>
                  <Badge tone={demo.gpu_escalation?.submitted ? 'red' : 'green'}>submitted: {String(demo.gpu_escalation?.submitted)}</Badge>
                </div>
                <div className="text-slate-400">CPU model: {demo.cpu_model_status} · release: {demo.release_status}</div>
                <details className="mt-1"><summary className="cursor-pointer text-slate-500">report</summary>
                  <pre className="mt-1 max-h-64 overflow-auto whitespace-pre-wrap text-[11px] text-slate-400">{demo.report_markdown}</pre>
                </details>
              </div>
            )}
            {dryRun && (
              <div className="rounded-lg border border-white/8 p-2 text-xs">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-slate-200 font-medium">GPU dry run {dryRun.run_id}</span>
                  <SBadge type={dryRun.source_type} />
                  <Badge tone="green">submissions: {dryRun.provider_submissions}</Badge>
                  <Badge tone="amber">approval: {dryRun.approval_status}</Badge>
                </div>
                <div className="text-slate-400">{dryRun.banner}</div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {dryRun.job_specs?.map((s: any) => (
                    <Badge key={s.job_type} tone={s.validated ? 'cyan' : 'red'}>{s.job_type}: ${s.estimated_cost_usd ?? '—'}</Badge>
                  ))}
                </div>
              </div>
            )}
          </Panel>

          {/* Worker contracts */}
          <Panel>
            <div className="section-title mb-2">GPU worker contracts <SBadge type={contracts?.source_type} /></div>
            <div className="grid gap-2 sm:grid-cols-2">
              {(contracts?.contracts || []).map((c: any) => (
                <div key={c.job_type} className="rounded border border-white/5 p-2 text-xs">
                  <div className="flex items-center gap-2"><span className="text-slate-200">{c.job_type}</span>
                    <Badge tone="amber" className="ml-auto">{c.status}</Badge></div>
                  <div className="mt-0.5 text-slate-500">CPU substitute: {c.cpu_substitute}</div>
                </div>
              ))}
            </div>
          </Panel>

          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}
