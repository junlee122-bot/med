import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  AgentRun,
  AuditEvent,
  AppMode,
  BusinessAssumptions,
  CheckpointEntry,
  ClinicalProtocolDraft,
  DatasetEntry,
  DiscoveryGoal,
  EvaluationResult,
  EvidenceItem,
  Hypothesis,
  InjectionToggles,
  Language,
  MoleculeCandidate,
  MoleculeWeights,
  Project,
  RegulatoryCheck,
  Report,
  ReportType,
  SafetyFlag,
  TargetCandidate,
  TargetWeights,
  Theme,
  ToolDef,
  ToolRun,
  TrainingJob,
  UserSettings,
  WorkflowRun,
} from '@/types'
import {
  buildCheckpoints,
  buildClinical,
  buildDatasets,
  buildDemoProject,
  buildEvaluation,
  buildEvidence,
  buildHypotheses,
  buildMolecules,
  buildRegulatory,
  buildSafetyFlags,
  buildTargets,
  buildTrainingJobs,
  DEMO_PROJECT_ID,
} from '@/data/seedData'
import { TOOL_DEFS, SAFETY_POLICY_VERSION } from '@/lib/constants'
import { buildRunScript, Emission, newWorkflowRun } from '@/lib/workflowEngine'
import {
  DEFAULT_MOLECULE_WEIGHTS,
  DEFAULT_TARGET_WEIGHTS,
  clamp01,
  moleculeComposite,
  recommendationFor,
  targetScore,
} from '@/lib/scoring'
import { DEFAULT_BUSINESS } from '@/lib/business'
import { generateReport, ReportCtx } from '@/lib/reportTemplates'
import { screenMolecule } from '@/lib/safety'

const DEMO_WORKFLOW_ID = 'wf-demo-001'

function defaultSettings(): UserSettings {
  return {
    id: 'settings-1',
    language: 'ko',
    theme: 'dark',
    mode: 'demo',
    modelName: 'claude-orchestrator',
    effortLevel: 'high',
    temperature: 0.2,
    maxOutput: 8000,
    fallbackModel: 'claude-small',
    safetyPolicyVersion: SAFETY_POLICY_VERSION,
    apiKeyStatus: TOOL_DEFS.reduce((acc, t) => ({ ...acc, [t.id]: t.status }), {}),
    fastDemo: false,
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  }
}

function seededWorkflowRun(): WorkflowRun {
  return {
    id: DEMO_WORKFLOW_ID,
    projectId: DEMO_PROJECT_ID,
    mode: 'demo',
    status: 'success',
    currentStage: 'COMPLETE',
    startedAt: '2026-06-30T09:00:00.000Z',
    completedAt: '2026-06-30T09:02:10.000Z',
    totalEstimatedCost: 0.42,
    totalEstimatedTokens: 128400,
    toolRunCount: 22,
    safetyStatus: 'REVIEW_REQUIRED',
    confidence: 0.8,
    errorCount: 4,
    revisionCount: 4,
  }
}

function buildInitialData() {
  const project = buildDemoProject()
  project.currentWorkflowId = DEMO_WORKFLOW_ID
  const evidence = buildEvidence()
  const targets = buildTargets()
  const hypotheses = buildHypotheses()
  const molecules = buildMolecules()
  const safetyFlags = buildSafetyFlags(molecules)
  const top = molecules.filter((m) => m.recommendation === 'advance').sort((a, b) => b.compositeScore - a.compositeScore)[0] ?? molecules[0]
  const clinical = buildClinical(top.id, top.label)
  const regulatory = buildRegulatory()
  const evaluations = buildEvaluation(DEMO_WORKFLOW_ID)
  return { project, evidence, targets, hypotheses, molecules, safetyFlags, clinical, regulatory, evaluations }
}

function delay(ms: number) {
  return new Promise<void>((r) => setTimeout(r, Math.max(0, ms)))
}

function nowISO() {
  return new Date().toISOString()
}

