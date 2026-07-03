import type {
  AgentName,
  AgentRun,
  AuditEvent,
  EvidenceItem,
  InjectionToggles,
  MoleculeCandidate,
  Project,
  TargetCandidate,
  ToolRun,
  WorkflowRun,
  WorkflowStage,
  AppMode,
} from '@/types'
import { PIPELINE_STAGES, STAGE_MAP } from '@/lib/constants'

// ============================================================================
// Workflow engine (Sections 8 / 14 / 15).
// Builds an ordered list of "emissions" that the store plays back with
// pause / resume / step controls. Every emission is a small observable unit:
// a stage transition, an agent action, a tool call, a validation, or a
// revision. Injected errors add correction loops.
// ============================================================================

export type Emission =
  | { kind: 'stage'; stage: WorkflowStage; delay: number }
  | { kind: 'agent'; stage: WorkflowStage; delay: number; agent: AgentRun }
  | { kind: 'tool'; stage: WorkflowStage; delay: number; tool: ToolRun }
  | { kind: 'event'; stage: WorkflowStage; delay: number; event: AuditEvent }
  | { kind: 'run'; stage: WorkflowStage; delay: number; patch: Partial<WorkflowRun> }

export interface EngineCtx {
  workflowId: string
  project: Project
  injections: InjectionToggles
  molecules: MoleculeCandidate[]
  evidence: EvidenceItem[]
  targets: TargetCandidate[]
  mode: AppMode
}

let _seq = 0
function nid(prefix: string) {
  _seq += 1
  return `${prefix}-${_seq}`
}

const PLACEHOLDER = ''

function mkAgent(
  wf: string,
  stage: WorkflowStage,
  agentName: AgentName,
  status: AgentRun['status'],
  inputSummary: string,
  outputSummary: string,
  opts: Partial<AgentRun> = {},
): AgentRun {
  return {
    id: nid('ar'),
    workflowId: wf,
    agentName,
    stage,
    status,
    inputSummary,
    outputSummary,
    confidence: opts.confidence ?? 0.8,
    startedAt: PLACEHOLDER,
    completedAt: status === 'running' ? undefined : PLACEHOLDER,
    validationStatus: opts.validationStatus ?? 'passed',
    evidenceIds: opts.evidenceIds ?? [],
    toolRunIds: opts.toolRunIds ?? [],
    warnings: opts.warnings ?? [],
    revisionOf: opts.revisionOf,
    isRevision: opts.isRevision,
  }
}

function mkTool(
  wf: string,
  agentRunId: string,
  stage: WorkflowStage,
  toolName: string,
  toolCategory: string,
  mode: AppMode,
  status: ToolRun['status'],
  inputSummary: string,
  outputSummary: string,
  opts: Partial<ToolRun> = {},
): ToolRun {
  return {
    id: nid('tr'),
    workflowId: wf,
    agentRunId,
    toolName,
    toolCategory,
    mode,
    status,
    inputSummary,
    outputSummary,
    error: opts.error,
    startedAt: PLACEHOLDER,
    completedAt: PLACEHOLDER,
    latencyMs: opts.latencyMs ?? 400,
    costEstimate: opts.costEstimate ?? 0.004,
    sourceType: opts.sourceType ?? (mode === 'real' ? 'real' : 'demo'),
    validationStatus: opts.validationStatus ?? 'passed',
  }
}

function mkEvent(
  wf: string,
  stage: WorkflowStage,
  type: AuditEvent['type'],
  title: string,
  detail: string,
  opts: Partial<AuditEvent> = {},
): AuditEvent {
  return {
    id: nid('ev'),
    workflowId: wf,
    ts: PLACEHOLDER,
    type,
    stage,
    agent: opts.agent,
    tool: opts.tool,
    title,
    detail,
    sourceType: opts.sourceType,
    validationStatus: opts.validationStatus,
    safetyStatus: opts.safetyStatus,
    confidence: opts.confidence,
    evidenceIds: opts.evidenceIds,
  }
}

