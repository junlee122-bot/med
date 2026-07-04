import React, { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import { Icon } from './Icon'
import { api } from '@/lib/api'

export const NAV = [
  { path: '/', label: 'Overview', icon: 'LayoutDashboard', group: 'Main' },
  { path: '/tools', label: 'Tool Registry', icon: 'Plug', group: 'Main' },
  { path: '/cockpit', label: 'Agent Cockpit', icon: 'Cpu', group: 'Run' },
  { path: '/evidence', label: 'Evidence Explorer', icon: 'BookOpen', group: 'Run' },
  { path: '/molecules', label: 'Molecule Lab', icon: 'Atom', group: 'Run' },
  { path: '/tdc', label: 'TDC Evaluation Bench', icon: 'Gauge', group: 'Run' },
  { path: '/docking', label: 'Docking Lab', icon: 'Magnet', group: 'Run' },
  { path: '/reinvent', label: 'REINVENT4 Studio', icon: 'FlaskConical', group: 'Run' },
  { path: '/safety', label: 'Safety Gate', icon: 'ShieldCheck', group: 'Governance' },
  { path: '/reports', label: 'Reports', icon: 'FileText', group: 'Governance' },
  { path: '/settings', label: 'Settings', icon: 'Settings', group: 'System' },
]

const GROUPS = ['Main', 'Run', 'Governance', 'System']

export function Layout({ children }: { children: React.ReactNode }) {
  const [online, setOnline] = useState<boolean | null>(null)
  const [version, setVersion] = useState('')
  const loc = useLocation()

  useEffect(() => {
    let alive = true
    api.health()
      .then((h) => { if (alive) { setOnline(true); setVersion(h.version) } })
      .catch(() => { if (alive) setOnline(false) })
    return () => { alive = false }
  }, [loc.pathname])

  return (
    <div className="flex min-h-screen">
      <aside className="fixed inset-y-0 left-0 flex w-64 flex-col border-r border-line bg-bg-soft/70 backdrop-blur">
        <div className="flex items-center gap-2.5 border-b border-line px-5 py-4">
          <div className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-brand-400 to-helix-blue text-lg">🧬</div>
          <div>
            <div className="text-sm font-semibold leading-tight text-white">HelixForge AI</div>
            <div className="text-[10px] uppercase tracking-wider text-slate-500">Integration Console</div>
          </div>
        </div>
        <nav className="flex-1 overflow-y-auto px-3 py-4 no-scrollbar">
          {GROUPS.map((g) => (
            <div key={g} className="mb-4">
              <div className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-slate-600">{g}</div>
              {NAV.filter((n) => n.group === g).map((n) => (
                <NavLink
                  key={n.path}
                  to={n.path}
                  end={n.path === '/'}
                  className={({ isActive }) =>
                    `mb-0.5 flex items-center gap-3 rounded-lg px-2.5 py-2 text-sm transition-colors ${
                      isActive ? 'bg-bg-hover text-white shadow-inner' : 'text-slate-400 hover:bg-bg-hover/60 hover:text-slate-200'
                    }`
                  }
                >
                  <Icon name={n.icon} size={16} />
                  {n.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>
        <div className="border-t border-line px-4 py-3 text-[11px] text-slate-500">
          <div className="flex items-center gap-2">
            <span className={`h-2 w-2 rounded-full ${online === null ? 'bg-slate-500' : online ? 'bg-brand-400' : 'bg-helix-red'}`} />
            {online === null ? 'checking backend…' : online ? `backend online · v${version}` : 'backend offline'}
          </div>
          <div className="mt-1">Research decision support only.</div>
        </div>
      </aside>

      <div className="ml-64 flex-1">
        {online === false && (
          <div className="border-b border-helix-red/30 bg-helix-red/10 px-6 py-2 text-xs text-helix-red">
            Backend not reachable at the configured API base. Start it with{' '}
            <code className="mono">uvicorn app.main:app --port 8000</code> (see README).
          </div>
        )}
        <main className="mx-auto max-w-[1400px] px-6 py-6 grid-bg min-h-screen">{children}</main>
      </div>
    </div>
  )
}