export interface AppState {
  settings: UserSettings
  projects: Project[]
  activeProjectId: string
  workflows: WorkflowRun[]
  agentRuns: AgentRun[]
  toolRuns: ToolRun[]
  auditEvents: AuditEvent[]
  evidence: EvidenceItem[]
  targets: TargetCandidate[]
  hypotheses: Hypothesis[]
  molecules: MoleculeCandidate[]
  safetyFlags: SafetyFlag[]
  clinical: ClinicalProtocolDraft[]
  regulatory: RegulatoryCheck[]
  evaluations: EvaluationResult[]
  reports: Report[]
  trainingJobs: TrainingJob[]
  datasets: DatasetEntry[]
  checkpoints: CheckpointEntry[]
  tools: ToolDef[]
  targetWeights: TargetWeights
  moleculeWeights: MoleculeWeights
  injections: InjectionToggles
  business: BusinessAssumptions

  // playback (not persisted)
  runScript: Emission[]
  runCursor: number
  runControl: 'idle' | 'running' | 'paused' | 'complete'
  currentWorkflowId: string | null

  // actions
  resetDemoData: () => void
  patchSettings: (p: Partial<UserSettings>) => void
  setMode: (m: AppMode) => void
  setLanguage: (l: Language) => void
  setTheme: (t: Theme) => void
  setActiveProject: (id: string) => void
  createProject: (input: {
    name: string
    disease: string
    indication: string
    patientPopulation: string
    unmetNeed: string
    discoveryGoal: DiscoveryGoal
    mode: AppMode
    scientificConstraints?: Partial<Project['scientificConstraints']>
    safetyConstraints?: Partial<Project['safetyConstraints']>
    evaluationPlan?: Partial<Project['evaluationPlan']>
  }) => string
  deleteProject: (id: string) => void

  startWorkflow: (projectId: string, fast?: boolean) => void
  pauseWorkflow: () => void
  resumeWorkflow: () => void
  stepWorkflow: () => void
  stopWorkflow: () => void

  setInjection: (k: keyof InjectionToggles, v: boolean) => void
  setTargetWeights: (w: TargetWeights) => void
  setMoleculeWeights: (w: MoleculeWeights) => void
  recomputeScores: () => void
  runSafetyAudit: () => void
  setBusiness: (b: BusinessAssumptions) => void
  testTool: (id: string) => void
  setToolMode: (id: string, mode: AppMode) => void

  buildReport: (type: ReportType) => Report
  removeReport: (id: string) => void

  startTrainingJob: (id: string) => void

  activeProject: () => Project | undefined
  activeWorkflow: () => WorkflowRun | undefined
  reportCtx: () => ReportCtx
}

const init = buildInitialData()

