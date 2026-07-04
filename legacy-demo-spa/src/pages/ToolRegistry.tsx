import React from 'react'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  StatCard,
  ModeBadge,
  Disclaimer,
  PageHeader,
  Tabs,
  SearchInput,
  EmptyState,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { TOOL_CATEGORIES } from '@/lib/constants'
import type { AppMode, ToolConnectionStatus, ToolDef } from '@/types'

// Map connection status → tone / label / icon (per Section 12 registry spec).
const STATUS_META: Record<ToolConnectionStatus, { tone: string; label: string; icon: string }> = {
  connected: { tone: 'green', label: 'Connected', icon: 'CircleCheck' },
  missing_key: { tone: 'amber', label: 'Missing key', icon: 'KeyRound' },
  local_only: { tone: 'cyan', label: 'Local only', icon: 'HardDrive' },
  demo_fallback: { tone: 'slate', label: 'Demo fallback', icon: 'PlugZap' },
  error: { tone: 'red', label: 'Error', icon: 'TriangleAlert' },
}

const CATEGORY_ICON: Record<string, string> = {
  literature: 'BookOpen',
  biology: 'Crosshair',
  chemistry: 'FlaskConical',
  structure: 'Magnet',
  synthesis: 'Wrench',
  clinical: 'Stethoscope',
  safety: 'ShieldAlert',
}

