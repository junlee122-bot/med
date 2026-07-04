import { useMemo, useState } from 'react'
import { Icon } from '@/components/Icon'
import { Disclaimer, Field, PageHeader, Panel } from '@/components/ui'
import { MetricTile } from '@/components/agentic'

export function Impact() {
  const [a, setA] = useState({
    litHours: 40, targetHours: 24, moleculeHours: 30, reportHours: 12,
    hourlyCost: 85, workflowsPerMonth: 6, automationFraction: 55, toolCost: 0.5,
  })
  const set = (k: string, v: number) => setA((s) => ({ ...s, [k]: v }))

  const out = useMemo(() => {
    const manualPer = a.litHours + a.targetHours + a.moleculeHours + a.reportHours
    const frac = Math.max(0, Math.min(1, a.automationFraction / 100))
    const savedPer = manualPer * frac
    const hoursMonth = Math.round(savedPer * a.workflowsPerMonth)
    const gross = Math.round(hoursMonth * a.hourlyCost)
    const runCost = Math.round(a.toolCost * a.workflowsPerMonth)
    const net = gross - runCost
    // Conservative ±20% range.
    return { hoursMonth, gross, net, low: Math.round(net * 0.8), high: Math.round(net * 1.2), manualPer, savedPer: Math.round(savedPer) }
  }, [a])

  const INPUTS: [string, string, string][] = [
    ['litHours', 'Literature triage (h/workflow)', 'litHours'],
    ['targetHours', 'Target prioritization (h/workflow)', 'targetHours'],
    ['moleculeHours', 'Molecule curation (h/workflow)', 'moleculeHours'],
    ['reportHours', 'Report writing (h/workflow)', 'reportHours'],
    ['hourlyCost', 'Researcher cost ($/h)', 'hourlyCost'],
    ['workflowsPerMonth', 'Workflows / month', 'workflowsPerMonth'],
    ['automationFraction', 'Automation fraction (%)', 'automationFraction'],
    ['toolCost', 'Tool/API cost ($/workflow)', 'toolCost'],
  ]

  return (
    <div>
      <PageHeader
        icon={<Icon name="TrendingUp" size={22} />}
        title="Business & Social Impact"
        subtitle="An adjustable, conservative estimate of the search-and-documentation burden HelixForge reduces. Ranges only — it does not replace wet-lab, clinical, or regulatory validation."
      />
      <div className="grid gap-4 lg:grid-cols-2">
        <Panel>
          <div className="section-title mb-3">Assumptions</div>
          <div className="grid grid-cols-2 gap-3">
            {INPUTS.map(([key, label]) => (
              <Field key={key} label={label}>
                <input type="number" className="input" value={(a as any)[key]} onChange={(e) => set(key, +e.target.value)} />
              </Field>
            ))}
          </div>
        </Panel>
        <div className="space-y-4">
          <Panel>
            <div className="section-title mb-3">Estimated monthly value (ranges)</div>
            <div className="grid grid-cols-2 gap-3">
              <MetricTile label="Hours saved / month" value={out.hoursMonth.toLocaleString()} tone="green" sub={`${out.savedPer}h × ${a.workflowsPerMonth} workflows`} />
              <MetricTile label="Net cost saved / month" value={`$${out.net.toLocaleString()}`} tone="green" sub={`range $${out.low.toLocaleString()}–$${out.high.toLocaleString()}`} />
              <MetricTile label="Gross saved" value={`$${out.gross.toLocaleString()}`} />
              <MetricTile label="Manual baseline" value={`${out.manualPer}h`} sub="per workflow" />
            </div>
          </Panel>
          <Panel>
            <div className="section-title mb-2">Where human review remains essential</div>
            <ul className="space-y-1 text-xs text-slate-400">
              {['Target & candidate sign-off', 'ADMET / toxicology confirmation (wet-lab)', 'Synthetic route design (out of scope by policy)', 'Clinical protocol finalization', 'All regulatory decisions'].map((t) => (
                <li key={t} className="flex items-center gap-2"><Icon name="UserCheck" size={13} className="text-helix-cyan" /> {t}</li>
              ))}
            </ul>
            <div className="mt-3 rounded-lg border border-line bg-bg-soft/40 p-2 text-[11px] text-slate-400">
              Risk reduction: an immutable audit trail, citation verification, and a safety gate reduce the risk of acting on fabricated or unsafe outputs.
            </div>
          </Panel>
        </div>
      </div>
      <div className="mt-4"><Disclaimer text="HelixForge AI reduces the search and documentation burden; it does not remove wet-lab, clinical, or regulatory validation. Estimates are illustrative ranges, not guarantees." /></div>
    </div>
  )
}