// ---------------------------------------------------------------------------
// Build the full run script.
// ---------------------------------------------------------------------------
export function buildRunScript(ctx: EngineCtx, fastDemo: boolean): Emission[] {
  _seq = 0
  const wf = ctx.workflowId
  const mode = ctx.mode
  const inj = ctx.injections
  const D = (ms: number) => (fastDemo ? Math.min(60, Math.round(ms * 0.12)) : ms)
  const out: Emission[] = []
  let cost = 0
  let tokens = 0
  let toolCount = 0
  let errorCount = 0
  let revisionCount = 0
  let confidence = 0.9

  const push = (e: Emission) => out.push(e)
  const runPatch = (stage: WorkflowStage, extra: Partial<WorkflowRun> = {}) =>
    push({
      kind: 'run',
      stage,
      delay: 0,
      patch: {
        currentStage: stage,
        totalEstimatedCost: Math.round(cost * 1000) / 1000,
        totalEstimatedTokens: tokens,
        toolRunCount: toolCount,
        errorCount,
        revisionCount,
        confidence: Math.round(confidence * 100) / 100,
        ...extra,
      },
    })

  const invalidMols = ctx.molecules.filter((m) => m.validityStatus === 'invalid')
  const blockedMols = ctx.molecules.filter((m) => m.safetyStatus === 'BLOCKED')
  const reviewMols = ctx.molecules.filter((m) => m.safetyStatus === 'REVIEW_REQUIRED')
  const validMols = ctx.molecules.filter((m) => m.validityStatus === 'valid')
  const topTarget = ctx.targets[0]

  // Emit an agent + optional tool + audit event grouped for a stage.
  function emitAgent(
    stage: WorkflowStage,
    agentName: AgentName,
    input: string,
    output: string,
    opts: {
      tools?: { name: string; cat: string; input: string; output: string; status?: ToolRun['status']; source?: ToolRun['sourceType']; error?: string; latency?: number; cost?: number; validation?: ToolRun['validationStatus'] }[]
      confidence?: number
      validation?: AgentRun['validationStatus']
      warnings?: string[]
      evidenceIds?: string[]
      isRevision?: boolean
      delay?: number
    } = {},
  ) {
    const agent = mkAgent(wf, stage, agentName, 'success', input, output, {
      confidence: opts.confidence ?? confidence,
      validationStatus: opts.validation ?? 'passed',
      warnings: opts.warnings,
      evidenceIds: opts.evidenceIds,
      isRevision: opts.isRevision,
    })
    push({ kind: 'agent', stage, delay: D(opts.delay ?? 520), agent })
    for (const tdef of opts.tools ?? []) {
      toolCount += 1
      const latency = tdef.latency ?? 500
      const c = tdef.cost ?? 0.004
      cost += c
      tokens += Math.round(latency * 1.4)
      const tool = mkTool(wf, agent.id, stage, tdef.name, tdef.cat, mode, tdef.status ?? 'success', tdef.input, tdef.output, {
        sourceType: tdef.source ?? (mode === 'real' ? 'real' : 'demo'),
        error: tdef.error,
        latencyMs: latency,
        costEstimate: c,
        validationStatus: tdef.validation ?? 'passed',
      })
      agent.toolRunIds.push(tool.id)
      push({ kind: 'tool', stage, delay: D(260), tool })
      push({
        kind: 'event',
        stage,
        delay: D(60),
        event: mkEvent(wf, stage, 'tool', `${tdef.name} · ${tdef.status === 'error' ? 'ERROR' : (tdef.source ?? mode) === 'real' ? 'Real Tool Output' : 'Demo Simulation'}`, `${tdef.input} → ${tdef.output}`, {
          agent: agentName,
          tool: tdef.name,
          sourceType: tool.sourceType,
          validationStatus: tool.validationStatus,
        }),
      })
    }
    push({
      kind: 'event',
      stage,
      delay: D(90),
      event: mkEvent(wf, stage, 'agent', `${agentName} · ${opts.isRevision ? 'revision' : STAGE_MAP[stage].label}`, output, {
        agent: agentName,
        confidence: opts.confidence ?? confidence,
        validationStatus: opts.validation ?? 'passed',
        evidenceIds: opts.evidenceIds,
      }),
    })
    tokens += 900
    return agent
  }

  // ---- Start ----
  push({ kind: 'run', stage: 'PLANNING', delay: 0, patch: { status: 'running', currentStage: 'PLANNING', startedAt: PLACEHOLDER } })

  // Stage: PLANNING
  push({ kind: 'stage', stage: 'PLANNING', delay: D(200) })
  emitAgent('PLANNING', 'Project Orchestrator',
    `Goal: ${ctx.project.discoveryGoal} · disease: ${ctx.project.disease}`,
    `Decomposed goal into a ${PIPELINE_STAGES.length}-stage DAG and assigned specialized agents. Verified required artifacts gate each transition.`,
    { tools: [{ name: 'Planner', cat: 'orchestration', input: 'project goal + constraints', output: `${PIPELINE_STAGES.length}-node DAG`, source: 'demo', latency: 300, cost: 0.002 }], confidence: 0.9, delay: 400 })
  runPatch('PLANNING')

  // Stage: EVIDENCE_MINING
  push({ kind: 'stage', stage: 'EVIDENCE_MINING', delay: D(150) })
  emitAgent('EVIDENCE_MINING', 'Evidence Miner',
    `Query: ${ctx.project.disease} / EGFR mechanisms & precedent`,
    `Retrieved ${ctx.evidence.length} evidence items; separated ${ctx.evidence.filter((e) => e.evidenceDirection === 'supports').length} supporting / ${ctx.evidence.filter((e) => e.evidenceDirection === 'contradicts').length} contradictory. Demo placeholders labeled.`,
    {
      tools: [
        { name: 'PubMed Adapter', cat: 'literature', input: `"${ctx.project.disease} EGFR"`, output: `${ctx.evidence.length} records`, source: mode === 'real' ? 'fallback' : 'demo', latency: 640, cost: 0.006 },
        { name: 'Europe PMC Adapter', cat: 'literature', input: 'CNS penetration; resistance', output: '2 records', source: 'demo', latency: 420, cost: 0.004 },
      ],
      confidence: 0.82,
      evidenceIds: ctx.evidence.map((e) => e.id),
    })
  if (inj.contradictoryEvidence) {
    revisionCount += 1
    emitAgent('EVIDENCE_MINING', 'Evidence Miner',
      'Critic requested counter-evidence for balance',
      'Added contradictory record (ev-007): subgroup non-response + toxicity signal. Target confidence will be recalculated; uncertainty retained in report.',
      { isRevision: true, confidence: 0.78, warnings: ['Contradictory evidence present — uncertainty represented, not hidden'], evidenceIds: ['ev-007'], delay: 380 })
    push({ kind: 'event', stage: 'EVIDENCE_MINING', delay: D(60), event: mkEvent(wf, 'EVIDENCE_MINING', 'revision', 'Revision · contradictory evidence added', 'Counter-evidence incorporated; downstream target confidence reduced.', { agent: 'Critic / Verifier Agent' }) })
  }
  // Citation verification (fake citation correction)
  if (inj.fakeCitation) {
    errorCount += 1
    revisionCount += 1
    confidence -= 0.04
    emitAgent('EVIDENCE_MINING', 'Evidence Miner',
      'Citation Verifier cross-check on all identifiers',
      'Verifier FAILED PMID:00000000 (unresolvable). Demoted to failed; excluded from verified evidence. Replaced with a labeled demo placeholder; hypothesis confidence reduced.',
      {
        tools: [{ name: 'Citation Verifier', cat: 'literature', input: 'PMID:00000000', output: 'status=failed (unresolvable)', status: 'error', source: 'demo', error: 'Identifier not resolved', latency: 180, cost: 0.001, validation: 'failed' }],
        isRevision: true, validation: 'warning', confidence: 0.78, warnings: ['Fabricated citation rejected'], delay: 420,
      })
    push({ kind: 'event', stage: 'EVIDENCE_MINING', delay: D(60), event: mkEvent(wf, 'EVIDENCE_MINING', 'safety', 'Safety · fabricated citation blocked', 'Citation honesty enforced: unverifiable reference cannot enter a report as verified.', { agent: 'Safety Auditor', safetyStatus: 'REVIEW_REQUIRED' }) })
  }
  runPatch('EVIDENCE_MINING')

  // Stage: DISEASE_MODELING
  push({ kind: 'stage', stage: 'DISEASE_MODELING', delay: D(150) })
  emitAgent('DISEASE_MODELING', 'Disease Biology Agent',
    `Frame biology for ${ctx.project.disease}`,
    'Built disease model: driver pathways, phenotypes, biomarker landscape (EGFR alteration status, ctDNA). Assumptions labeled; evidence IDs attached.',
    { tools: [{ name: 'Knowledge Graph Adapter', cat: 'biology', input: 'disease→pathway→target', output: 'graph: 14 nodes / 21 edges', source: 'demo', latency: 520, cost: 0.005 }], confidence: 0.8, evidenceIds: ['ev-001', 'ev-003'] })
  runPatch('DISEASE_MODELING')

  // Stage: TARGET_RANKING
  push({ kind: 'stage', stage: 'TARGET_RANKING', delay: D(150) })
  emitAgent('TARGET_RANKING', 'Target Scout',
    'Rank targets by relevance/tractability/novelty/safety/precedent',
    `Ranked ${ctx.targets.length} targets. Top: ${topTarget?.symbol} (${topTarget?.score}/100). Each ranked target has ≥1 evidence path; ALK retained as exploratory.`,
    {
      tools: [
        { name: 'Open Targets Adapter', cat: 'biology', input: `${ctx.project.disease}`, output: 'association scores', source: 'demo', latency: 600, cost: 0.006 },
        { name: 'ChEMBL Target Adapter', cat: 'biology', input: 'EGFR/MET/KRAS...', output: 'tractability signal', source: 'demo', latency: 480, cost: 0.004 },
      ],
      confidence: inj.contradictoryEvidence ? 0.76 : 0.83,
      evidenceIds: ['ev-002', 'ev-004'],
      warnings: inj.contradictoryEvidence ? ['Confidence reduced by contradictory evidence'] : [],
    })
  runPatch('TARGET_RANKING')

  // Stage: HYPOTHESIS_GENERATION
  push({ kind: 'stage', stage: 'HYPOTHESIS_GENERATION', delay: D(150) })
  emitAgent('HYPOTHESIS_GENERATION', 'Hypothesis Generator',
    'Convert evidence into testable high-level hypotheses',
    'Generated 3 hypotheses (mutant-selective CNS-penetrant inhibitor; MET co-targeting; ctDNA biomarker). Explicit uncertainty; no wet-lab validation claimed.',
    { confidence: 0.72, evidenceIds: ['ev-001', 'ev-002', 'ev-003'] })
  if (inj.overclaim) {
    revisionCount += 1
    emitAgent('HYPOTHESIS_GENERATION', 'Critic / Verifier Agent',
      'Language audit on hypothesis phrasing',
      'Detected overclaim ("validated cure"/"proven efficacy"). Rewrote to "in-silico hypothesis for expert review". Audit log records the language correction.',
      { isRevision: true, validation: 'warning', confidence: 0.7, warnings: ['Overclaim rewritten'], delay: 360 })
    push({ kind: 'event', stage: 'HYPOTHESIS_GENERATION', delay: D(60), event: mkEvent(wf, 'HYPOTHESIS_GENERATION', 'revision', 'Revision · overclaim corrected', 'Report Builder will use the corrected, non-overstated phrasing.', { agent: 'Critic / Verifier Agent' }) })
  }
  runPatch('HYPOTHESIS_GENERATION')

  // Stage: MOLECULE_GENERATION
  push({ kind: 'stage', stage: 'MOLECULE_GENERATION', delay: D(150) })
  emitAgent('MOLECULE_GENERATION', 'Molecular Design Agent',
    `Generate candidates for ${topTarget?.symbol} under safety constraints`,
    `Generated ${ctx.molecules.length} candidates (safe demo structures). Source labeled; hazardous chemical space excluded by scoring.`,
    { tools: [{ name: 'REINVENT4 Adapter', cat: 'chemistry', input: `target=${topTarget?.symbol}, weights, safety=on`, output: `${ctx.molecules.length} SMILES`, source: mode === 'real' ? 'fallback' : 'demo', latency: 2400, cost: 0.12 }], confidence: 0.8 })
  runPatch('MOLECULE_GENERATION')

  // Stage: STRUCTURE_VALIDATION (invalid SMILES correction)
  push({ kind: 'stage', stage: 'STRUCTURE_VALIDATION', delay: D(150) })
  emitAgent('STRUCTURE_VALIDATION', 'Cheminformatics Validator',
    'Validate all SMILES; compute descriptors (RDKit)',
    `${validMols.length}/${ctx.molecules.length} passed the SMILES validity gate. Descriptors, QED, and Lipinski computed for valid structures.`,
    { tools: [{ name: 'RDKit Adapter', cat: 'chemistry', input: `${ctx.molecules.length} SMILES`, output: `${validMols.length} valid / ${invalidMols.length} invalid`, source: 'demo', latency: 700, cost: 0.003 }], confidence: 0.85 })
  if (inj.invalidSmiles && invalidMols.length > 0) {
    errorCount += invalidMols.length
    revisionCount += 1
    for (const m of invalidMols) {
      push({ kind: 'event', stage: 'STRUCTURE_VALIDATION', delay: D(90), event: mkEvent(wf, 'STRUCTURE_VALIDATION', 'validation', `Validation FAILED · ${m.label}`, `Invalid SMILES rejected (${m.validityReason}). Cannot enter ranking.`, { agent: 'Cheminformatics Validator', validationStatus: 'failed' }) })
    }
    emitAgent('STRUCTURE_VALIDATION', 'Molecular Design Agent',
      `Critic requested regeneration of ${invalidMols.length} invalid candidate(s)`,
      `Regenerated ${invalidMols.length} replacement candidate(s); Validator re-checked and accepted. Correction recorded in the audit trail.`,
      { isRevision: true, confidence: 0.83, warnings: [`${invalidMols.length} invalid structures corrected`], delay: 520 })
    push({ kind: 'event', stage: 'STRUCTURE_VALIDATION', delay: D(60), event: mkEvent(wf, 'STRUCTURE_VALIDATION', 'revision', 'Revision · invalid structures regenerated', 'Molecular Design Agent → Cheminformatics Validator loop closed.', { agent: 'Critic / Verifier Agent' }) })
  }
  runPatch('STRUCTURE_VALIDATION')

  // Stage: DOCKING (tool failure correction)
  push({ kind: 'stage', stage: 'DOCKING_OR_BINDING_ESTIMATION', delay: D(150) })
  const dockTools = [{ name: 'AutoDock Vina Adapter', cat: 'structure', input: `receptor=EGFR, ${validMols.length} ligands`, output: 'affinity + pose confidence (Demo Simulation)', source: (mode === 'real' ? 'fallback' : 'demo') as ToolRun['sourceType'], latency: 1800, cost: 0.02 }]
  emitAgent('DOCKING_OR_BINDING_ESTIMATION', 'Binding & Structure Agent',
    'Estimate binding & structural plausibility',
    `Estimated binding for ${validMols.length} valid candidates. Values labeled Demo Simulation; docking failures reduce confidence.`,
    { tools: dockTools, confidence: 0.74 })
  if (inj.toolFailure) {
    errorCount += 1
    emitAgent('DOCKING_OR_BINDING_ESTIMATION', 'Project Orchestrator',
      'Docking worker returned ERROR (simulated outage)',
      'Retried once; external docking unavailable → fell back to Demo Mode for this tool only. Audit records the fallback; no fake real result is presented.',
      {
        tools: [{ name: 'AutoDock Vina Adapter', cat: 'structure', input: 'retry', output: 'endpoint unavailable', status: 'error', source: 'fallback', error: 'HTTP 503 docking worker', latency: 900, cost: 0.0, validation: 'failed' }],
        isRevision: true, validation: 'warning', confidence: 0.68, warnings: ['Tool fallback to demo — provenance preserved'], delay: 480,
      })
    push({ kind: 'event', stage: 'DOCKING_OR_BINDING_ESTIMATION', delay: D(60), event: mkEvent(wf, 'DOCKING_OR_BINDING_ESTIMATION', 'error', 'Tool error · graceful fallback', 'Missing tool never silently pretended used; fallback labeled.', { agent: 'Project Orchestrator', sourceType: 'fallback' }) })
  }
  runPatch('DOCKING_OR_BINDING_ESTIMATION')

  // Stage: ADMET_SCREENING
  push({ kind: 'stage', stage: 'ADMET_SCREENING', delay: D(150) })
  emitAgent('ADMET_SCREENING', 'ADMET & Toxicology Agent',
    'Predict PK/tox risks (hERG/Ames/DILI/CYP/BBB/solubility/clearance)',
    `Scored ${validMols.length} candidates. ${reviewMols.length} flagged high/borderline risk → routed to Safety Auditor. Uncertainty reported per endpoint.`,
    { tools: [{ name: 'TDC / ChemProp Adapter', cat: 'chemistry', input: `${validMols.length} molecules`, output: 'endpoint predictions + uncertainty', source: mode === 'real' ? 'fallback' : 'demo', latency: 900, cost: 0.018 }], confidence: 0.75, warnings: reviewMols.length ? [`${reviewMols.length} high-risk candidates escalated`] : [] })
  runPatch('ADMET_SCREENING')

  // Stage: SYNTHESIS_FEASIBILITY
  push({ kind: 'stage', stage: 'SYNTHESIS_FEASIBILITY', delay: D(150) })
  emitAgent('SYNTHESIS_FEASIBILITY', 'Synthesis Feasibility Agent',
    'Estimate synthetic feasibility (score only)',
    'Feasibility scored (High/Medium/Low) with route confidence & estimated complexity. NO route steps, reagents, or conditions displayed — by policy. Expert review required.',
    { tools: [{ name: 'AiZynthFinder Adapter', cat: 'synthesis', input: `${validMols.length} molecules`, output: 'feasibility score only', source: mode === 'real' ? 'fallback' : 'demo', latency: 1100, cost: 0.006 }], confidence: 0.7 })
  runPatch('SYNTHESIS_FEASIBILITY')

  // Stage: SAFETY_AUDIT (safety hazard correction)
  push({ kind: 'stage', stage: 'SAFETY_AUDIT', delay: D(150) })
  const blockedCount = inj.safetyHazard ? blockedMols.length : 0
  emitAgent('SAFETY_AUDIT', 'Safety Auditor',
    'Screen candidates & outputs for hazard/dual-use/controlled classes',
    blockedCount > 0
      ? `Blocked/quarantined ${blockedCount} candidate(s). Reason category shown without actionable detail. Blocked items cannot enter the clinical/regulatory package.`
      : 'No hazardous-material or dual-use trigger in current candidate set. Toxicity screened defensively, never optimized.',
    {
      tools: [
        { name: 'Controlled Chemical Screen', cat: 'safety', input: `${validMols.length} candidates`, output: blockedCount > 0 ? `${blockedCount} BLOCKED` : 'PASS', source: 'demo', latency: 300, cost: 0.001, validation: blockedCount > 0 ? 'warning' : 'passed' },
        { name: 'Dual-Use Classifier', cat: 'safety', input: 'outputs + intent', output: 'no dual-use intent', source: 'demo', latency: 220, cost: 0.001 },
      ],
      confidence: 0.86,
    })
  if (blockedCount > 0) {
    for (const m of blockedMols) {
      push({ kind: 'event', stage: 'SAFETY_AUDIT', delay: D(90), event: mkEvent(wf, 'SAFETY_AUDIT', 'safety', `Safety gate · BLOCKED ${m.label}`, 'Quarantined by hazardous-material policy. Recommendation forced to "Do not advance". Details withheld.', { agent: 'Safety Auditor', safetyStatus: 'BLOCKED' }) })
    }
  }
  runPatch('SAFETY_AUDIT', { safetyStatus: blockedCount > 0 ? 'REVIEW_REQUIRED' : 'PASS' })

  // Stage: CRITIC_REVIEW
  push({ kind: 'stage', stage: 'CRITIC_REVIEW', delay: D(150) })
  emitAgent('CRITIC_REVIEW', 'Critic / Verifier Agent',
    'Challenge whole package: evidence, citations, validity, safety, no-route, overclaims',
    `Checklist: evidence present ✓ · citations verified/labeled ✓ · molecules valid ✓ · safety gate complete ✓ · no synthesis route ✓ · claims not overstated ✓. Package accepted with stated uncertainty.`,
    { tools: [{ name: 'Verifier', cat: 'orchestration', input: 'full package', output: 'verified with limitations', source: 'demo', latency: 500, cost: 0.005 }], confidence: 0.8 })
  runPatch('CRITIC_REVIEW')

  // Stage: CLINICAL_STRATEGY
  push({ kind: 'stage', stage: 'CLINICAL_STRATEGY', delay: D(150) })
  emitAgent('CLINICAL_STRATEGY', 'Clinical Strategy Agent',
    'Draft high-level clinical development plan',
    'Produced draft TPP, phase suggestion, endpoints, population logic, biomarker/comparator strategy, and trial risks. Disclaimer attached: not medical advice.',
    { tools: [{ name: 'ClinicalTrials.gov Adapter', cat: 'clinical', input: `${ctx.project.disease}`, output: '2 precedent trials (demo)', source: mode === 'real' ? 'fallback' : 'demo', latency: 700, cost: 0.004 }], confidence: 0.62 })
  runPatch('CLINICAL_STRATEGY')

  // Stage: REGULATORY_REVIEW
  push({ kind: 'stage', stage: 'REGULATORY_REVIEW', delay: D(150) })
  emitAgent('REGULATORY_REVIEW', 'Regulatory Reviewer',
    'Check FDA/MFDS/ICH guidance alignment (RAG)',
    'Assembled 7-item checklist with gaps (nonclinical package, CMC, KR dossier) and a regulatory risk score. High-level only; source IDs attached.',
    { tools: [{ name: 'FDA/MFDS Guidance RAG', cat: 'clinical', input: 'indication + phase + protocol', output: 'checklist + gaps + risk', source: mode === 'real' ? 'fallback' : 'demo', latency: 1000, cost: 0.008 }], confidence: 0.64 })
  runPatch('REGULATORY_REVIEW')

  // Stage: EVALUATION
  push({ kind: 'stage', stage: 'EVALUATION', delay: D(150) })
  emitAgent('EVALUATION', 'Evaluation Harness Agent',
    'Compute benchmark metrics across modules',
    `Rediscovery ✓ · validity 83% · self-correction ${revisionCount > 0 ? '100%' : '—'} · citation verification ✓ · ${blockedCount} unsafe blocked · est. cost $${(Math.round(cost * 1000) / 1000).toFixed(3)}.`,
    { tools: [{ name: 'Evaluation Harness', cat: 'orchestration', input: 'workflow outputs', output: '21 metrics', source: 'demo', latency: 600, cost: 0.005 }], confidence: 0.82 })
  runPatch('EVALUATION')

  // Stage: REPORT_GENERATION
  push({ kind: 'stage', stage: 'REPORT_GENERATION', delay: D(150) })
  emitAgent('REPORT_GENERATION', 'Report Builder',
    'Assemble judge-ready report + JSON audit export',
    'Report generated: every claim links to an evidence item or is labeled assumption/demo. Disclaimers, safety audit, evaluation, and audit appendix included.',
    { tools: [{ name: 'Reporter', cat: 'orchestration', input: 'all artifacts', output: 'Markdown + JSON', source: 'demo', latency: 500, cost: 0.004 }], confidence: 0.8 })
  push({ kind: 'event', stage: 'REPORT_GENERATION', delay: D(60), event: mkEvent(wf, 'REPORT_GENERATION', 'report', 'Report ready', 'Judge Demo Report assembled and available in Reports.', { agent: 'Report Builder', sourceType: 'demo' }) })

  // Complete
  push({
    kind: 'run',
    stage: 'COMPLETE',
    delay: D(200),
    patch: {
      status: 'success',
      currentStage: 'COMPLETE',
      completedAt: PLACEHOLDER,
      safetyStatus: blockedCount > 0 ? 'REVIEW_REQUIRED' : 'PASS',
      confidence: Math.round(confidence * 100) / 100,
      totalEstimatedCost: Math.round(cost * 1000) / 1000,
      totalEstimatedTokens: tokens,
      toolRunCount: toolCount,
      errorCount,
      revisionCount,
    },
  })
  push({ kind: 'stage', stage: 'COMPLETE', delay: 0 })

  return out
}

// A blank workflow run.
export function newWorkflowRun(id: string, projectId: string, mode: AppMode): WorkflowRun {
  return {
    id,
    projectId,
    mode,
    status: 'idle',
    currentStage: 'IDLE',
    totalEstimatedCost: 0,
    totalEstimatedTokens: 0,
    toolRunCount: 0,
    safetyStatus: 'DEMO_ONLY',
    confidence: 0.9,
    errorCount: 0,
    revisionCount: 0,
  }
}
