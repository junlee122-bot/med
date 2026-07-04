import React from 'react'
import { Icon } from '@/components/Icon'
import {
  Badge,
  Button,
  Panel,
  SectionTitle,
  Toggle,
  ModeBadge,
  Disclaimer,
  PageHeader,
  KeyVal,
} from '@/components/ui'
import { useAppStore } from '@/store/useAppStore'
import { SAFETY_POLICY_VERSION } from '@/lib/constants'
import type { UserSettings, ToolConnectionStatus } from '@/types'

// ----------------------------------------------------------------------------
// Local presentation helpers (no external state)
// ----------------------------------------------------------------------------

const STATUS_META: Record<ToolConnectionStatus, { tone: string; label: string; icon: string }> = {
  connected: { tone: 'green', label: 'Connected', icon: 'CircleCheck' },
  missing_key: { tone: 'amber', label: 'Missing key', icon: 'KeyRound' },
  local_only: { tone: 'cyan', label: 'Local only', icon: 'HardDrive' },
  demo_fallback: { tone: 'violet', label: 'Demo fallback', icon: 'FlaskConical' },
  error: { tone: 'red', label: 'Error', icon: 'TriangleAlert' },
}

const EFFORT_OPTIONS: UserSettings['effortLevel'][] = ['low', 'medium', 'high', 'max']

// Read-only, always-enforced safety policies (Section 3 / 23).
const ENFORCED_POLICIES = [
  {
    name: 'No synthesis routes',
    nameKo: '합성 경로 미표시',
    desc: 'Actionable synthesis routes, reagents, and reaction conditions are never displayed — feasibility is summarized as a score only.',
    icon: 'FlaskConical',
  },
  {
    name: 'Controlled / hazardous screening',
    nameKo: '규제·위험물질 차단',
    desc: 'Candidates matching controlled, explosive, or highly toxic chemical classes are quarantined by the Safety Auditor.',
    icon: 'ShieldX',
  },
  {
    name: 'Dual-use gate',
    nameKo: '이중용도 게이트',
    desc: 'Weaponization and harmful-enhancement requests are blocked before any generation step.',
    icon: 'ShieldAlert',
  },
  {
    name: 'No toxicity optimization',
    nameKo: '독성 최적화 금지',
    desc: 'The optimizer screens for hERG/Ames/DILI risk but never optimizes toward increased toxicity.',
    icon: 'Ban',
  },
  {
    name: 'Citation verification',
    nameKo: '인용 검증',
    desc: 'Fabricated or unverifiable references are marked and blocked from entering reports.',
    icon: 'BadgeCheck',
  },
  {
    name: 'Human responsibility',
    nameKo: '인간 책임 원칙',
    desc: 'Every output is research decision support only; final scientific, clinical, and regulatory responsibility remains with the human team.',
    icon: 'UserCheck',
  },
  {
    name: 'Auditable process',
    nameKo: '감사 가능성',
    desc: 'Observable agent/tool/validation trace is retained — no hidden chain-of-thought is exposed or required.',
    icon: 'ScrollText',
  },
]

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <div>
      <label className="label">{label}</label>
      {children}
      {hint && <div className="mt-1 text-[11px] leading-relaxed text-slate-500">{hint}</div>}
    </div>
  )
}

function Segmented({
  options,
  value,
  onChange,
}: {
  options: { id: string; label: string; icon?: string }[]
  value: string
  onChange: (id: string) => void
}) {
  return (
    <div className="inline-flex rounded-lg border border-line bg-bg-soft/60 p-1">
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          onClick={() => onChange(o.id)}
          className={`flex items-center gap-1.5 rounded-md px-3.5 py-1.5 text-sm transition-colors ${
            value === o.id ? 'bg-bg-raised text-white shadow-card' : 'text-slate-400 hover:text-slate-200'
          }`}
        >
          {o.icon && <Icon name={o.icon} size={14} />}
          {o.label}
        </button>
      ))}
    </div>
  )
}

// ----------------------------------------------------------------------------
// Page
// ----------------------------------------------------------------------------