function applyEmission(
  em: Emission,
  set: (fn: (s: AppState) => Partial<AppState>) => void,
  wfId: string,
) {
  if (em.kind === 'agent') {
    const a = { ...em.agent, startedAt: nowISO(), completedAt: em.agent.completedAt === undefined ? undefined : nowISO() }
    set((s) => ({ agentRuns: [...s.agentRuns, a] }))
  } else if (em.kind === 'tool') {
    const t = { ...em.tool, startedAt: nowISO(), completedAt: nowISO() }
    set((s) => ({ toolRuns: [...s.toolRuns, t] }))
  } else if (em.kind === 'event') {
    set((s) => ({ auditEvents: [...s.auditEvents, { ...em.event, ts: nowISO() }] }))
  } else if (em.kind === 'run') {
    const patch = { ...em.patch }
    if (patch.startedAt === '') patch.startedAt = nowISO()
    if (patch.completedAt === '') patch.completedAt = nowISO()
    set((s) => ({ workflows: s.workflows.map((w) => (w.id === wfId ? { ...w, ...patch } : w)) }))
  } else if (em.kind === 'stage') {
    set((s) => ({ workflows: s.workflows.map((w) => (w.id === wfId ? { ...w, currentStage: em.stage } : w)) }))
  }
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => {
      const play = async () => {
        for (;;) {
          const { runControl, runScript, runCursor, currentWorkflowId } = get()
          if (runControl !== 'running') return
          if (runCursor >= runScript.length) {
            set((s) => ({
              runControl: 'complete',
              projects: s.projects.map((p) => (p.id === s.activeProjectId ? { ...p, status: 'complete' } : p)),
            }))
            return
          }
          const em = runScript[runCursor]
          await delay(em.delay)
          if (get().runControl !== 'running') return
          applyEmission(em, set as never, currentWorkflowId!)
          set((s) => ({ runCursor: s.runCursor + 1 }))
        }
      }
      return {
      settings: defaultSettings(),
      projects: [init.project],
      activeProjectId: DEMO_PROJECT_ID,
      workflows: [seededWorkflowRun()],
      agentRuns: [],
      toolRuns: [],
      auditEvents: [],
      evidence: init.evidence,
      targets: init.targets,
      hypotheses: init.hypotheses,
      molecules: init.molecules,
      safetyFlags: init.safetyFlags,
      clinical: [init.clinical],
      regulatory: init.regulatory,
      evaluations: init.evaluations,
      reports: [],
      trainingJobs: buildTrainingJobs(),
      datasets: buildDatasets(),
      checkpoints: buildCheckpoints(),
      tools: TOOL_DEFS,
      targetWeights: DEFAULT_TARGET_WEIGHTS,
      moleculeWeights: DEFAULT_MOLECULE_WEIGHTS,
      injections: {
        invalidSmiles: true,
        fakeCitation: true,
        contradictoryEvidence: true,
        toolFailure: false,
        safetyHazard: true,
        overclaim: false,
      },
      business: DEFAULT_BUSINESS,

      runScript: [],
      runCursor: 0,
      runControl: 'idle',
      currentWorkflowId: null,

      resetDemoData: () => {
        const d = buildInitialData()
        d.project.currentWorkflowId = DEMO_WORKFLOW_ID
        set({
          projects: [d.project],
          activeProjectId: DEMO_PROJECT_ID,
          workflows: [seededWorkflowRun()],
          agentRuns: [],
          toolRuns: [],
          auditEvents: [],
          evidence: d.evidence,
          targets: d.targets,
          hypotheses: d.hypotheses,
          molecules: d.molecules,
          safetyFlags: d.safetyFlags,
          clinical: [d.clinical],
          regulatory: d.regulatory,
          evaluations: d.evaluations,
          reports: [],
          trainingJobs: buildTrainingJobs(),
          datasets: buildDatasets(),
          checkpoints: buildCheckpoints(),
          runScript: [],
          runCursor: 0,
          runControl: 'idle',
          currentWorkflowId: null,
        })
      },

      patchSettings: (p) =>
        set((s) => ({ settings: { ...s.settings, ...p, updatedAt: nowISO() } })),
      setMode: (m) => set((s) => ({ settings: { ...s.settings, mode: m, updatedAt: nowISO() } })),
      setLanguage: (l) => set((s) => ({ settings: { ...s.settings, language: l, updatedAt: nowISO() } })),
      setTheme: (t) => set((s) => ({ settings: { ...s.settings, theme: t, updatedAt: nowISO() } })),
      setActiveProject: (id) => set({ activeProjectId: id }),

      createProject: (inp) => {
        const id = `proj-${Date.now().toString(36)}`
        const project: Project = {
          id,
          name: inp.name || 'Untitled Project',
          disease: inp.disease,
          indication: inp.indication,
          patientPopulation: inp.patientPopulation,
          unmetNeed: inp.unmetNeed,
          discoveryGoal: inp.discoveryGoal,
          mode: inp.mode,
          status: 'ready',
          scientificConstraints: {
            knownTargets: [],
            excludedTargets: [],
            mechanismPreferences: [],
            biomarkerRequirements: [],
            modality: 'small_molecule',
            ...inp.scientificConstraints,
          },
          safetyConstraints: {
            excludeControlled: true,
            excludeHighToxicityOptimization: true,
            noSynthesisRecipe: true,
            humanReviewRequired: true,
            ...inp.safetyConstraints,
          },
          evaluationPlan: {
            retrospectiveRediscovery: true,
            tdcAdmet: true,
            dockingEnrichment: true,
            citationVerification: true,
            selfCorrection: true,
            costLatency: true,
            ...inp.evaluationPlan,
          },
          createdAt: nowISO(),
          updatedAt: nowISO(),
          owner: 'you@helixforge.ai',
          summary: `New project targeting ${inp.disease}. Scientific dataset seeded as Demo Simulation for immediate exploration.`,
          humanResponsibilityAccepted: true,
          seeded: false,
        }
        set((s) => ({ projects: [...s.projects, project], activeProjectId: id }))
        return id
      },

      deleteProject: (id) => {
        if (id === DEMO_PROJECT_ID) return
        set((s) => ({
          projects: s.projects.filter((p) => p.id !== id),
          activeProjectId: s.activeProjectId === id ? DEMO_PROJECT_ID : s.activeProjectId,
        }))
      },

      startWorkflow: (projectId, fast) => {
        const s = get()
        const project = s.projects.find((p) => p.id === projectId) ?? s.projects[0]
        const wfId = `wf-${Date.now().toString(36)}`
        const wf = newWorkflowRun(wfId, project.id, s.settings.mode)
        const script = buildRunScript(
          {
            workflowId: wfId,
            project,
            injections: s.injections,
            molecules: s.molecules,
            evidence: s.evidence,
            targets: s.targets,
            mode: s.settings.mode,
          },
          fast ?? s.settings.fastDemo,
        )
        set((st) => ({
          workflows: [wf, ...st.workflows.filter((w) => w.id !== wfId)],
          agentRuns: st.agentRuns.filter((a) => a.workflowId !== wfId),
          toolRuns: st.toolRuns.filter((t) => t.workflowId !== wfId),
          auditEvents: st.auditEvents.filter((e) => e.workflowId !== wfId),
          projects: st.projects.map((p) => (p.id === project.id ? { ...p, currentWorkflowId: wfId, status: 'running' } : p)),
          runScript: script,
          runCursor: 0,
          runControl: 'running',
          currentWorkflowId: wfId,
          activeProjectId: project.id,
        }))
        void play()
      },

      pauseWorkflow: () => {
        if (get().runControl === 'running') set({ runControl: 'paused' })
      },
      resumeWorkflow: () => {
        if (get().runControl === 'paused') {
          set({ runControl: 'running' })
          void play()
        }
      },
      stepWorkflow: () => {
        const st = get()
        if (st.runScript.length === 0 || st.runCursor >= st.runScript.length) return
        if (st.runControl === 'running') return
        applyEmission(st.runScript[st.runCursor], set as never, st.currentWorkflowId!)
        set((s) => ({ runControl: 'paused', runCursor: s.runCursor + 1 }))
        if (get().runCursor >= get().runScript.length) set({ runControl: 'complete' })
      },
      stopWorkflow: () => set({ runControl: 'idle', runScript: [], runCursor: 0 }),

      setInjection: (k, v) => set((s) => ({ injections: { ...s.injections, [k]: v } })),

      setTargetWeights: (w) => {
        set({ targetWeights: w })
        get().recomputeScores()
      },
      setMoleculeWeights: (w) => {
        set({ moleculeWeights: w })
        get().recomputeScores()
      },

      recomputeScores: () => {
        const s = get()
        const targets = s.targets
          .map((t) => ({ ...t, score: targetScore(t, s.targetWeights) }))
          .sort((a, b) => b.score - a.score)
          .map((t, i) => ({ ...t, rank: i + 1 }))
        const molecules = s.molecules.map((m) => {
          if (m.validityStatus !== 'valid') return m
          const composite = moleculeComposite(
            {
              bindingNormalized: m.bindingNormalized,
              admetScore: m.admetScore,
              qed: m.qed,
              lipinskiPass: m.lipinskiPass,
              lipinskiViolations: m.lipinskiViolations,
              synthesisFeasibility: m.synthesisFeasibility,
              novelty: m.novelty,
              targetRationale: 0.82,
              confidence: 1 - m.uncertainty,
              uncertainty: m.uncertainty,
              safetyStatus: m.safetyStatus,
            },
            s.moleculeWeights,
          )
          const recommendation = recommendationFor({
            compositeScore: composite,
            safetyStatus: m.safetyStatus,
            uncertainty: m.uncertainty,
            validityStatus: m.validityStatus,
          })
          return { ...m, compositeScore: composite, recommendation }
        })
        set({ targets, molecules })
      },

      runSafetyAudit: () => {
        const s = get()
        const molecules = s.molecules.map((m) => {
          if (m.validityStatus !== 'valid') return m
          const forceHazard = s.injections.safetyHazard && (m.label === 'HF-EGFR-008' || m.label === 'HF-EGFR-010')
          const screen = screenMolecule({ hERG: m.hERG, Ames: m.Ames, DILI: m.DILI, label: m.label, forceHazard })
          return { ...m, safetyStatus: screen.status }
        })
        set({ molecules })
        set((st) => ({ safetyFlags: buildSafetyFlags(molecules) }))
        get().recomputeScores()
      },

      setBusiness: (b) => set({ business: b }),

      testTool: (id) =>
        set((s) => ({
          tools: s.tools.map((t) =>
            t.id === id
              ? {
                  ...t,
                  lastRun: nowISO(),
                  lastError: undefined,
                  status:
                    s.settings.mode === 'real' && (t.requiredConfig.length === 0 || t.status === 'connected')
                      ? 'connected'
                      : t.status === 'missing_key'
                        ? 'demo_fallback'
                        : t.status,
                }
              : t,
          ),
        })),

      setToolMode: (id, mode) =>
        set((s) => ({ tools: s.tools.map((t) => (t.id === id ? { ...t, mode } : t)) })),

      buildReport: (type) => {
        const ctx = get().reportCtx()
        const report = generateReport(type, ctx)
        set((s) => ({ reports: [report, ...s.reports.filter((r) => r.type !== type)] }))
        return report
      },
      removeReport: (id) => set((s) => ({ reports: s.reports.filter((r) => r.id !== id) })),

      startTrainingJob: (id) => {
        set((s) => ({ trainingJobs: s.trainingJobs.map((j) => (j.id === id ? { ...j, status: 'running', progress: 0 } : j)) }))
        const tick = async () => {
          for (let p = 0; p <= 100; p += 10) {
            await delay(get().settings.fastDemo ? 40 : 260)
            const done = p >= 100
            set((s) => ({
              trainingJobs: s.trainingJobs.map((j) =>
                j.id === id
                  ? {
                      ...j,
                      progress: p,
                      status: done ? 'complete' : 'running',
                      completedAt: done ? nowISO() : j.completedAt,
                      logs: done ? [...j.logs, '[demo] run complete', 'Demo Simulation — no model was actually trained.'] : j.logs,
                    }
                  : j,
              ),
            }))
          }
        }
        void tick()
      },

      activeProject: () => get().projects.find((p) => p.id === get().activeProjectId),
      activeWorkflow: () => {
        const s = get()
        const p = s.projects.find((pr) => pr.id === s.activeProjectId)
        if (p?.currentWorkflowId) return s.workflows.find((w) => w.id === p.currentWorkflowId)
        return s.workflows.find((w) => w.projectId === s.activeProjectId)
      },
      reportCtx: () => {
        const s = get()
        const project = s.projects.find((p) => p.id === s.activeProjectId) ?? s.projects[0]
        return {
          project,
          evidence: s.evidence,
          targets: s.targets,
          hypotheses: s.hypotheses,
          molecules: s.molecules,
          safetyFlags: s.safetyFlags,
          clinical: s.clinical[0],
          regulatory: s.regulatory,
          evaluations: s.evaluations,
          workflow: s.activeWorkflow(),
          business: s.business,
        }
      },
      }
    },
    {
      name: 'helixforge-store-v1',
      partialize: (s) => {
        const { runScript, runCursor, runControl, ...rest } = s
        return rest as AppState
      },
      version: 1,
    },
  ),
)
