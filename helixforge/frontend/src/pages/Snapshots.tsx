import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, Field, PageHeader, Panel, Spinner } from '@/components/ui'
import { AgentRunCard, MetricTile } from '@/components/agentic'

export function Snapshots() {
  const [snaps, setSnaps] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState('')
  const [err, setErr] = useState('')
  const [name, setName] = useState('EGFR/NSCLC recorded run')
  const [replay, setReplay] = useState<any | null>(null)

  async function load() {
    setLoading(true)
    try { setSnaps((await api.listSnapshots()).snapshots) } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  async function captureNew() {
    setBusy('capture'); setErr('')
    try {
      const run = await api.runAgenticPipeline({ target_query: 'EGFR', max_results: 4, create_reinvent_config: false, error_injections: {} })
      await api.createSnapshot(run.run_id, name)
      await load()
    } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }
  async function doReplay(id: string) {
    setBusy(id); setErr(''); setReplay(null)
    try { setReplay(await api.replaySnapshot(id)) } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }
  async function doExport(id: string) {
    setBusy(id)
    try {
      const b = await api.exportSnapshot(id)
      const blob = new Blob([JSON.stringify(b, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob); const a = document.createElement('a')
      a.href = url; a.download = `${id}.json`; a.click(); URL.revokeObjectURL(url)
    } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }
  async function doDelete(id: string) {
    setBusy(id)
    try { await api.deleteSnapshot(id); await load() } catch (e: any) { setErr(e.message) } finally { setBusy('') }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="DatabaseZap" size={22} />}
        title="Snapshots · Record / Replay"
        subtitle="Capture a real run, then replay it with NO live API calls — labeled RECORDED_REAL_TOOL_OUTPUT. The demo-day safety net for flaky networks. Replayed reports disclose original + replay timestamps."
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}

      <Panel className="mb-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[260px] flex-1"><Field label="Snapshot name"><input className="input" value={name} onChange={(e) => setName(e.target.value)} /></Field></div>
          <button className="btn-primary" onClick={captureNew} disabled={!!busy}>
            <Icon name="Camera" size={15} /> {busy === 'capture' ? 'Running + capturing…' : 'Run pipeline + capture snapshot'}
          </button>
        </div>
      </Panel>

      {loading ? <Spinner label="Loading snapshots…" /> : (
        <div className="grid gap-4 lg:grid-cols-[1fr_400px]">
          <Panel>
            <div className="mb-3 section-title">Snapshots · {snaps.length}</div>
            {snaps.length === 0 ? <Empty>No snapshots yet. Capture one, or ship the committed built-in snapshot.</Empty> : (
              <div className="space-y-2">
                {snaps.map((s) => (
                  <div key={s.id} className="rounded-lg border border-line bg-bg-soft/40 p-3">
                    <div className="flex items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2 text-sm font-medium text-slate-100">
                          {s.name} {s.is_builtin && <Badge tone="cyan">built-in</Badge>}
                        </div>
                        <div className="mt-0.5 font-mono text-[10px] text-slate-500">{s.id} · {s.checksum?.slice(0, 22)}</div>
                        <div className="mt-0.5 text-[11px] text-slate-400">{s.condition} · {s.target_query} · captured {s.created_at ? new Date(s.created_at).toLocaleString() : '—'}</div>
                        <div className="mt-1 flex flex-wrap gap-1 text-[10px] text-slate-500">
                          {Object.entries(s.tool_output_counts || {}).map(([k, v]) => <span key={k} className="chip border-line-bright bg-bg-hover">{k}: {String(v)}</span>)}
                        </div>
                      </div>
                      <div className="flex flex-shrink-0 flex-col gap-1">
                        <button className="btn-primary !px-2 !py-1 text-xs" onClick={() => doReplay(s.id)} disabled={!!busy}><Icon name="Play" size={12} /> Replay</button>
                        <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => doExport(s.id)} disabled={!!busy}><Icon name="Download" size={12} /> Export</button>
                        {!s.is_builtin && <button className="btn-ghost !px-2 !py-1 text-xs" onClick={() => doDelete(s.id)} disabled={!!busy}><Icon name="Trash2" size={12} /></button>}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Panel>

          <Panel>
            <div className="mb-3 section-title">Replay result</div>
            {busy && busy !== 'capture' && <Spinner label="Replaying recorded run (no live calls)…" />}
            {!replay && !busy && <Empty>Replay a snapshot to reconstruct the run from recorded real outputs.</Empty>}
            {replay && (
              <div>
                <div className="mb-2 rounded-lg border border-helix-cyan/40 bg-helix-cyan/10 px-3 py-2 text-xs text-helix-cyan">
                  <Icon name="Info" size={12} className="mr-1 inline" />{replay.warning}
                </div>
                <div className="mb-3 grid grid-cols-2 gap-2">
                  <MetricTile label="Mode" value="RECORDED" tone="green" />
                  <MetricTile label="Agents" value={replay.agent_runs?.length ?? 0} />
                  <MetricTile label="Original run" value={<span className="text-xs">{replay.original_run_id?.slice(0, 14)}</span>} />
                  <MetricTile label="Retrieved" value={<span className="text-[10px]">{replay.original_retrieved_at ? new Date(replay.original_retrieved_at).toLocaleDateString() : '—'}</span>} />
                </div>
                <div className="max-h-[420px] space-y-2 overflow-auto pr-1">
                  {(replay.agent_runs || []).slice(0, 8).map((a: any) => <AgentRunCard key={a.id} run={a} />)}
                </div>
              </div>
            )}
          </Panel>
        </div>
      )}
    </div>
  )
}