export function Settings() {
  const settings = useAppStore((s) => s.settings)
  const tools = useAppStore((s) => s.tools)
  const projects = useAppStore((s) => s.projects)
  const patchSettings = useAppStore((s) => s.patchSettings)
  const setMode = useAppStore((s) => s.setMode)
  const setLanguage = useAppStore((s) => s.setLanguage)
  const setTheme = useAppStore((s) => s.setTheme)
  const resetDemoData = useAppStore((s) => s.resetDemoData)

  // Draft (masked) key values — never leave the browser, never sent anywhere.
  const [keyDrafts, setKeyDrafts] = React.useState<Record<string, string>>({})
  // Illustrative retention toggles — session-local only.
  const [retention, setRetention] = React.useState({
    retainAuditLogs: true,
    persistProjects: true,
    anonymizeExports: false,
    autoExportReports: false,
  })
  const [notice, setNotice] = React.useState<{ tone: string; msg: string } | null>(null)
  const fileRef = React.useRef<HTMLInputElement>(null)

  const configurable = tools.filter((t) => t.requiredConfig.length > 0)
  const connectedCount = tools.filter(
    (t) => (settings.apiKeyStatus[t.id] ?? t.status) === 'connected',
  ).length

  const onKeyChange = (toolId: string, val: string, originalStatus: ToolConnectionStatus) => {
    setKeyDrafts((d) => ({ ...d, [toolId]: val }))
    patchSettings({
      apiKeyStatus: {
        ...settings.apiKeyStatus,
        [toolId]: val.trim().length > 0 ? 'connected' : originalStatus,
      },
    })
  }

  const exportConfig = () => {
    const payload = {
      app: 'HelixForge AI',
      exportedAt: new Date().toISOString(),
      safetyPolicyVersion: SAFETY_POLICY_VERSION,
      projects: projects.map((p) => ({ ...p })),
      settings: { ...settings, apiKeyStatus: undefined }, // never export secrets/status
    }
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `helixforge-config-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
    setNotice({ tone: 'green', msg: `Exported ${projects.length} project(s) and settings as JSON (API keys excluded).` })
  }

  const importConfig = (file: File) => {
    const reader = new FileReader()
    reader.onload = () => {
      try {
        const parsed = JSON.parse(String(reader.result)) as {
          settings?: Partial<UserSettings>
          projects?: unknown[]
        }
        const src = parsed.settings ?? {}
        const patch: Partial<UserSettings> = {}
        if (typeof src.modelName === 'string') patch.modelName = src.modelName
        if (typeof src.fallbackModel === 'string') patch.fallbackModel = src.fallbackModel
        if (typeof src.temperature === 'number') patch.temperature = Math.max(0, Math.min(1, src.temperature))
        if (typeof src.maxOutput === 'number') patch.maxOutput = Math.max(256, Math.round(src.maxOutput))
        if (src.effortLevel && EFFORT_OPTIONS.includes(src.effortLevel)) patch.effortLevel = src.effortLevel
        if (typeof src.fastDemo === 'boolean') patch.fastDemo = src.fastDemo
        if (Object.keys(patch).length > 0) patchSettings(patch)
        // eslint-disable-next-line no-console
        console.log('[HelixForge] Imported config (safe subset applied):', patch, parsed)
        const projCount = Array.isArray(parsed.projects) ? parsed.projects.length : 0
        setNotice({
          tone: 'green',
          msg: `Config parsed successfully. Applied ${Object.keys(patch).length} model setting(s); ${projCount} project(s) detected (not overwritten — import is read-only in demo).`,
        })
      } catch {
        setNotice({ tone: 'red', msg: 'Import failed — the selected file is not valid HelixForge JSON.' })
      }
    }
    reader.readAsText(file)
  }

  const doReset = () => {
    if (window.confirm('Reset all demo data to the seeded state? Projects and workflow history you created will be cleared. Settings are preserved.')) {
      resetDemoData()
      setNotice({ tone: 'cyan', msg: 'Demo data reset to the seeded baseline.' })
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Settings · 설정"
        subtitle="Runtime mode, model parameters, tool configuration, and enforced safety policies. 모든 설정과 키는 이 브라우저에만 로컬 저장됩니다 — 실제 비밀키는 수집되지 않습니다."
        icon="Settings"
        actions={
          <div className="flex items-center gap-2">
            <ModeBadge mode={settings.mode} />
            <Badge tone="slate" icon="ShieldCheck">{SAFETY_POLICY_VERSION}</Badge>
          </div>
        }
      />

      {notice && (
        <Disclaimer tone={notice.tone}>
          <span className="flex-1">{notice.msg}</span>
        </Disclaimer>
      )}

      {/* 1 · Mode */}
      <Panel className="p-5">
        <SectionTitle icon="ToggleRight" right={<ModeBadge mode={settings.mode} />}>
          실행 모드 · Runtime Mode
        </SectionTitle>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="max-w-xl text-sm leading-relaxed text-slate-400">
            <span className="font-medium text-slate-200">Demo</span> runs the full pipeline on seeded, clearly-labeled simulation data — no external calls.{' '}
            <span className="font-medium text-slate-200">Real Tool</span> attempts live adapters where a key/endpoint is configured and{' '}
            <span className="text-helix-amber">automatically falls back to Demo Simulation</span> for any tool that is missing configuration or errors, so a run never silently produces unlabeled output.
          </div>
          <Segmented
            options={[
              { id: 'demo', label: 'Demo', icon: 'FlaskConical' },
              { id: 'real', label: 'Real Tool', icon: 'Plug' },
            ]}
            value={settings.mode}
            onChange={(id) => setMode(id as UserSettings['mode'])}
          />
        </div>
        {settings.mode === 'real' && (
          <div className="mt-3">
            <Disclaimer tone="amber">
              Real Tool mode is active. Tools without a configured key/endpoint below will run as{' '}
              <ModeBadge mode="fallback" small /> and their outputs stay labeled as Demo Fallback.
            </Disclaimer>
          </div>
        )}
      </Panel>

      {/* 2 · Model settings */}
      <Panel className="p-5">
        <SectionTitle icon="BrainCircuit" right={<Badge tone="cyan" icon="Sparkles">Orchestrator LLM</Badge>}>
          모델 설정 · Model Parameters
        </SectionTitle>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Model name" hint="Primary orchestrator/agent model identifier.">
            <input
              className="input font-mono text-xs"
              value={settings.modelName}
              onChange={(e) => patchSettings({ modelName: e.target.value })}
              placeholder="claude-orchestrator"
            />
          </Field>
          <Field label="Fallback model" hint="Used for lightweight sub-tasks and on primary-model error.">
            <input
              className="input font-mono text-xs"
              value={settings.fallbackModel}
              onChange={(e) => patchSettings({ fallbackModel: e.target.value })}
              placeholder="claude-small"
            />
          </Field>
          <Field label="Reasoning effort" hint="Higher effort = deeper planning & self-correction, more cost.">
            <select
              className="input"
              value={settings.effortLevel}
              onChange={(e) => patchSettings({ effortLevel: e.target.value as UserSettings['effortLevel'] })}
            >
              {EFFORT_OPTIONS.map((o) => (
                <option key={o} value={o}>
                  {o.charAt(0).toUpperCase() + o.slice(1)}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Max output tokens" hint="Per-agent generation ceiling.">
            <input
              type="number"
              className="input font-mono tabular-nums"
              min={256}
              step={256}
              value={settings.maxOutput}
              onChange={(e) => patchSettings({ maxOutput: Math.max(256, Number(e.target.value) || 0) })}
            />
          </Field>
          <Field
            label={`Temperature — ${settings.temperature.toFixed(2)}`}
            hint="Lower = more deterministic & reproducible. Recommended ≤ 0.3 for scientific runs."
          >
            <div className="flex items-center gap-3 pt-1">
              <span className="font-mono text-[11px] text-slate-500">0.0</span>
              <input
                type="range"
                min={0}
                max={1}
                step={0.05}
                value={settings.temperature}
                onChange={(e) => patchSettings({ temperature: Number(e.target.value) })}
                className="h-1.5 w-full cursor-pointer"
                style={{ accentColor: '#22d3ee' }}
              />
              <span className="font-mono text-[11px] text-slate-500">1.0</span>
            </div>
          </Field>
          <div className="flex items-end">
            <div className="w-full rounded-lg border border-line bg-bg-raised/40 p-3">
              <div className="text-[11px] uppercase tracking-wide text-slate-500">Effective config</div>
              <div className="mt-1 font-mono text-xs text-slate-300">
                {settings.modelName} · {settings.effortLevel} · t={settings.temperature.toFixed(2)} · {settings.maxOutput} tok
              </div>
            </div>
          </div>
        </div>
      </Panel>

      {/* 3 · Tool API keys / configs */}
      <Panel className="p-5">
        <SectionTitle
          icon="Plug"
          right={<Badge tone={connectedCount > 0 ? 'green' : 'slate'} icon="CircleCheck">{connectedCount} connected</Badge>}
        >
          도구 연결 · Tool API Keys & Configs
        </SectionTitle>
        <Disclaimer tone="slate">
          <span>
            <Icon name="Lock" size={12} className="mr-1 inline" />
            Keys are stored <span className="text-slate-200">locally in this browser only</span> and are never transmitted. These fields are illustrative for the demo — typing any value marks the adapter{' '}
            <span className="text-brand-300">Connected</span>; clearing it reverts to the tool&apos;s default state. No real secret is collected or validated.
          </span>
        </Disclaimer>
        <div className="mt-3 max-h-[420px] space-y-2 overflow-y-auto pr-1">
          {configurable.map((t) => {
            const status = settings.apiKeyStatus[t.id] ?? t.status
            const meta = STATUS_META[status]
            return (
              <div
                key={t.id}
                className="grid grid-cols-1 items-center gap-2 rounded-lg border border-line bg-bg-raised/40 p-3 md:grid-cols-[1.4fr_1.6fr_auto]"
              >
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium text-slate-200">{t.name}</div>
                  <div className="mt-0.5 flex flex-wrap gap-1">
                    {t.requiredConfig.map((c) => (
                      <span key={c} className="rounded border border-line-soft px-1.5 py-0.5 font-mono text-[10px] text-slate-500">
                        {c}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="relative">
                  <Icon name="KeyRound" size={13} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-600" />
                  <input
                    type="password"
                    className="input pl-8 font-mono text-xs"
                    placeholder={`Paste ${t.requiredConfig[0] ?? 'key'} (local only)…`}
                    value={keyDrafts[t.id] ?? ''}
                    onChange={(e) => onKeyChange(t.id, e.target.value, t.status)}
                    autoComplete="off"
                  />
                </div>
                <div className="justify-self-start md:justify-self-end">
                  <Badge tone={meta.tone} icon={meta.icon}>{meta.label}</Badge>
                </div>
              </div>
            )
          })}
        </div>
      </Panel>

      {/* 4 · Safety policies */}
      <Panel className="p-5">
        <SectionTitle
          icon="ShieldCheck"
          right={<Badge tone="green" icon="Lock">Enforced · {SAFETY_POLICY_VERSION}</Badge>}
        >
          안전 정책 · Safety Policies
        </SectionTitle>
        <p className="mb-3 text-sm text-slate-400">
          These policies are enforced at the engine level and <span className="font-medium text-slate-200">cannot be disabled from the UI</span>. They apply identically in Demo and Real Tool mode.
        </p>
        <div className="grid gap-2 md:grid-cols-2">
          {ENFORCED_POLICIES.map((p) => (
            <div key={p.name} className="flex items-start gap-3 rounded-lg border border-line bg-bg-raised/40 p-3">
              <div className="rounded-lg border border-brand-500/30 bg-brand-500/10 p-2 text-brand-300">
                <Icon name={p.icon} size={16} />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-medium text-slate-200">{p.name}</div>
                  <span title="Locked — cannot be disabled">
                    <Icon name="Lock" size={13} className="shrink-0 text-slate-600" />
                  </span>
                </div>
                <div className="text-[11px] text-slate-500">{p.nameKo}</div>
                <div className="mt-1 text-xs leading-relaxed text-slate-400">{p.desc}</div>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      {/* 5 · Data retention & performance */}
      <Panel className="p-5">
        <SectionTitle icon="Database" right={<Badge tone="slate" icon="Info">Illustrative · local</Badge>}>
          데이터 보존 & 성능 · Data & Performance
        </SectionTitle>
        <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
          <Toggle
            checked={settings.fastDemo}
            onChange={(v) => patchSettings({ fastDemo: v })}
            label="Fast demo playback"
            desc="Compress inter-step delays so the full workflow completes in seconds."
          />
          <Toggle
            checked={retention.persistProjects}
            onChange={(v) => setRetention((r) => ({ ...r, persistProjects: v }))}
            label="Persist projects in this browser"
            desc="Keep projects & settings in local storage between sessions."
          />
          <Toggle
            checked={retention.retainAuditLogs}
            onChange={(v) => setRetention((r) => ({ ...r, retainAuditLogs: v }))}
            label="Retain full audit trail"
            desc="Store the agent / tool / validation trace for each run."
          />
          <Toggle
            checked={retention.anonymizeExports}
            onChange={(v) => setRetention((r) => ({ ...r, anonymizeExports: v }))}
            label="Anonymize exports"
            desc="Strip owner e-mail and identifiers from exported JSON."
          />
          <Toggle
            checked={retention.autoExportReports}
            onChange={(v) => setRetention((r) => ({ ...r, autoExportReports: v }))}
            label="Auto-export reports on completion"
            desc="Generate a JSON copy of every report as a run finishes."
          />
        </div>
        <div className="mt-3 text-[11px] text-slate-500">
          <Icon name="Info" size={11} className="mr-1 inline" />
          Retention toggles above are illustrative and held for this session only — no data leaves your browser.
        </div>
      </Panel>

      {/* 6 & 7 · Language + Theme */}
      <div className="grid gap-4 sm:grid-cols-2">
        <Panel className="p-5">
          <SectionTitle icon="Languages">언어 · Language</SectionTitle>
          <div className="flex items-center justify-between gap-4">
            <div className="text-sm text-slate-400">Interface language for headings and labels.</div>
            <Segmented
              options={[
                { id: 'ko', label: '한국어' },
                { id: 'en', label: 'English' },
              ]}
              value={settings.language}
              onChange={(id) => setLanguage(id as UserSettings['language'])}
            />
          </div>
        </Panel>
        <Panel className="p-5">
          <SectionTitle icon="Palette">테마 · Theme</SectionTitle>
          <div className="flex items-center justify-between gap-4">
            <div className="text-sm text-slate-400">Dark is tuned for the scientific workbench.</div>
            <Segmented
              options={[
                { id: 'dark', label: 'Dark', icon: 'Moon' },
                { id: 'light', label: 'Light', icon: 'Sun' },
              ]}
              value={settings.theme}
              onChange={(id) => setTheme(id as UserSettings['theme'])}
            />
          </div>
        </Panel>
      </div>

      {/* 8 · Data management */}
      <Panel className="p-5">
        <SectionTitle icon="HardDriveDownload">데이터 관리 · Import / Export & Reset</SectionTitle>
        <div className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg border border-line bg-bg-raised/40 p-4">
            <div className="mb-2 inline-flex rounded-lg border border-line bg-bg-soft p-2 text-helix-cyan">
              <Icon name="Download" size={16} />
            </div>
            <div className="text-sm font-medium text-slate-200">Export configuration</div>
            <div className="mt-1 mb-3 text-xs leading-relaxed text-slate-500">
              Download projects and settings as JSON. API keys and connection status are excluded.
            </div>
            <Button variant="secondary" icon="Download" onClick={exportConfig}>Export JSON</Button>
          </div>

          <div className="rounded-lg border border-line bg-bg-raised/40 p-4">
            <div className="mb-2 inline-flex rounded-lg border border-line bg-bg-soft p-2 text-helix-cyan">
              <Icon name="Upload" size={16} />
            </div>
            <div className="text-sm font-medium text-slate-200">Import configuration</div>
            <div className="mt-1 mb-3 text-xs leading-relaxed text-slate-500">
              Read a HelixForge JSON file. Only safe model settings are applied; projects are validated, not overwritten.
            </div>
            <input
              ref={fileRef}
              type="file"
              accept="application/json,.json"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0]
                if (f) importConfig(f)
                e.target.value = ''
              }}
            />
            <Button variant="secondary" icon="Upload" onClick={() => fileRef.current?.click()}>Choose file…</Button>
          </div>

          <div className="rounded-lg border border-helix-red/30 bg-helix-red/5 p-4">
            <div className="mb-2 inline-flex rounded-lg border border-helix-red/40 bg-helix-red/10 p-2 text-helix-red">
              <Icon name="RotateCcw" size={16} />
            </div>
            <div className="text-sm font-medium text-slate-200">Reset demo data</div>
            <div className="mt-1 mb-3 text-xs leading-relaxed text-slate-500">
              Restore the seeded baseline (evidence, targets, molecules, workflow). Your settings are preserved.
            </div>
            <Button variant="danger" icon="RotateCcw" onClick={doReset}>Reset to seeded data</Button>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-line bg-bg-raised/40 p-3">
          <KeyVal k="Settings id" v={settings.id} mono />
          <KeyVal k="Safety policy version" v={settings.safetyPolicyVersion} mono />
          <KeyVal k="Projects stored" v={projects.length} mono />
          <KeyVal k="Last updated" v={new Date(settings.updatedAt).toLocaleString()} mono />
        </div>
      </Panel>
    </div>
  )
}
