import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon'
import { Badge, Button, Panel, StatCard, SectionTitle, ModeBadge } from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'

const PIPELINE = [
  { k: 'Disease', icon: 'Microscope', tone: 'blue' },
  { k: 'Target', icon: 'Crosshair', tone: 'cyan' },
  { k: 'Hypothesis', icon: 'Lightbulb', tone: 'violet' },
  { k: 'Molecule', icon: 'Atom', tone: 'green' },
  { k: 'Safety', icon: 'ShieldCheck', tone: 'red' },
  { k: 'Clinical / Reg', icon: 'Stethoscope', tone: 'pink' },
  { k: 'Report', icon: 'FileText', tone: 'amber' },
]

const HIGHLIGHTS = [
  { icon: 'Network', title: 'Multi-agent autonomy', desc: '17 specialized agents decompose the goal into a 16-stage DAG and coordinate — not a single chatbot.' },
  { icon: 'Plug', title: 'Tool integration', desc: 'Adapters for RDKit, TDC, REINVENT4, docking, literature, and clinical/regulatory sources — with Demo fallback.' },
  { icon: 'RefreshCw', title: 'Self-correction loop', desc: 'Invalid SMILES, fake citations, tool errors, and overclaims are caught and revised — visibly.' },
  { icon: 'ShieldCheck', title: 'Safety gate', desc: 'Hazardous / dual-use candidates are blocked. No synthesis routes, ever.' },
  { icon: 'ScrollText', title: 'Transparent audit trail', desc: 'Observable process trace — no hidden chain-of-thought — for every agent, tool, and validation.' },
  { icon: 'Gauge', title: 'Evaluation harness', desc: 'Rediscovery, generation, ADMET, docking, agent, and safety benchmark modules.' },
]

