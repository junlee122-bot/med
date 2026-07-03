import React from 'react'
import { useNavigate } from 'react-router-dom'
import { Icon } from '@/components/Icon'
import { Badge, Button, Panel, SectionTitle, SafetyBadge, Toggle, PageHeader, EmptyState } from '@/components/ui'
import {
  AgentCard,
  AuditTimeline,
  ConfidenceTrend,
  CostLedger,
  ErrorInjectionPanel,
  ToolRunCard,
  WorkflowDAG,
} from '@/components/workflow'
import { useAppStore } from '@/store/useAppStore'
import { STAGE_MAP } from '@/lib/constants'

export function Cockpit() {
  const navigate = useNavigate()
  const s = useAppStore()
  const wf = useAppStore((st) => st.activeWorkflow())
  const runControl = useAppStore((st) => st.runControl)
  const wfId = useAppStore((st) => st.currentWorkflowId)
  const agentRuns = useAppStore((st) => st.agentRuns).filter((a) => a.workflowId === wfId)
  const toolRuns = useAppStore((st) => st.toolRuns).filter((t) => t.workflowId === wfId)
  const auditEvents = useAppStore((st) => st.auditEvents).filter((e) => e.workflowId === wfId)
  const injections = useAppStore((st) => st.injections)
  const settings = useAppStore((st) => st.settings)

  const isRunning = runControl === 'running'
  const isPaused = runControl === 'paused'
  const started = agentRuns.length > 0 || isRunning
  const current = wf?.currentStage ?? 'IDLE'
  const recentAgents = [...agentRuns].slice(-5).reverse()
  const recentTools = [...toolRuns].slice(-6).reverse()
  const totalLatency = toolRuns.reduce((a, t) => a + t.latencyMs, 0)

  const start = () => s.startWorkflow(s.activeProjectId, settings.fastDemo)

  return (
    <div className="space-y-4">
      <PageHeader
        title="Agent Cockpit"
        subtitle="Observable Agent Trace — 자율 계획 · 도구 호출 · 검증 · 자기교정 루프. This panel shows external process transparency, not hidden model chain-of-thought."
        icon="Cpu"
        actions={
          <div className="flex items-center gap-2">
            <Toggle checked={settings.fastDemo} onChange={(v) => s.patchSettings({ fastDemo: v })} label="Fast demo" />
            {wf && <SafetyBadge status={wf.safetyStatus} />}
          </div>
        }
      />

      {/* Controls */}
      <Panel className="p-3">
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="primary" icon="Play" onClick={start} disabled={isRunning}>
            Run Full Pipeline
          </Button>
          <Button variant="secondary" icon="Pause" onClick={s.pauseWorkflow} disabled={!isRunning}>
            Pause
          </Button>
          <Button variant="secondary" icon="Play" onClick={s.resumeWorkflow} disabled={!isPaused}>
            Resume
          </Button>
          <Button variant="secondary" icon="StepForward" onClick={s.stepWorkflow} disabled={isRunning || (!started && s.runScript.length === 0)}>
            Run Next Step
          </Button>
          <Button variant="ghost" icon="Square" onClick={s.stopWorkflow} disabled={!started && s.runScript.length === 0}>
            Reset Run
          </Button>
          <div className="ml-auto flex items-center gap-2 text-xs text-slate-400">
            <span className="flex items-center gap-1.5">
              <span className={`h-2 w-2 rounded-full ${isRunning ? 'animate-pulse bg-brand-400' : isPaused ? 'bg-helix-amber' : runControl === 'complete' ? 'bg-brand-500' : 'bg-slate-600'}`} />
              {runControl.toUpperCase()}
            </span>
            <span className="text-slate-600">·</span>
            <span className="font-mono">{STAGE_MAP[current]?.label ?? current}</span>
          </div>
        </div>
      </Panel>

      {/* Error injection */}
      <Panel className="p-4">
        <SectionTitle icon="Bug" right={<Badge tone="amber" icon="RefreshCw">Self-correction demo</Badge>}>
          Error Injection — 오류를 주입하고 시스템이 스스로 교정하는 과정을 시연
        </SectionTitle>
        <ErrorInjectionPanel injections={injections} onToggle={s.setInjection} />
        <div className="mt-2 text-[11px] text-slate-500">
          Enabled injections create a visible correction loop in the trace when the pipeline runs. Toggle, then Run Full Pipeline.
        </div>
      </Panel>

      {!started && s.runScript.length === 0 ? (
        <EmptyState
          icon="Cpu"
          title="Pipeline idle"
          desc="Run the full pipeline to watch 17 agents decompose the goal, call tools, validate outputs, and self-correct injected errors — all logged to the observable trace."
          action={<Button variant="primary" icon="Play" onClick={start}>Run Full Pipeline</Button>}
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-12">
          {/* Left: DAG */}
          <Panel className="p-4 lg:col-span-3">
            <SectionTitle icon="Workflow">Workflow DAG</SectionTitle>
            <WorkflowDAG current={current} revisionCount={wf?.revisionCount ?? 0} />
          </Panel>

          {/* Center: agents + tools */}
          <div className="space-y-4 lg:col-span-5">
            <Panel className="p-4">
              <SectionTitle icon="Bot" right={<Badge tone="slate">{agentRuns.length} agent runs</Badge>}>
                Active Agents · Current Task
              </SectionTitle>
              {recentAgents.length === 0 ? (
                <div className="py-6 text-center text-xs text-slate-500">Awaiting first agent…</div>
              ) : (
                <div className="space-y-2">
                  {recentAgents.map((a) => (
                    <AgentCard key={a.id} run={a} />
                  ))}
                </div>
              )}
            </Panel>

            <Panel className="p-4">
              <SectionTitle icon="Plug" right={<Badge tone="slate">{toolRuns.length} tool calls</Badge>}>
                Tool Calls
              </SectionTitle>
              {recentTools.length === 0 ? (
                <div className="py-4 text-center text-xs text-slate-500">No tool calls yet.</div>
              ) : (
                <div className="grid gap-2 sm:grid-cols-2">
                  {recentTools.map((t) => (
                    <ToolRunCard key={t.id} run={t} />
                  ))}
                </div>
              )}
            </Panel>
          </div>

          {/* Right: audit trail */}
          <Panel className="p-4 lg:col-span-4">
            <SectionTitle icon="ScrollText" right={<Badge tone="cyan">{auditEvents.length} events</Badge>}>
              Observable Agent Trace
            </SectionTitle>
            <AuditTimeline events={auditEvents} dense />
          </Panel>
        </div>
      )}

      {/* Bottom console */}
      {(started || s.runScript.length > 0) && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Panel className="p-4 lg:col-span-2">
            <SectionTitle icon="Coins">Cost Ledger · 자원/비용 추적</SectionTitle>
            <CostLedger cost={wf?.totalEstimatedCost ?? 0} tokens={wf?.totalEstimatedTokens ?? 0} toolRuns={wf?.toolRunCount ?? toolRuns.length} latencyMs={totalLatency} />
            <div className="mt-3 grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg border border-line bg-bg-raised/50 p-2">
                <div className="text-[10px] uppercase text-slate-500">Caught errors</div>
                <div className="font-mono text-lg font-semibold text-helix-red">{wf?.errorCount ?? 0}</div>
              </div>
              <div className="rounded-lg border border-line bg-bg-raised/50 p-2">
                <div className="text-[10px] uppercase text-slate-500">Revisions</div>
                <div className="font-mono text-lg font-semibold text-helix-amber">{wf?.revisionCount ?? 0}</div>
              </div>
              <div className="rounded-lg border border-line bg-bg-raised/50 p-2">
                <div className="text-[10px] uppercase text-slate-500">Overall conf.</div>
                <div className="font-mono text-lg font-semibold text-brand-300">{Math.round((wf?.confidence ?? 0) * 100)}%</div>
              </div>
            </div>
          </Panel>
          <Panel className="p-4">
            <SectionTitle icon="TrendingUp">Confidence Trend</SectionTitle>
            <ConfidenceTrend agentRuns={agentRuns} />
            {runControl === 'complete' && (
              <Button variant="primary" icon="FileText" className="mt-3 w-full" onClick={() => navigate('/reports')}>
                Workflow complete — View Report
              </Button>
            )}
          </Panel>
        </div>
      )}
    </div>
  )
}
