import React, { useState, useEffect } from 'react'
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
import { api, HUMAN_RESPONSIBILITY } from '@/lib/api'
import type { SourceType, ToolHealth } from '@/lib/api'

interface HealthPayload {
  checked_at: string
  summary: Record<string, number>
  tools: ToolHealth[]
}

interface TestResult {
  loading?: boolean
  error?: string
  sourceType?: SourceType
  summary?: string
}

// Pick a live test call per tool, matched by name (normalised, punctuation-free).
// Returns null when a tool has no exercise-able endpoint (never fakes a call).
function testFor(tool: ToolHealth): (() => Promise<TestResult>) | null {
  const n = (tool.name + ' ' + tool.category).toLowerCase().replace(/[^a-z0-9]/g, '')

  if (n.includes('rdkit')) {
    return async () => {
      const r = await api.rdkitDescriptors('CCO')
      return {
        sourceType: r.source_type,
        summary: r.output_summary || `valid=${r.valid} · canonical ${r.canonical_smiles || 'CCO'}`,
      }
    }
  }
  if (n.includes('pubmed')) {
    return async () => {
      const r = await api.pubmed('EGFR', 2)
      return { sourceType: r.source_type, summary: r.output_summary || `${r.items.length} PubMed record(s)` }
    }
  }
  if (n.includes('clinicaltrial')) {
    return async () => {
      const r = await api.clinicaltrials('non-small cell lung cancer', 'EGFR', 2)
      return { sourceType: r.source_type, summary: r.output_summary || `${r.items.length} trial(s)` }
    }
  }
  if (n.includes('chembl')) {
    return async () => {
      const r = await api.chemblTargets('EGFR', 2)
      return { sourceType: r.source_type, summary: r.output_summary || `${r.items.length} target(s)` }
    }
  }
  if (n.includes('tdc') || n.includes('pytdc')) {
    return async () => {
      const r = await api.tdcDatasets()
      return {
        sourceType: r.source_type,
        summary: `${r.installed ? 'installed' : 'not installed'} · ${r.datasets?.length ?? 0} dataset(s)`,
      }
    }
  }
  if (n.includes('vina') || n.includes('autodock')) {
    return async () => {
      const r = await api.vinaDock({})
      return { sourceType: r.source_type, summary: r.output_summary || `status=${r.status ?? 'unknown'}` }
    }
  }
  if (n.includes('reinvent')) {
    return async () => {
      const r = await api.reinventCreateConfig({ target_name: 'EGFR', max_molecules: 20 })
      return { sourceType: r.source_type, summary: r.output_summary || `config: ${r.config_path ?? 'n/a'}` }
    }
  }
  if (n.includes('safety')) {
    return async () => {
      const r = await api.safetyScreen({ text: 'high-level candidate prioritization' })
      return { sourceType: r.source_type, summary: r.output_summary || `status=${r.status ?? 'unknown'}` }
    }
  }
  if (n.includes('report')) {
    return async () => {
      const r = await api.listReports()
      return { summary: `${r.reports?.length ?? 0} report(s) stored` }
    }
  }
  return null
}