export function Overview() {
  const navigate = useNavigate()
  const startWorkflow = useAppStore((s) => s.startWorkflow)
  const activeProjectId = useAppStore((s) => s.activeProjectId)
  const settings = useAppStore((s) => s.settings)
  const molecules = useAppStore((s) => s.molecules)
  const targets = useAppStore((s) => s.targets)
  const evidence = useAppStore((s) => s.evidence)
  const safetyFlags = useAppStore((s) => s.safetyFlags)

  const runDemo = () => {
    startWorkflow(activeProjectId, settings.fastDemo)
    navigate('/cockpit')
  }

  return (
    <div className="space-y-6">
      {/* Hero */}
      <Panel className="relative overflow-hidden p-8 grid-bg">
        <div className="absolute -right-24 -top-24 h-72 w-72 rounded-full bg-brand-500/10 blur-3xl" />
        <div className="absolute -bottom-24 left-1/3 h-72 w-72 rounded-full bg-helix-blue/10 blur-3xl" />
        <div className="relative">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <Badge tone="cyan" icon="Sparkles">4th JUMP AI · Field 4</Badge>
            <ModeBadge mode={settings.mode} />
            <Badge tone="green" icon="ShieldCheck">Evidence-grounded · Auditable · Safety-gated</Badge>
          </div>
          <h1 className="max-w-3xl text-balance text-3xl font-bold leading-tight text-white md:text-4xl">
            신약개발 전주기를 연결하는 <span className="gradient-text">Agentic AI Workbench</span>
          </h1>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-slate-400">
            HelixForge AI decomposes a drug-discovery objective into evidence mining, target prioritization, molecule
            optimization, safety screening, and clinical/regulatory strategy — with every tool call and validation step
            logged. 챗봇이 아니라, 도구를 사용하고 스스로 오류를 교정하는 다중 에이전트 의사결정 지원 플랫폼입니다.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Button variant="primary" icon="Play" onClick={runDemo}>
              Run Full Demo Workflow
            </Button>
            <Button variant="secondary" icon="Plus" onClick={() => navigate('/projects/new')}>
              Create New Project
            </Button>
            <Button variant="ghost" icon="Presentation" onClick={() => navigate('/reports')}>
              View Judge Report
            </Button>
          </div>
        </div>
      </Panel>

      {/* Pipeline */}
      <Panel className="p-5">
        <SectionTitle icon="Workflow">End-to-end pipeline · 파이프라인</SectionTitle>
        <div className="flex flex-wrap items-center gap-2">
          {PIPELINE.map((p, i) => (
            <div key={p.k} className="flex items-center gap-2">
              <div className="flex items-center gap-2 rounded-lg border border-line bg-bg-raised px-3 py-2">
                <Icon name={p.icon} size={16} className="text-helix-cyan" />
                <span className="text-sm text-slate-200">{p.k}</span>
              </div>
              {i < PIPELINE.length - 1 && <Icon name="ChevronRight" size={16} className="text-slate-600" />}
            </div>
          ))}
        </div>
      </Panel>

      {/* Live demo stats */}
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <StatCard label="Evidence items" value={evidence.length} sub="6 demo-verified · 1 contradictory · 1 blocked" icon="BookOpen" tone="violet" />
        <StatCard label="Targets ranked" value={targets.length} sub={`Top: ${targets[0]?.symbol} (${targets[0]?.score})`} icon="Crosshair" tone="cyan" />
        <StatCard label="Molecule candidates" value={molecules.length} sub={`${molecules.filter((m) => m.validityStatus === 'valid').length} valid · ${molecules.filter((m) => m.validityStatus === 'invalid').length} invalid`} icon="Atom" tone="green" />
        <StatCard label="Safety flags" value={safetyFlags.length} sub={`${safetyFlags.filter((f) => f.status === 'BLOCKED').length} blocked · ${safetyFlags.filter((f) => f.status === 'REVIEW_REQUIRED').length} review`} icon="ShieldAlert" tone="red" />
      </div>

      {/* Judge highlights */}
      <div>
        <SectionTitle icon="Award" right={<Badge tone="slate" icon="Eye">Judge-facing highlights</Badge>}>
          왜 이것이 진짜 에이전트 시스템인가
        </SectionTitle>
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {HIGHLIGHTS.map((h) => (
            <Panel key={h.title} className="card-hover p-4">
              <div className="mb-2 inline-flex rounded-lg border border-line bg-bg-raised p-2 text-helix-cyan">
                <Icon name={h.icon} size={18} />
              </div>
              <div className="text-sm font-semibold text-white">{h.title}</div>
              <div className="mt-1 text-xs leading-relaxed text-slate-400">{h.desc}</div>
            </Panel>
          ))}
        </div>
      </div>

      {/* Quick nav */}
      <Panel className="p-5">
        <SectionTitle icon="Compass">Explore the system</SectionTitle>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { to: '/cockpit', icon: 'Cpu', label: 'Agent Cockpit', desc: 'Live DAG, agents, audit trail, error injection' },
            { to: '/molecules', icon: 'Atom', label: 'Molecule Lab', desc: 'Leaderboard, ADMET, safety, no synthesis routes' },
            { to: '/safety', icon: 'ShieldCheck', label: 'Safety Gate', desc: 'Policy checks, blocked candidates, ethics appendix' },
            { to: '/evaluation', icon: 'Gauge', label: 'Evaluation Bench', desc: 'Rediscovery, generation, agent & safety metrics' },
          ].map((q) => (
            <button
              key={q.to}
              onClick={() => navigate(q.to)}
              className="flex flex-col items-start gap-1 rounded-lg border border-line bg-bg-raised p-3 text-left transition-colors hover:border-line-bright hover:bg-bg-hover"
            >
              <Icon name={q.icon} size={18} className="text-helix-cyan" />
              <div className="text-sm font-medium text-white">{q.label}</div>
              <div className="text-[11px] text-slate-500">{q.desc}</div>
            </button>
          ))}
        </div>
      </Panel>
    </div>
  )
}
