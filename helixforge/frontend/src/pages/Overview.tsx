import React, { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon'
import {
  Panel,
  StatCard,
  PageHeader,
  Badge,
  SourceBadge,
  HealthBadge,
  Spinner,
  ErrorNote,
  Empty,
  Disclaimer,
} from '@/components/ui'
import { api, SOURCE_META, HUMAN_RESPONSIBILITY, rememberRunId } from '@/lib/api'
import type { SourceType, ToolHealth } from '@/lib/api'

interface SmokeResult {
  label: string
  ok: boolean
  source_type?: SourceType
  summary: string
}

const PIPELINE_STEPS = [
  { name: 'Evidence', icon: 'FileSearch' },
  { name: 'Target', icon: 'Crosshair' },
  { name: 'Molecule', icon: 'FlaskConical' },
  { name: 'Safety', icon: 'ShieldCheck' },
  { name: 'Clinical', icon: 'Stethoscope' },
  { name: 'Report', icon: 'FileText' },
]

export function Overview() {
  const navigate = useNavigate()

  const [tools, setTools] = useState<ToolHealth[]>([])
  const [version, setVersion] = useState<string>('—')
  const [healthLoading, setHealthLoading] = useState<boolean>(true)
  const [healthError, setHealthError] = useState<string>('')

  const [smokeLoading, setSmokeLoading] = useState<boolean>(false)
  const [smokeResults, setSmokeResults] = useState<SmokeResult[]>([])
  const [smokeError, setSmokeError] = useState<string>('')

  const [pipelineLoading, setPipelineLoading] = useState<boolean>(false)
  const [pipelineError, setPipelineError] = useState<string>('')

  useEffect(() => {
    let active = true
    ;(async () => {
      setHealthLoading(true)
      setHealthError('')
      const [healthRes, toolsRes] = await Promise.allSettled([
        api.health(),
        api.toolsHealth(),
      ])
      if (!active) return
      if (healthRes.status === 'fulfilled') {
        setVersion(healthRes.value.version)
      }
      if (toolsRes.status === 'fulfilled') {
        setTools(toolsRes.value.tools)
      }
      if (toolsRes.status === 'rejected') {
        setHealthError(
          toolsRes.reason instanceof Error
            ? toolsRes.reason.message
            : 'Failed to load tool health.',
        )
      }
      setHealthLoading(false)
    })()
    return () => {
      active = false
    }
  }, [])

  const totalTools = tools.length
  const availableCount = tools.filter((t) => t.status === 'AVAILABLE').length
  const notConfiguredCount = tools.filter(
    (t) => t.status === 'NOT_CONFIGURED',
  ).length

  async function runSmokeTest() {
    setSmokeLoading(true)
    setSmokeError('')
    setSmokeResults([])
    try {
      const [rdkit, pubmed, chembl] = await Promise.allSettled([
        api.rdkitDescriptors('CC(=O)Oc1ccccc1C(=O)O'),
        api.pubmed('EGFR NSCLC resistance', 3),
        api.chemblTargets('EGFR', 3),
      ])

      const results: SmokeResult[] = []

      if (rdkit.status === 'fulfilled') {
        const r = rdkit.value
        const mw =
          r.descriptors?.mol_weight != null
            ? ` · MW ${r.descriptors.mol_weight}`
            : ''
        results.push({
          label: 'RDKit · Descriptors',
          ok: true,
          source_type: r.source_type,
          summary: r.valid
            ? `Canonical ${r.canonical_smiles}${mw}`
            : 'SMILES reported invalid',
        })
      } else {
        results.push({
          label: 'RDKit · Descriptors',
          ok: false,
          summary:
            rdkit.reason instanceof Error ? rdkit.reason.message : 'Request failed',
        })
      }

      if (pubmed.status === 'fulfilled') {
        const p = pubmed.value
        results.push({
          label: 'PubMed · Search',
          ok: true,
          source_type: p.source_type,
          summary: `${p.items.length} article${p.items.length === 1 ? '' : 's'} for "EGFR NSCLC resistance"`,
        })
      } else {
        results.push({
          label: 'PubMed · Search',
          ok: false,
          summary:
            pubmed.reason instanceof Error
              ? pubmed.reason.message
              : 'Request failed',
        })
      }

      if (chembl.status === 'fulfilled') {
        const c = chembl.value
        results.push({
          label: 'ChEMBL · Targets',
          ok: true,
          source_type: c.source_type,
          summary: `${c.items.length} target${c.items.length === 1 ? '' : 's'} matched "EGFR"`,
        })
      } else {
        results.push({
          label: 'ChEMBL · Targets',
          ok: false,
          summary:
            chembl.reason instanceof Error
              ? chembl.reason.message
              : 'Request failed',
        })
      }

      setSmokeResults(results)
    } catch (e) {
      setSmokeError(e instanceof Error ? e.message : 'Smoke test failed.')
    } finally {
      setSmokeLoading(false)
    }
  }

  async function startDemoPipeline() {
    setPipelineLoading(true)
    setPipelineError('')
    try {
      const run = await api.runPipeline({
        condition: 'non-small cell lung cancer',
        target_query: 'EGFR',
        max_results: 6,
        create_reinvent_config: true,
      })
      rememberRunId(run.run_id)
      navigate(`/cockpit?run=${encodeURIComponent(run.run_id)}`)
    } catch (e) {
      setPipelineError(
        e instanceof Error ? e.message : 'Failed to start demo pipeline.',
      )
      setPipelineLoading(false)
    }
  }

  return (
    <div className="mx-auto max-w-7xl px-5 py-6">
      <PageHeader
        icon={<Icon name="LayoutDashboard" size={22} />}
        title="HelixForge AI — Integration Console"
        subtitle="A real multi-agent drug-discovery backend that orchestrates PubMed, ClinicalTrials.gov, ChEMBL, RDKit and TDC — plus AutoDock Vina and REINVENT4 adapters. Every output is provenance-labeled so you always know whether you are seeing a live tool call, a demo fallback, or a not-yet-run step."
        actions={
          <>
            <button
              className="btn btn-secondary"
              onClick={runSmokeTest}
              disabled={smokeLoading}
            >
              <Icon name="Activity" size={16} />
              {smokeLoading ? 'Running…' : 'Run Real Tool Smoke Test'}
            </button>
            <button
              className="btn btn-primary"
              onClick={startDemoPipeline}
              disabled={pipelineLoading}
            >
              <Icon name="Play" size={16} />
              {pipelineLoading ? 'Starting…' : 'Start EGFR Demo Pipeline'}
            </button>
          </>
        }
      />

      {/* KPI row */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard
          label="Registered Tools"
          value={healthLoading ? '…' : totalTools}
          sub="Integration adapters"
        />
        <StatCard
          label="Available"
          value={healthLoading ? '…' : availableCount}
          sub="Live & ready"
          tone="green"
        />
        <StatCard
          label="Not Configured"
          value={healthLoading ? '…' : notConfiguredCount}
          sub="Needs credentials"
          tone="amber"
        />
        <StatCard
          label="Backend Version"
          value={<span className="mono text-2xl">{version}</span>}
          sub="FastAPI service"
        />
      </div>

      {/* Pipeline strip */}
      <Panel className="mt-4">
        <div className="section-title mb-3">Field 4 Pipeline</div>
        <div className="flex flex-wrap items-center gap-2">
          {PIPELINE_STEPS.map((s, i) => (
            <React.Fragment key={s.name}>
              <span className="chip border-line-bright bg-bg-hover text-slate-200">
                <Icon name={s.icon} size={14} />
                {s.name}
              </span>
              {i < PIPELINE_STEPS.length - 1 && (
                <Icon
                  name="ArrowRight"
                  size={14}
                  className="text-slate-600"
                />
              )}
            </React.Fragment>
          ))}
        </div>
      </Panel>

      {/* Pipeline launch error surfaces here (navigate on success) */}
      {pipelineError && (
        <div className="mt-4">
          <ErrorNote error={pipelineError} />
        </div>
      )}

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        {/* Tool status summary */}
        <Panel className="lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <div className="section-title">Tool Status</div>
            {healthLoading && <Spinner label="Checking tools…" />}
          </div>

          {healthError ? (
            <ErrorNote error={healthError} />
          ) : !healthLoading && tools.length === 0 ? (
            <Empty>No tools reported by the backend.</Empty>
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              {tools.map((t) => (
                <div
                  key={t.tool_id}
                  className="rounded-lg border border-line bg-bg-soft/40 p-3 card-hover"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="truncate text-sm font-medium text-white">
                      {t.name}
                    </div>
                    <HealthBadge status={t.status} />
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-[11px] uppercase tracking-wide text-slate-500">
                    <span>{t.category}</span>
                    <span className="text-slate-600">·</span>
                    <span className="mono normal-case text-slate-400">
                      {t.mode}
                    </span>
                  </div>
                  <div
                    className="mt-1 truncate text-xs text-slate-400"
                    title={t.detail}
                  >
                    {t.detail || '—'}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        {/* Smoke test results */}
        <Panel>
          <div className="mb-3 flex items-center justify-between">
            <div className="section-title">Live Smoke Test</div>
            {smokeLoading && <Spinner label="Calling tools…" />}
          </div>

          {smokeError ? (
            <ErrorNote error={smokeError} />
          ) : smokeResults.length === 0 && !smokeLoading ? (
            <Empty>
              Run the smoke test to hit RDKit, PubMed and ChEMBL in parallel and
              confirm live provenance.
            </Empty>
          ) : (
            <div className="space-y-2">
              {smokeResults.map((r) => (
                <div
                  key={r.label}
                  className="rounded-lg border border-line bg-bg-soft/40 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="text-sm font-medium text-white">
                      {r.label}
                    </div>
                    {r.ok && r.source_type ? (
                      <SourceBadge type={r.source_type} />
                    ) : (
                      <Badge tone="red">Failed</Badge>
                    )}
                  </div>
                  <div
                    className={`mt-1 text-xs ${r.ok ? 'text-slate-400' : 'text-helix-red'}`}
                  >
                    {r.summary}
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      {/* Provenance legend */}
      <Panel className="mt-4">
        <div className="section-title mb-1">Provenance Legend</div>
        <p className="mb-3 text-xs text-slate-400">
          Every tool result in HelixForge carries one of these labels so real
          data is never confused with a fallback or an un-run step.
        </p>
        <div className="flex flex-wrap gap-2">
          {(Object.keys(SOURCE_META) as SourceType[]).map((k) => (
            <div
              key={k}
              className="flex items-center gap-2 rounded-lg border border-line bg-bg-soft/40 px-3 py-1.5"
            >
              <SourceBadge type={k} />
              <span className="mono text-[11px] text-slate-500">{k}</span>
            </div>
          ))}
        </div>
      </Panel>

      <div className="mt-4">
        <Disclaimer text={HUMAN_RESPONSIBILITY} />
      </div>
    </div>
  )
}
