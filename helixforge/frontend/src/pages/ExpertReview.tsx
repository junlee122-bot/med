import { useEffect, useState } from 'react'
import { api } from '@/lib/api'
import { Icon } from '@/components/Icon'
import { Badge, Disclaimer, Empty, ErrorNote, PageHeader, Panel, Spinner } from '@/components/ui'
import { HUMAN_RESPONSIBILITY } from '@/lib/api'

const RISK_TONE: Record<string, string> = { high: 'red', medium: 'amber', low: 'slate' }
const DECISIONS = ['APPROVE_FOR_PROPOSAL', 'APPROVE_FOR_DEMO_ONLY', 'NEEDS_MORE_EVIDENCE', 'REJECT', 'ESCALATE', 'NOT_APPLICABLE']

export function ExpertReview() {
  const [items, setItems] = useState<any[]>([])
  const [roles, setRoles] = useState<string[]>([])
  const [roleFilter, setRoleFilter] = useState('all')
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')

  async function load() {
    setLoading(true); setErr('')
    try {
      const res = await api.expertReviewItems()
      setItems(res.items || []); setRoles(res.roles || [])
    } catch (e: any) { setErr(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])
  async function generate() {
    setLoading(true)
    try { await api.expertReviewGenerate(); await load() } catch (e: any) { setErr(e.message); setLoading(false) }
  }
  async function decide(id: string, decision: string) {
    try { await api.expertReviewDecision(id, { decision, reviewer_role: 'reviewer', reviewer_name: 'expert' }); await load() }
    catch (e: any) { setErr(e.message) }
  }

  const shown = roleFilter === 'all' ? items : items.filter((i) => i.recommended_role === roleFilter || (i.required_roles || []).includes(roleFilter))
  const pending = items.filter((i) => i.review_status === 'PENDING').length
  const highPending = items.filter((i) => i.risk_level === 'high' && i.review_status === 'PENDING').length

  return (
    <div>
      <PageHeader icon={<Icon name="Users" size={22} />} title="Expert Review Board"
        subtitle="Role-based sign-off queue. High-risk items (safety, clinical, regulatory, final report) must be reviewed before the run is submission-ready."
        actions={<button className="btn-primary" onClick={generate} disabled={loading}><Icon name="ListPlus" size={14} /> Generate from latest run</button>} />
      {err && <div className="mb-4"><ErrorNote error={err} /></div>}
      {loading ? <Spinner label="Loading review queue…" /> : (
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <Badge tone={highPending ? 'red' : 'green'}>{highPending} high-risk pending</Badge>
            <Badge tone="amber">{pending} total pending</Badge>
            <span className="mx-1 text-slate-600">|</span>
            <button className={`badge ${roleFilter === 'all' ? 'ring-1 ring-brand-400' : ''}`} onClick={() => setRoleFilter('all')}>all roles</button>
            {roles.map((r) => <button key={r} className={`badge ${roleFilter === r ? 'ring-1 ring-brand-400' : ''}`} onClick={() => setRoleFilter(r)}>{r.replace(/_/g, ' ').toLowerCase()}</button>)}
          </div>
          {!shown.length ? <Empty>No review items — generate them from the latest run.</Empty> : (
            <div className="space-y-2">
              {shown.map((it) => (
                <Panel key={it.id}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Badge tone={RISK_TONE[it.risk_level]}>{it.risk_level}</Badge>
                        <span className="text-sm text-slate-200">{it.title}</span>
                      </div>
                      <div className="mt-0.5 text-xs text-slate-500">{it.summary}</div>
                      <div className="mt-1 flex flex-wrap gap-1 text-[10px] text-slate-500">
                        <Badge tone="slate">{it.recommended_role?.replace(/_/g, ' ').toLowerCase()}</Badge>
                        {it.source_type && <Badge tone="slate">{it.source_type}</Badge>}
                      </div>
                    </div>
                    <div className="shrink-0 text-right">
                      {it.review_status === 'REVIEWED' ? (
                        <Badge tone={it.decision === 'REJECT' ? 'red' : 'green'}>{it.decision?.replace(/_/g, ' ')}</Badge>
                      ) : (
                        <select className="input text-xs" defaultValue="" onChange={(e) => e.target.value && decide(it.id, e.target.value)}>
                          <option value="" disabled>decide…</option>
                          {DECISIONS.map((d) => <option key={d} value={d}>{d.replace(/_/g, ' ').toLowerCase()}</option>)}
                        </select>
                      )}
                    </div>
                  </div>
                </Panel>
              ))}
            </div>
          )}
          <Disclaimer text={HUMAN_RESPONSIBILITY} />
        </div>
      )}
    </div>
  )
}
