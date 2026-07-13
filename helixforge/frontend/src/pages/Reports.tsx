import { useEffect, useState } from 'react'
import { api, getRememberedRunId, HUMAN_RESPONSIBILITY, rememberRunId } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url; a.download = name; a.click()
  URL.revokeObjectURL(url)
}

export function Reports() {
  const [runId, setRunId] = useState(getRememberedRunId)
  const [reports, setReports] = useState<any[]>([])
  const [active, setActive] = useState<{ report_id: string; title: string; markdown: string; json_audit: any } | null>(null)
  const [loading, setLoading] = useState<string | null>(null)
  const [err, setErr] = useState('')

  async function refresh() {
    try { const r = await api.listReports(undefined, runId || undefined); setReports(r.reports || []) } catch (e: any) { setReports([]); setErr(e.message) }
  }
  useEffect(() => {
    setActive(null)
    setReports([])
    refresh()
  }, [runId])

  async function open(id: string) {
    setLoading('open'); setErr('')
    try { setActive(await api.getReport(id)) } catch (e: any) { setErr(e.message) } finally { setLoading(null) }
  }

  async function generate() {
    setLoading('gen'); setErr(''); setActive(null)
    try {
      const run = await api.runPipeline({ condition: 'non-small cell lung cancer', target_query: 'EGFR', max_results: 5 })
      rememberRunId(run.run_id); setRunId(run.run_id)
      const rep = await api.reportGenerate({
        project_id: run.project_id,
        workflow_run_id: run.run_id,
        title: 'HelixForge AI — Candidate Package Report',
      })
      setActive(rep as any)
      const refreshed = await api.listReports(undefined, run.run_id)
      setReports(refreshed.reports || [])
    } catch (e: any) { setErr(e.message) } finally { setLoading(null) }
  }

  return (
    <div>
      <PageHeader
        icon={<Icon name="FileText" size={22} />}
        title="Reports"
        subtitle="Generate a Markdown report from real tool runs — evidence, molecule descriptors, TDC dataset usage, Vina/REINVENT status, safety audit, and the human-responsibility statement. Export Markdown or JSON."
        actions={<button className="btn-primary" onClick={generate} disabled={!!loading}><Icon name="Sparkles" size={15} /> Run pipeline + build report</button>}
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading === 'gen' && <div className="mb-4"><Spinner label="Running real pipeline and assembling report…" /></div>}

      <div className="grid gap-4 lg:grid-cols-[320px_1fr]">
        <Panel>
          <div className="section-title mb-3">Generated reports · {reports.length}</div>
          {reports.length === 0 ? <Empty>No reports yet. Run the pipeline to build one from real tool runs.</Empty> : (
            <div className="space-y-2">
              {reports.map((r) => (
                <button key={r.report_id || r.id} onClick={() => open(r.report_id || r.id)} className={`w-full rounded-lg border p-3 text-left ${active?.report_id === (r.report_id || r.id) ? 'border-helix-cyan/50 bg-helix-cyan/5' : 'border-line bg-bg-soft/40 card-hover'}`}>
                  <div className="text-sm font-medium text-slate-100">{r.title || 'Report'}</div>
                  <div className="mt-1 text-[11px] text-slate-500">{r.report_id || r.id} · {r.created_at ? new Date(r.created_at).toLocaleString() : ''}</div>
                </button>
              ))}
            </div>
          )}
        </Panel>

        <Panel>
          {loading === 'open' && <Spinner label="Loading report…" />}
          {!active && loading !== 'open' && <Empty>Select or generate a report to preview and export it.</Empty>}
          {active && (
            <div>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2"><Icon name="FileText" size={16} className="text-helix-cyan" /><span className="font-medium text-slate-100">{active.title}</span><Badge tone="cyan">{active.report_id}</Badge></div>
                <div className="flex gap-2">
                  <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => download(`${active.report_id}.md`, active.markdown, 'text/markdown')}><Icon name="Download" size={13} /> .md</button>
                  <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => download(`${active.report_id}.json`, JSON.stringify(active.json_audit, null, 2), 'application/json')}><Icon name="Braces" size={13} /> JSON</button>
                  <button className="btn-secondary !px-2 !py-1 text-xs" onClick={() => window.print()}><Icon name="Printer" size={13} /> Print</button>
                </div>
              </div>
              <pre className="max-h-[560px] overflow-auto whitespace-pre-wrap rounded-lg border border-line bg-black/30 p-4 font-mono text-[11px] leading-relaxed text-slate-300">{active.markdown}</pre>
            </div>
          )}
        </Panel>
      </div>
      <div className="mt-4"><Disclaimer text={HUMAN_RESPONSIBILITY} /></div>
    </div>
  )
}
