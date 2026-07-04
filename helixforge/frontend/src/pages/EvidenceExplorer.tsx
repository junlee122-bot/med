import { useState } from 'react'
import { api } from '@/lib/api'
import type { PubMedItem, ClinicalTrialItem, Envelope } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Empty, ErrorNote, Field, PageHeader, Panel, SourceBadge, Spinner } from '@/components/ui'

type Tab = 'pubmed' | 'chembl' | 'trials'

export function EvidenceExplorer() {
  const [tab, setTab] = useState<Tab>('pubmed')
  return (
    <div>
      <PageHeader
        icon={<Icon name="BookOpen" size={22} />}
        title="Evidence Explorer"
        subtitle="Query real public sources — PubMed (NCBI E-utilities), ChEMBL web services, and ClinicalTrials.gov v2. Every result is labeled by provenance."
      />
      <div className="mb-5 flex gap-2">
        {([['pubmed', 'PubMed', 'BookText'], ['chembl', 'ChEMBL', 'Database'], ['trials', 'ClinicalTrials.gov', 'Stethoscope']] as const).map(([id, label, icon]) => (
          <button key={id} onClick={() => setTab(id)} className={tab === id ? 'btn-primary' : 'btn-secondary'}>
            <Icon name={icon} size={15} /> {label}
          </button>
        ))}
      </div>
      {tab === 'pubmed' && <PubMedPanel />}
      {tab === 'chembl' && <ChemblPanel />}
      {tab === 'trials' && <TrialsPanel />}
    </div>
  )
}

function ProvenanceBar({ env }: { env: Envelope }) {
  return (
    <div className="mb-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
      <SourceBadge type={env.source_type} />
      <span>{env.output_summary}</span>
      {env.retrieved_at && <span className="text-slate-500">· retrieved {new Date(env.retrieved_at).toLocaleTimeString()}</span>}
      {env.errors?.length > 0 && <span className="text-helix-red">· {env.errors.join('; ')}</span>}
    </div>
  )
}