export function ToolRegistry() {
  const [data, setData] = useState<HealthPayload | null>(null)
  const [loading, setLoading] = useState<boolean>(true)
  const [error, setError] = useState<string | null>(null)
  const [tests, setTests] = useState<Record<string, TestResult>>({})

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.toolsHealth()
      setData(res)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  async function runTest(tool: ToolHealth) {
    const fn = testFor(tool)
    if (!fn) return
    setTests((prev) => ({ ...prev, [tool.tool_id]: { loading: true } }))
    try {
      const result = await fn()
      setTests((prev) => ({ ...prev, [tool.tool_id]: { ...result, loading: false } }))
    } catch (e) {
      setTests((prev) => ({
        ...prev,
        [tool.tool_id]: { loading: false, error: e instanceof Error ? e.message : String(e) },
      }))
    }
  }

  const summary = data?.summary ?? {}
  const total = data?.tools.length ?? 0
  const available = summary.AVAILABLE ?? 0
  const notConfigured = summary.NOT_CONFIGURED ?? 0
  const errored = summary.ERROR ?? 0
  const missingDeps = summary.MISSING_DEPENDENCY ?? 0

  return (
    <div>
      <PageHeader
        icon={<Icon name="Plug" size={22} />}
        title="Tool Registry"
        subtitle="Real integrations with honest, live-checked status — no tool is shown as connected unless the backend confirms it."
        actions={
          <button className="btn-secondary" onClick={load} disabled={loading}>
            <Icon name="RefreshCw" size={15} className={loading ? 'animate-spin' : ''} />
            Refresh health
          </button>
        }
      />

      {data && (
        <div className="mb-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <StatCard label="Total tools" value={total} sub={data.checked_at ? `checked ${data.checked_at}` : undefined} />
          <StatCard label="Available" value={available} tone="green" sub="ready to run" />
          <StatCard label="Not configured" value={notConfigured} tone="amber" sub="needs credentials" />
          <StatCard
            label="Errors"
            value={errored}
            tone={errored ? 'red' : 'slate'}
            sub={`${missingDeps} missing dependency`}
          />
        </div>
      )}

      {loading && !data && (
        <Panel>
          <Spinner label="Checking tool health…" />
        </Panel>
      )}

      {error && (
        <div className="mb-6">
          <ErrorNote error={error} />
        </div>
      )}

      {!loading && data && data.tools.length === 0 && <Empty>No tools registered on this backend.</Empty>}

      {data && data.tools.length > 0 && (
        <div className="grid gap-4 md:grid-cols-2">
          {data.tools.map((tool) => {
            const t = tests[tool.tool_id]
            const testable = testFor(tool) !== null
            return (
              <Panel key={tool.tool_id} className="card-hover flex flex-col">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="text-base font-semibold text-white">{tool.name}</div>
                    <div className="mt-0.5 text-xs uppercase tracking-wide text-slate-500">{tool.category}</div>
                  </div>
                  <HealthBadge status={tool.status} />
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-400">
                  <Badge tone="slate">mode: {tool.mode || 'n/a'}</Badge>
                  {typeof tool.latency_ms === 'number' && (
                    <Badge tone="cyan">
                      <Icon name="Timer" size={11} />
                      {tool.latency_ms} ms
                    </Badge>
                  )}
                </div>

                {tool.detail && <p className="mt-3 text-sm leading-relaxed text-slate-300">{tool.detail}</p>}

                <div className="mt-3">
                  <div className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Required config</div>
                  {tool.required_config && tool.required_config.length > 0 ? (
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {tool.required_config.map((cfg) => (
                        <span key={cfg} className="chip mono border-line-bright bg-bg-hover text-slate-300">
                          {cfg}
                        </span>
                      ))}
                    </div>
                  ) : (
                    <div className="mt-1 text-xs text-slate-500">None — no credentials needed.</div>
                  )}
                </div>

                <div className="mt-auto border-t border-line pt-3">
                  {testable ? (
                    <div className="flex flex-col gap-2">
                      <div className="flex items-center justify-between gap-2">
                        <button
                          className="btn-secondary"
                          onClick={() => runTest(tool)}
                          disabled={t?.loading}
                        >
                          <Icon name="Play" size={14} />
                          {t?.loading ? 'Testing…' : 'Test'}
                        </button>
                        {t?.sourceType && <SourceBadge type={t.sourceType} />}
                      </div>

                      {t?.loading && <Spinner label="Calling endpoint…" />}
                      {t?.error && <ErrorNote error={t.error} />}
                      {!t?.loading && !t?.error && t?.summary && (
                        <div className="rounded-lg border border-line bg-bg-soft/50 px-3 py-2 text-xs text-slate-300">
                          {t.summary}
                        </div>
                      )}
                      {!t && (
                        <div className="text-xs text-slate-500">Run a live call to verify this integration.</div>
                      )}
                    </div>
                  ) : (
                    <div className="text-xs text-slate-500">
                      No direct test endpoint — status above reflects the backend health check only.
                    </div>
                  )}
                </div>
              </Panel>
            )
          })}
        </div>
      )}

      <div className="mt-6">
        <Disclaimer text={HUMAN_RESPONSIBILITY} />
      </div>
    </div>
  )
}
