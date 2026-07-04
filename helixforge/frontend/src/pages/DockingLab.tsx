import { useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, Field, PageHeader, Panel, SourceBadge, Spinner } from '@/components/ui'

export function DockingLab() {
  const [form, setForm] = useState({
    receptor_fixture: 'sample_receptor.pdbqt',
    ligand_fixture: 'sample_ligand.pdbqt',
    center: '0,0,0',
    box_size: '20,20,20',
    exhaustiveness: 8,
  })
  const [res, setRes] = useState<any | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')

  async function run() {
    setLoading(true); setErr(''); setRes(null)
    try {
      const body = {
        receptor_fixture: form.receptor_fixture,
        ligand_fixture: form.ligand_fixture,
        center: form.center.split(',').map(Number),
        box_size: form.box_size.split(',').map(Number),
        exhaustiveness: Number(form.exhaustiveness),
      }
      setRes(await api.vinaDock(body))
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }

  const set = (k: string, v: any) => setForm((f) => ({ ...f, [k]: v }))

  return (
    <div>
      <PageHeader
        icon={<Icon name="Magnet" size={22} />}
        title="Docking Lab"
        subtitle="Fixture-based AutoDock Vina integration. If the Vina engine is installed it runs a real dock on bundled fixtures; otherwise it reports CONFIGURED_BUT_NOT_RUN — never a fabricated score."
      />
      <div className="mb-4 rounded-lg border border-helix-amber/40 bg-helix-amber/10 px-3 py-2 text-xs text-helix-amber">
        <Icon name="Info" size={13} className="mr-1 inline" />
        Fixture-based docking integration; arbitrary receptor preparation (grid box definition, protonation, PDBQT conversion) is future work and requires expert setup.
      </div>
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <div className="section-title mb-3">Fixture docking job</div>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Receptor fixture"><input className="input" value={form.receptor_fixture} onChange={(e) => set('receptor_fixture', e.target.value)} /></Field>
            <Field label="Ligand fixture"><input className="input" value={form.ligand_fixture} onChange={(e) => set('ligand_fixture', e.target.value)} /></Field>
            <Field label="Center (x,y,z)"><input className="input" value={form.center} onChange={(e) => set('center', e.target.value)} /></Field>
            <Field label="Box size (x,y,z)"><input className="input" value={form.box_size} onChange={(e) => set('box_size', e.target.value)} /></Field>
            <Field label="Exhaustiveness"><input type="number" className="input" value={form.exhaustiveness} onChange={(e) => set('exhaustiveness', e.target.value)} /></Field>
          </div>
          <button className="btn-primary mt-4" onClick={run} disabled={loading}><Icon name="Play" size={15} /> Run fixture dock</button>
          <div className="mt-3 text-xs text-slate-500">Fixtures live in <span className="mono">backend/fixtures/vina/</span>. Set <span className="mono">VINA_BIN</span> in Settings to enable real docking.</div>
        </Panel>

        <Panel>
          <div className="section-title mb-3">Result</div>
          {loading && <Spinner label="Submitting docking job…" />}
          {!loading && !res && <Empty>Run a fixture dock to see the job status, score, and logs.</Empty>}
          {res && (
            <div>
              <div className="mb-3 flex flex-wrap items-center gap-2">
                <SourceBadge type={res.source_type} />
                <Badge tone={res.status === 'complete' ? 'green' : res.status === 'error' ? 'red' : 'amber'}>{res.status}</Badge>
                {res.job_id && <span className="font-mono text-[10px] text-slate-500">{res.job_id}</span>}
              </div>
              <div className="text-sm text-slate-300">{res.output_summary}</div>
              {res.scores?.length > 0 && (
                <div className="mt-3">
                  <div className="label">Binding scores (kcal/mol)</div>
                  <div className="flex flex-wrap gap-2">{res.scores.map((s: number, i: number) => <span key={i} className="chip border-helix-cyan/40 bg-helix-cyan/10 text-helix-cyan">{s}</span>)}</div>
                </div>
              )}
              {res.errors?.length > 0 && <div className="mt-3"><ErrorNote error={res.errors.join('; ')} /></div>}
              {res.logs?.length > 0 && (
                <pre className="mt-3 max-h-52 overflow-auto rounded-lg border border-line bg-black/40 p-3 font-mono text-[10px] text-slate-400">{res.logs.join('\n')}</pre>
              )}
            </div>
          )}
        </Panel>
      </div>
    </div>
  )
}