function PubMedPanel() {
  const [q, setQ] = useState('EGFR non-small cell lung cancer resistance')
  const [n, setN] = useState(8)
  const [res, setRes] = useState<(Envelope & { items: PubMedItem[] }) | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  async function go() { setLoading(true); setErr(''); try { setRes(await api.pubmed(q, n)) } catch (e: any) { setErr(e.message) } finally { setLoading(false) } }
  return (
    <Panel>
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[280px] flex-1"><Field label="PubMed query"><input className="input" value={q} onChange={(e) => setQ(e.target.value)} /></Field></div>
        <div className="w-28"><Field label="Max results"><input type="number" className="input" value={n} onChange={(e) => setN(+e.target.value)} /></Field></div>
        <button className="btn-primary" onClick={go} disabled={loading}><Icon name="Search" size={15} /> Search</button>
      </div>
      <div className="mt-4">
        {loading && <Spinner label="Querying NCBI E-utilities…" />}
        {err && <ErrorNote error={err} />}
        {res && (<><ProvenanceBar env={res} />
          {res.items.length === 0 ? <Empty>No records.</Empty> : (
            <div className="space-y-3">
              {res.items.map((it) => (
                <div key={it.pmid} className="rounded-lg border border-line bg-bg-soft/40 p-3">
                  <a href={it.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-slate-100 hover:text-helix-cyan">{it.title}</a>
                  <div className="mt-1 text-xs text-slate-400">{it.journal} · {it.year} · PMID {it.pmid}</div>
                  {it.abstract && <div className="mt-1 line-clamp-3 text-xs text-slate-500">{it.abstract}</div>}
                </div>
              ))}
            </div>
          )}</>)}
      </div>
    </Panel>
  )
}

function ChemblPanel() {
  const [q, setQ] = useState('EGFR')
  const [targets, setTargets] = useState<(Envelope & { items: any[] }) | null>(null)
  const [acts, setActs] = useState<(Envelope & { items: any[] }) | null>(null)
  const [loading, setLoading] = useState<'t' | 'a' | null>(null)
  const [err, setErr] = useState('')
  async function searchT() { setLoading('t'); setErr(''); setActs(null); try { setTargets(await api.chemblTargets(q, 8)) } catch (e: any) { setErr(e.message) } finally { setLoading(null) } }
  async function loadActs(id: string) { setLoading('a'); setErr(''); try { setActs(await api.chemblActivities(id, 'IC50', 25)) } catch (e: any) { setErr(e.message) } finally { setLoading(null) } }
  return (
    <Panel>
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[280px] flex-1"><Field label="ChEMBL target query"><input className="input" value={q} onChange={(e) => setQ(e.target.value)} /></Field></div>
        <button className="btn-primary" onClick={searchT} disabled={!!loading}><Icon name="Search" size={15} /> Search targets</button>
      </div>
      <div className="mt-4">
        {loading === 't' && <Spinner label="Querying ChEMBL targets…" />}
        {err && <ErrorNote error={err} />}
        {targets && (<><ProvenanceBar env={targets} />
          <div className="space-y-2">
            {targets.items.map((t, i) => (
              <div key={i} className="flex items-center justify-between rounded-lg border border-line bg-bg-soft/40 p-3">
                <div>
                  <div className="text-sm font-medium text-slate-100">{t.pref_name || t.target_chembl_id}</div>
                  <div className="text-xs text-slate-400">{t.target_chembl_id} · {t.organism || '—'} · {t.target_type || ''}</div>
                </div>
                {t.target_chembl_id && <button className="btn-secondary" onClick={() => loadActs(t.target_chembl_id)} disabled={!!loading}><Icon name="Activity" size={14} /> Activities</button>}
              </div>
            ))}
          </div></>)}
        {loading === 'a' && <div className="mt-3"><Spinner label="Loading ChEMBL activities…" /></div>}
        {acts && (<div className="mt-4"><ProvenanceBar env={acts} />
          <div className="overflow-auto rounded-lg border border-line">
            <table className="w-full text-left text-xs">
              <thead className="bg-bg-soft text-slate-400"><tr><th className="p-2">Molecule</th><th className="p-2">Type</th><th className="p-2">Value</th><th className="p-2">pChEMBL</th><th className="p-2">SMILES</th></tr></thead>
              <tbody>
                {acts.items.slice(0, 25).map((a, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="p-2 text-slate-300">{a.molecule_chembl_id}</td>
                    <td className="p-2 text-slate-400">{a.activity_type || a.standard_type}</td>
                    <td className="p-2 text-slate-400">{a.standard_value} {a.standard_units}</td>
                    <td className="p-2 text-slate-400">{a.pchembl_value ?? '—'}</td>
                    <td className="p-2 font-mono text-[10px] text-slate-500">{(a.canonical_smiles || '').slice(0, 28) || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div></div>)}
      </div>
    </Panel>
  )
}

function TrialsPanel() {
  const [cond, setCond] = useState('non-small cell lung cancer')
  const [q, setQ] = useState('EGFR')
  const [res, setRes] = useState<(Envelope & { items: ClinicalTrialItem[] }) | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState('')
  async function go() { setLoading(true); setErr(''); try { setRes(await api.clinicaltrials(cond, q, 8)) } catch (e: any) { setErr(e.message) } finally { setLoading(false) } }
  return (
    <Panel>
      <div className="flex flex-wrap items-end gap-3">
        <div className="min-w-[220px] flex-1"><Field label="Condition"><input className="input" value={cond} onChange={(e) => setCond(e.target.value)} /></Field></div>
        <div className="min-w-[160px] flex-1"><Field label="Query term"><input className="input" value={q} onChange={(e) => setQ(e.target.value)} /></Field></div>
        <button className="btn-primary" onClick={go} disabled={loading}><Icon name="Search" size={15} /> Search trials</button>
      </div>
      <div className="mt-4">
        {loading && <Spinner label="Querying ClinicalTrials.gov v2…" />}
        {err && <ErrorNote error={err} />}
        {res && (<><ProvenanceBar env={res} />
          {res.items.length === 0 ? <Empty>No trials.</Empty> : (
            <div className="space-y-3">
              {res.items.map((it) => (
                <div key={it.nct_id} className="rounded-lg border border-line bg-bg-soft/40 p-3">
                  <div className="flex items-start justify-between gap-3">
                    <a href={it.url} target="_blank" rel="noreferrer" className="text-sm font-medium text-slate-100 hover:text-helix-cyan">{it.brief_title}</a>
                    <span className="chip border-line-bright bg-bg-hover text-slate-300 whitespace-nowrap">{it.phase || 'N/A'}</span>
                  </div>
                  <div className="mt-1 text-xs text-slate-400">{it.nct_id} · {it.status}</div>
                  {it.interventions?.length > 0 && <div className="mt-1 text-xs text-slate-500">Interventions: {it.interventions.slice(0, 4).join(', ')}</div>}
                </div>
              ))}
            </div>
          )}</>)}
      </div>
    </Panel>
  )
}
