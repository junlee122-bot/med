import React from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon'
import { Badge, ModeBadge, SafetyBadge, Button } from '@/components/ui'
import { NAV, NAV_GROUPS } from '@/lib/i18n'
import { useAppStore } from '@/store/useAppStore'

export function Layout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate()
  const settings = useAppStore((s) => s.settings)
  const projects = useAppStore((s) => s.projects)
  const activeProjectId = useAppStore((s) => s.activeProjectId)
  const setActiveProject = useAppStore((s) => s.setActiveProject)
  const setMode = useAppStore((s) => s.setMode)
  const wf = useAppStore((s) => s.activeWorkflow())
  const runControl = useAppStore((s) => s.runControl)
  const [mobileOpen, setMobileOpen] = React.useState(false)
  const lang = settings.language

  const active = projects.find((p) => p.id === activeProjectId)

  return (
    <div className="flex h-full min-h-screen bg-bg text-slate-200">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-40 flex w-64 flex-col border-r border-line bg-bg-soft/95 backdrop-blur transition-transform lg:static lg:translate-x-0 ${
          mobileOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex items-center gap-2.5 border-b border-line px-4 py-4">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-brand-400 to-helix-blue text-slate-950 shadow-glow">
            <Icon name="Dna" size={20} />
          </div>
          <div className="leading-tight">
            <div className="text-sm font-bold text-white">HelixForge AI</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Agentic Discovery OS</div>
          </div>
        </div>

        <nav className="flex-1 overflow-y-auto px-2 py-3 no-scrollbar">
          {NAV_GROUPS.map((g) => (
            <div key={g.id} className="mb-4">
              <div className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
                {lang === 'ko' ? g.ko : g.en}
              </div>
              {NAV.filter((n) => n.group === g.id).map((n) => (
                <NavLink
                  key={n.key}
                  to={n.path}
                  onClick={() => setMobileOpen(false)}
                  className={({ isActive }) =>
                    `group mb-0.5 flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? 'bg-bg-raised text-white shadow-card ring-1 ring-line-bright'
                        : 'text-slate-400 hover:bg-bg-hover/60 hover:text-slate-200'
                    }`
                  }
                >
                  {({ isActive }) => (
                    <>
                      <Icon name={n.icon} size={16} className={isActive ? 'text-helix-cyan' : 'text-slate-500 group-hover:text-slate-300'} />
                      <span className="flex-1">{lang === 'ko' ? n.ko : n.en}</span>
                      {n.key === 'cockpit' && runControl === 'running' && (
                        <span className="h-2 w-2 animate-pulse rounded-full bg-brand-400" />
                      )}
                    </>
                  )}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="border-t border-line p-3 text-[10px] leading-relaxed text-slate-500">
          <div className="flex items-center gap-1.5">
            <Icon name="ShieldCheck" size={12} className="text-brand-400" />
            {settings.safetyPolicyVersion}
          </div>
          <div className="mt-1">Research decision support only. No wet-lab / synthesis / medical advice.</div>
        </div>
      </aside>

      {/* Main column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Header */}
        <header className="sticky top-0 z-30 border-b border-line bg-bg-soft/80 backdrop-blur">
          <div className="flex items-center gap-3 px-4 py-3">
            <Button variant="ghost" icon="Menu" className="!px-2 lg:hidden" onClick={() => setMobileOpen((o) => !o)} />

            <div className="flex min-w-0 items-center gap-2">
              <Icon name="FolderKanban" size={15} className="shrink-0 text-slate-500" />
              <select
                value={activeProjectId}
                onChange={(e) => setActiveProject(e.target.value)}
                className="min-w-0 max-w-[240px] truncate rounded-lg border border-line bg-bg-soft px-2.5 py-1.5 text-sm text-slate-200 focus:border-helix-cyan/60 focus:outline-none"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </div>

            <div className="ml-auto flex items-center gap-2">
              <div className="hidden items-center gap-2 sm:flex">
                {active && <Badge tone="slate" icon="Microscope">{active.disease}</Badge>}
                {wf && <SafetyBadge status={wf.safetyStatus} small />}
              </div>
              <button
                onClick={() => setMode(settings.mode === 'demo' ? 'real' : 'demo')}
                title="Toggle Demo / Real Tool Mode"
                className="transition-transform hover:scale-105"
              >
                <ModeBadge mode={settings.mode} />
              </button>
              <Button variant="secondary" icon="Download" onClick={() => navigate('/reports')} className="hidden md:inline-flex">
                Export
              </Button>
              <Button variant="primary" icon="Play" onClick={() => navigate('/cockpit')}>
                <span className="hidden sm:inline">Cockpit</span>
              </Button>
            </div>
          </div>

          {/* Safety banner */}
          <div className="flex items-center gap-2 border-t border-line bg-bg/60 px-4 py-1.5 text-[11px] text-slate-400">
            <Icon name="ShieldAlert" size={13} className="text-helix-amber" />
            {settings.mode === 'demo'
              ? 'Demo Mode: all scientific outputs are simulated unless explicitly marked as real tool output. · 연구 의사결정 지원 전용 — 실험 프로토콜/합성 레시피/의료 자문 없음.'
              : 'Real Tool Mode: unconfigured tools fall back to Demo and are labeled as fallback — a missing tool is never presented as used.'}
          </div>
        </header>

        <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-6 lg:px-6">{children}</main>

        <footer className="border-t border-line px-6 py-3 text-center text-[11px] text-slate-600">
          HelixForge AI · 4th JUMP AI Drug Discovery Competition — Field 4 · This system is research decision support only; final responsibility belongs to the human research team.
        </footer>
      </div>
    </div>
  )
}