function ModeSwitch({ mode, onChange }: { mode: AppMode; onChange: (m: AppMode) => void }) {
  return (
    <div className="inline-flex rounded-md border border-line bg-bg-soft/60 p-0.5">
      {(['demo', 'real'] as AppMode[]).map((m) => (
        <button
          key={m}
          type="button"
          onClick={() => onChange(m)}
          className={`rounded px-2.5 py-0.5 text-[11px] font-medium transition-colors ${
            mode === m ? 'bg-bg-raised text-white shadow-card' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          {m === 'demo' ? 'Demo' : 'Real'}
        </button>
      ))}
    </div>
  )
}

function ToolRegistryCard({
  tool,
  globalMode,
  onTest,
  onSetMode,
}: {
  tool: ToolDef
  globalMode: AppMode
  onTest: () => void
  onSetMode: (m: AppMode) => void
}) {
  const t = tool
  const meta = STATUS_META[t.status]
  const isSynthesis = t.category === 'synthesis'
  // Consistent with the store's testTool resolution: in Real Tool Mode a tool
  // without satisfied config silently drops to Demo — and is labeled, never hidden.
  const wouldFallback = globalMode === 'real' && !(t.requiredConfig.length === 0 || t.status === 'connected')

  return (
    <Panel className="flex flex-col gap-3 p-4 card-hover">
      {/* Header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="truncate text-sm font-semibold text-white">{t.name}</span>
          </div>
          <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{t.purpose}</p>
        </div>
        <Badge tone={meta.tone} icon={meta.icon} className="shrink-0 whitespace-nowrap">
          {meta.label}
        </Badge>
      </div>

      {/* Mode row */}
      <div className="flex flex-wrap items-center gap-2">
        <ModeBadge mode={t.mode} small />
        {wouldFallback && (
          <span title="Required config not satisfied in Real Tool Mode — resolves to labeled Demo output.">
            <ModeBadge mode="fallback" small />
          </span>
        )}
      </div>

      {/* Required config */}
      <div>
        <div className="mb-1 text-[10px] uppercase tracking-wide text-slate-500">Required config</div>
        {t.requiredConfig.length === 0 ? (
          <Badge tone="slate" icon="Check">none</Badge>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {t.requiredConfig.map((c) => (
              <Badge key={c} tone="slate" icon="KeyRound" className="text-[10px]">
                <span className="font-mono">{c}</span>
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Example output */}
      <div>
        <div className="mb-1 flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-slate-500">
          <Icon name="Braces" size={11} />
          Example output
        </div>
        <pre className="overflow-x-auto rounded-lg border border-line bg-bg-raised/60 p-2 font-mono text-[10px] leading-relaxed tabular-nums text-slate-300">
          {t.exampleOutput}
        </pre>
      </div>

      {/* Safety notes */}
      <div
        className={`flex items-start gap-1.5 rounded-lg border p-2 text-[11px] leading-relaxed ${
          isSynthesis
            ? 'border-helix-amber/30 bg-helix-amber/10 text-amber-300'
            : 'border-line bg-bg-soft/40 text-slate-400'
        }`}
      >
        <Icon name={isSynthesis ? 'ShieldAlert' : 'ShieldCheck'} size={12} className="mt-0.5 shrink-0" />
        <span>{t.safetyNotes}</span>
      </div>

      {/* Run meta */}
      <div className="grid grid-cols-2 gap-2 text-[11px]">
        <div className="rounded-lg border border-line bg-bg-raised/40 px-2 py-1.5">
          <div className="text-[10px] uppercase text-slate-500">Last run</div>
          <div className="font-mono tabular-nums text-slate-300">
            {t.lastRun ? new Date(t.lastRun).toLocaleTimeString() : '—'}
          </div>
        </div>
        <div className="rounded-lg border border-line bg-bg-raised/40 px-2 py-1.5">
          <div className="text-[10px] uppercase text-slate-500">Last error</div>
          <div className={`truncate font-mono ${t.lastError ? 'text-helix-red' : 'text-slate-500'}`} title={t.lastError}>
            {t.lastError ?? 'none'}
          </div>
        </div>
      </div>

      {/* Actions */}
      <div className="mt-auto flex items-center justify-between gap-2 border-t border-line-soft pt-3">
        <ModeSwitch mode={t.mode} onChange={onSetMode} />
        <Button variant="secondary" icon="Play" onClick={onTest} className="!px-2.5 !py-1 text-xs">
          Test
        </Button>
      </div>
    </Panel>
  )
}

export function ToolRegistry() {
  const tools = useAppStore((s) => s.tools)
  const testTool = useAppStore((s) => s.testTool)
  const setToolMode = useAppStore((s) => s.setToolMode)
  const globalMode = useAppStore((s) => s.settings.mode)

  const [cat, setCat] = React.useState<string>('all')
  const [query, setQuery] = React.useState('')

  const q = query.trim().toLowerCase()
  const matches = (t: ToolDef) =>
    !q || t.name.toLowerCase().includes(q) || t.purpose.toLowerCase().includes(q) || t.id.includes(q)

  const visibleCategories = (cat === 'all' ? TOOL_CATEGORIES : TOOL_CATEGORIES.filter((c) => c.id === cat)).filter((c) =>
    tools.some((t) => t.category === c.id && matches(t)),
  )

  const connectedCount = tools.filter((t) => t.status === 'connected').length
  const demoFallbackCount = tools.filter((t) => t.status === 'demo_fallback').length

  const testAllVisible = () => {
    tools.filter((t) => (cat === 'all' || t.category === cat) && matches(t)).forEach((t) => testTool(t.id))
  }

  const categoryTabs = [
    { id: 'all', label: 'All', icon: 'LayoutGrid', count: tools.length },
    ...TOOL_CATEGORIES.map((c) => ({
      id: c.id,
      label: c.label,
      icon: CATEGORY_ICON[c.id] ?? 'Wrench',
      count: tools.filter((t) => t.category === c.id).length,
    })),
  ]

  return (
    <div className="space-y-4">
      <PageHeader
        title="Tool Registry · 도구 레지스트리"
        subtitle="Every adapter the agents can call — connection status, mode, and labeled example output. 설정되지 않은 도구는 자동으로 Demo로 폴백되며, 사용된 적 없는 도구는 결코 사용된 것처럼 표시되지 않습니다."
        icon="Plug"
        actions={
          <>
            <ModeBadge mode={globalMode} />
            <Button variant="secondary" icon="Play" onClick={testAllVisible}>
              Test tools in view
            </Button>
          </>
        }
      />

      <Disclaimer tone={globalMode === 'real' ? 'green' : 'cyan'}>
        <span className="font-medium text-slate-100">Real Tool Mode fallback policy.</span> In Real Tool Mode, any adapter
        whose required configuration is not satisfied automatically falls back to a <ModeBadge mode="fallback" small />{' '}
        Demo Simulation and is explicitly labeled as such. A missing or unconfigured tool is <em>never</em> presented as if
        it were actually used — provenance is preserved on every output.
      </Disclaimer>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Total tools" value={tools.length} sub={`${TOOL_CATEGORIES.length} categories`} icon="Wrench" tone="cyan" />
        <StatCard label="Connected" value={connectedCount} sub="live adapters" icon="Plug" tone="green" />
        <StatCard label="Demo fallback" value={demoFallbackCount} sub="labeled simulation" icon="PlugZap" tone="amber" />
        <StatCard label="Categories" value={TOOL_CATEGORIES.length} sub="literature → safety" icon="LayoutGrid" tone="violet" />
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Tabs active={cat} onChange={setCat} tabs={categoryTabs} />
        <div className="w-full max-w-xs">
          <SearchInput value={query} onChange={setQuery} placeholder="Filter adapters…" />
        </div>
      </div>

      {/* Category groups */}
      {visibleCategories.length === 0 ? (
        <EmptyState icon="SearchX" title="No adapters match" desc="Try a different category filter or search term." />
      ) : (
        <div className="space-y-4">
          {visibleCategories.map((c) => {
            const catTools = tools.filter((t) => t.category === c.id && matches(t))
            return (
              <Panel key={c.id} className="p-4">
                <SectionTitle
                  icon={CATEGORY_ICON[c.id] ?? 'Wrench'}
                  right={<Badge tone="slate">{catTools.length} tools</Badge>}
                >
                  {c.label}
                </SectionTitle>
                <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
                  {catTools.map((t) => (
                    <ToolRegistryCard
                      key={t.id}
                      tool={t}
                      globalMode={globalMode}
                      onTest={() => testTool(t.id)}
                      onSetMode={(m) => setToolMode(t.id, m)}
                    />
                  ))}
                </div>
              </Panel>
            )
          })}
        </div>
      )}
    </div>
  )
}
