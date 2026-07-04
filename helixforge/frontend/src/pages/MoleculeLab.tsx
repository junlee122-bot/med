import { useState } from 'react'
import { api } from '@/lib/api'
import type { RDKitResponse } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Empty, ErrorNote, Field, PageHeader, Panel, SourceBadge, Spinner, StatCard } from '@/components/ui'

interface Candidate { smiles: string; source: string; res?: RDKitResponse; safety?: string }

const SEEDS = ['CC(=O)Oc1ccccc1C(=O)O', 'CN1C=NC2=C1C(=O)N(C)C(=O)N2C', 'COc1cc2ncnc(Nc3ccc(F)cc3)c2cc1OC', 'CC(C)(C']

export function MoleculeLab() {
  const [smiles, setSmiles] = useState('COc1cc2ncnc(Nc3ccc(F)cc3)c2cc1OC')
  const [ref, setRef] = useState('CC(=O)Oc1ccccc1C(=O)O')
  const [single, setSingle] = useState<RDKitResponse | null>(null)
  const [sim, setSim] = useState<RDKitResponse | null>(null)
  const [candidates, setCandidates] = useState<Candidate[]>([])
  const [loading, setLoading] = useState<string | null>(null)
  const [err, setErr] = useState('')
  const [chemblId, setChemblId] = useState('CHEMBL203')

  async function validate() { setLoading('v'); setErr(''); try { setSingle(await api.rdkitDescriptors(smiles)) } catch (e: any) { setErr(e.message) } finally { setLoading(null) } }
  async function similarity() { setLoading('s'); setErr(''); try { setSim(await api.rdkitSimilarity(smiles, ref)) } catch (e: any) { setErr(e.message) } finally { setLoading(null) } }

  async function screenSeeds() {
    setLoading('seeds'); setErr('')
    try {
      const rows: Candidate[] = []
      for (const s of SEEDS) {
        const res = await api.rdkitDescriptors(s)
        let safety = 'PASS'
        try { const sc = await api.safetyScreen({ smiles: s, label: s }); safety = sc.status || sc.safety_status || 'PASS' } catch {}
        rows.push({ smiles: s, source: 'seed', res, safety })
      }
      setCandidates(rows)
    } catch (e: any) { setErr(e.message) } finally { setLoading(null) }
  }

  async function loadFromChembl() {
    setLoading('chembl'); setErr('')
    try {
      const acts = await api.chemblActivities(chemblId, 'IC50', 15)
      const seen = new Set<string>()
      const rows: Candidate[] = []
      for (const a of acts.items) {
        const s = a.canonical_smiles
        if (!s || seen.has(s)) continue
        seen.add(s)
        const res = await api.rdkitValidate(s)
        rows.push({ smiles: s, source: `ChEMBL ${a.molecule_chembl_id}`, res })
        if (rows.length >= 8) break
      }
      setCandidates((prev) => [...rows, ...prev])
    } catch (e: any) { setErr(e.message) } finally { setLoading(null) }
  }

  const d = single?.descriptors
  return (
    <div>
      <PageHeader
        icon={<Icon name="Atom" size={22} />}
        title="Molecule Lab"
        subtitle="Validate SMILES and compute descriptors with real RDKit, compare similarity, and pull real molecule structures from ChEMBL activities. Safety-screened; no synthesis routes."
      />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}

      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <div className="section-title mb-3">RDKit validation & descriptors</div>
          <Field label="SMILES"><input className="input font-mono text-xs" value={smiles} onChange={(e) => setSmiles(e.target.value)} /></Field>
          <div className="mt-3 flex gap-2">
            <button className="btn-primary" onClick={validate} disabled={!!loading}><Icon name="CheckCircle2" size={15} /> Validate & compute</button>
            <button className="btn-secondary" onClick={screenSeeds} disabled={!!loading}><Icon name="Rows3" size={15} /> Screen seed set</button>
          </div>
          {loading === 'v' && <div className="mt-3"><Spinner label="Running RDKit…" /></div>}
          {single && (
            <div className="mt-4">
              <div className="mb-3 flex items-center gap-2"><SourceBadge type={single.source_type} />
                <Badge tone={single.valid ? 'green' : 'red'}>{single.valid ? 'Valid' : 'Invalid'}</Badge>
                {single.canonical_smiles && <span className="font-mono text-[10px] text-slate-500">{single.canonical_smiles}</span>}
              </div>
              {single.errors?.length > 0 && <ErrorNote error={single.errors.join('; ')} />}
              {d && (
                <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                  <StatCard label="MW" value={d.mol_weight} />
                  <StatCard label="logP" value={d.logp} />
                  <StatCard label="TPSA" value={d.tpsa} />
                  <StatCard label="QED" value={d.qed} tone={d.qed > 0.6 ? 'green' : 'amber'} />
                  <StatCard label="HBD/HBA" value={`${d.hbd}/${d.hba}`} />
                  <StatCard label="Rot. bonds" value={d.rotatable_bonds} />
                  <StatCard label="Rings" value={d.ring_count} />
                  <StatCard label="Lipinski" value={d.lipinski_pass ? 'Pass' : `${d.lipinski_violations} viol`} tone={d.lipinski_pass ? 'green' : 'amber'} />
                </div>
              )}
            </div>
          )}
        </Panel>

        <Panel>
          <div className="section-title mb-3">Tanimoto similarity (Morgan FP)</div>
          <Field label="Query SMILES"><input className="input font-mono text-xs" value={smiles} onChange={(e) => setSmiles(e.target.value)} /></Field>
          <div className="mt-3"><Field label="Reference SMILES"><input className="input font-mono text-xs" value={ref} onChange={(e) => setRef(e.target.value)} /></Field></div>
          <button className="btn-primary mt-3" onClick={similarity} disabled={!!loading}><Icon name="GitCompare" size={15} /> Compute similarity</button>
          {loading === 's' && <div className="mt-3"><Spinner label="Computing fingerprint similarity…" /></div>}
          {sim && (
            <div className="mt-4 flex items-center gap-3">
              <SourceBadge type={sim.source_type} />
              {sim.similarity != null ? <div className="kpi text-helix-cyan">{(sim.similarity * 100).toFixed(1)}%</div> : <span className="text-sm text-slate-400">n/a</span>}
              {sim.errors?.length > 0 && <span className="text-xs text-helix-red">{sim.errors.join('; ')}</span>}
            </div>
          )}
          <div className="mt-6 section-title mb-2">Load candidates from ChEMBL</div>
          <div className="flex items-end gap-2">
            <div className="flex-1"><Field label="Target ChEMBL ID"><input className="input" value={chemblId} onChange={(e) => setChemblId(e.target.value)} /></Field></div>
            <button className="btn-secondary" onClick={loadFromChembl} disabled={!!loading}><Icon name="Download" size={14} /> Load structures</button>
          </div>
          {loading === 'chembl' && <div className="mt-3"><Spinner label="Fetching ChEMBL structures + RDKit validation…" /></div>}
        </Panel>
      </div>

      <Panel className="mt-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="section-title">Candidate table · {candidates.length}</div>
          {loading === 'seeds' && <Spinner label="Screening…" />}
        </div>
        {candidates.length === 0 ? (
          <Empty>Screen the seed set or load structures from ChEMBL to populate real RDKit-validated candidates.</Empty>
        ) : (
          <div className="overflow-auto rounded-lg border border-line">
            <table className="w-full text-left text-xs">
              <thead className="bg-bg-soft text-slate-400"><tr><th className="p-2">Source</th><th className="p-2">SMILES</th><th className="p-2">Valid</th><th className="p-2">MW</th><th className="p-2">QED</th><th className="p-2">Lipinski</th><th className="p-2">Safety</th><th className="p-2">Provenance</th></tr></thead>
              <tbody>
                {candidates.map((c, i) => (
                  <tr key={i} className="border-t border-line">
                    <td className="p-2 text-slate-400">{c.source}</td>
                    <td className="p-2 font-mono text-[10px] text-slate-500">{c.smiles.slice(0, 30)}</td>
                    <td className="p-2">{c.res?.valid ? <Badge tone="green">valid</Badge> : <Badge tone="red">invalid</Badge>}</td>
                    <td className="p-2 text-slate-400">{c.res?.descriptors?.mol_weight ?? '—'}</td>
                    <td className="p-2 text-slate-400">{c.res?.descriptors?.qed ?? '—'}</td>
                    <td className="p-2 text-slate-400">{c.res?.descriptors ? (c.res.descriptors.lipinski_pass ? 'pass' : `${c.res.descriptors.lipinski_violations} viol`) : '—'}</td>
                    <td className="p-2">{c.safety ? <Badge tone={c.safety === 'PASS' ? 'green' : c.safety === 'BLOCKED' ? 'red' : 'amber'}>{c.safety}</Badge> : '—'}</td>
                    <td className="p-2">{c.res && <SourceBadge type={c.res.source_type} />}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </div>
  )
}
