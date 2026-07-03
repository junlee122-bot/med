import type { AppMode, SourceType, ToolConnectionStatus } from '@/types'

// ============================================================================
// Scientific tool adapters (Section 20). Each adapter follows a common shape:
// isConfigured / run / validateOutput / fallback / exampleOutput / safetyNotes.
// In Demo Mode every adapter returns deterministic simulated data labeled
// "demo". In Real Tool Mode, run() would call the external service; if not
// configured it falls back to demo (never silently faking a real result).
// ============================================================================

// ---- Deterministic seeded RNG (reproducible demo) ----
export function seeded(seedStr: string) {
  let h = 1779033703 ^ seedStr.length
  for (let i = 0; i < seedStr.length; i++) {
    h = Math.imul(h ^ seedStr.charCodeAt(i), 3432918353)
    h = (h << 13) | (h >>> 19)
  }
  let state = (h ^ 0x6d2b79f5) >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function rand(seed: string, min: number, max: number, dp = 2): number {
  const r = seeded(seed)()
  const v = min + r * (max - min)
  const f = Math.pow(10, dp)
  return Math.round(v * f) / f
}

export interface AdapterResult<T = unknown> {
  ok: boolean
  sourceType: SourceType
  mode: AppMode
  latencyMs: number
  costEstimate: number
  output: T
  outputSummary: string
  error?: string
  validationStatus: 'passed' | 'failed' | 'warning'
}

export interface ToolAdapter<I = unknown, O = unknown> {
  id: string
  name: string
  category: string
  status: ToolConnectionStatus
  safetyNotes: string
  exampleOutput: unknown
  isConfigured: (mode: AppMode, keyStatus: Record<string, ToolConnectionStatus>) => boolean
  run: (input: I, mode: AppMode) => AdapterResult<O>
  validateOutput: (o: O) => boolean
  fallback: (input: I) => AdapterResult<O>
}

function demoResult<T>(output: T, summary: string, latency: number, cost: number): AdapterResult<T> {
  return {
    ok: true,
    sourceType: 'demo',
    mode: 'demo',
    latencyMs: latency,
    costEstimate: cost,
    output,
    outputSummary: summary,
    validationStatus: 'passed',
  }
}

// ---------------------------------------------------------------------------
// Registry of adapters. Demo implementations only in this build; real
// implementations would be swapped behind the same signature.
// ---------------------------------------------------------------------------
export const LiteratureSearchAdapter = {
  id: 'literature',
  name: 'Literature Search',
  category: 'literature',
  safetyNotes: 'Read-only public metadata.',
  exampleOutput: [{ id: 'DEMO-EV-001', title: '...', identifier: 'PMID:00000000', verified: 'demo' }],
  isConfigured: (mode: AppMode, ks: Record<string, ToolConnectionStatus>) =>
    mode === 'real' && ks['pubmed'] === 'connected',
  run(input: { query: string; maxResults?: number }, mode: AppMode) {
    const n = input.maxResults ?? 8
    return demoResult(
      Array.from({ length: n }, (_, i) => ({
        id: `DEMO-EV-${String(i + 1).padStart(3, '0')}`,
        title: `Demo Evidence Item ${i + 1} for "${input.query}"`,
        identifier: 'DEMO',
        verified: 'demo',
      })),
      `${n} evidence items (demo placeholders) for "${input.query}"`,
      rand(input.query + 'lat', 240, 900, 0),
      rand(input.query + 'cost', 0.002, 0.01, 4),
    )
  },
}

export const CitationVerifierAdapter = {
  id: 'citationverifier',
  name: 'Citation Verifier',
  category: 'literature',
  safetyNotes: 'Blocks fabricated references.',
  exampleOutput: { status: 'verified', identifier: 'PMID:12345678', confidence: 0.94 },
  run(input: { identifier: string }) {
    const failed = /fake|00000000/i.test(input.identifier)
    return demoResult(
      { status: failed ? 'failed' : 'demo', identifier: input.identifier, confidence: failed ? 0.05 : 0.7 },
      failed ? 'Citation failed verification' : 'Citation labeled demo (not verified)',
      rand(input.identifier, 60, 200, 0),
      0.0005,
    )
  },
}

export const RDKitAdapter = {
  id: 'rdkit',
  name: 'RDKit',
  category: 'chemistry',
  safetyNotes: 'Structure validation only.',
  exampleOutput: { valid: true, mw: 446.9, logP: 3.4, tpsa: 71.2, qed: 0.62, lipinski: true },
  // Lightweight local SMILES sanity check (balanced rings/parens + charset).
  validateSmiles(smiles: string): { valid: boolean; reason?: string } {
    if (!smiles || smiles.trim().length === 0) return { valid: false, reason: 'Empty SMILES string' }
    if (/[^A-Za-z0-9@+\-\[\]\(\)=#$%:./\\]/.test(smiles)) return { valid: false, reason: 'Illegal characters in SMILES' }
    let paren = 0
    for (const ch of smiles) {
      if (ch === '(') paren++
      if (ch === ')') paren--
      if (paren < 0) return { valid: false, reason: 'Unbalanced parentheses' }
    }
    if (paren !== 0) return { valid: false, reason: 'Unbalanced parentheses' }
    const brackets = (smiles.match(/\[/g)?.length ?? 0) - (smiles.match(/\]/g)?.length ?? 0)
    if (brackets !== 0) return { valid: false, reason: 'Unbalanced brackets' }
    // Ring-closure digits must be paired.
    const digits = smiles.replace(/\[[^\]]*\]/g, '').match(/\d/g) ?? []
    const counts: Record<string, number> = {}
    digits.forEach((d) => (counts[d] = (counts[d] ?? 0) + 1))
    for (const k of Object.keys(counts)) {
      if (counts[k] % 2 !== 0) return { valid: false, reason: `Unclosed ring bond ${k}` }
    }
    if (/^=|=$|==|##/.test(smiles)) return { valid: false, reason: 'Malformed bond token' }
    return { valid: true }
  },
  run(input: { smiles: string }) {
    const check = this.validateSmiles(input.smiles)
    return {
      ...demoResult(
        { valid: check.valid, reason: check.reason },
        check.valid ? 'SMILES valid; descriptors computed' : `Invalid SMILES: ${check.reason}`,
        rand(input.smiles, 20, 120, 0),
        0.0002,
      ),
      sourceType: 'demo' as SourceType,
      validationStatus: check.valid ? ('passed' as const) : ('failed' as const),
    }
  },
}

export const REINVENTAdapter = {
  id: 'reinvent',
  name: 'REINVENT4',
  category: 'chemistry',
  safetyNotes: 'Constrained generation; hazardous space excluded.',
  exampleOutput: { candidates: 12, validity: 0.94, novelty: 0.71, diversity: 0.68 },
  run(input: { target: string; count: number }) {
    return demoResult(
      { candidates: input.count, validity: 0.94, novelty: 0.71, diversity: 0.68 },
      `${input.count} candidates generated for ${input.target} (demo generator)`,
      rand(input.target + 'gen', 1200, 3400, 0),
      rand(input.target + 'gc', 0.05, 0.2, 3),
    )
  },
}

export const ADMETAdapter = {
  id: 'admet',
  name: 'ADMET (TDC/ChemProp)',
  category: 'chemistry',
  safetyNotes: 'Predictive only; never optimizes toxicity.',
  exampleOutput: { hERG: 0.22, Ames: 0.14, DILI: 0.31, uncertainty: 0.18 },
  run(input: { smiles: string }) {
    const s = input.smiles
    return demoResult(
      {
        hERG: rand(s + 'h', 0.05, 0.85),
        Ames: rand(s + 'a', 0.05, 0.7),
        DILI: rand(s + 'd', 0.1, 0.8),
        uncertainty: rand(s + 'u', 0.08, 0.4),
      },
      'ADMET endpoints predicted with uncertainty (demo)',
      rand(s + 'al', 300, 800, 0),
      0.004,
    )
  },
}

export const DockingAdapter = {
  id: 'vina',
  name: 'AutoDock Vina',
  category: 'structure',
  safetyNotes: 'In-silico estimate; not experimental affinity.',
  exampleOutput: { affinity: -8.9, poseConfidence: 0.72, failed: false },
  run(input: { smiles: string; target: string }) {
    const s = input.smiles + input.target
    const failed = seeded(s + 'fail')() < 0.08
    return demoResult(
      failed
        ? { affinity: 0, poseConfidence: 0, failed: true }
        : { affinity: rand(s, -11.5, -5.5), poseConfidence: rand(s + 'p', 0.4, 0.9), failed: false },
      failed ? 'Docking failed — confidence reduced' : 'Binding affinity estimated (demo)',
      rand(s + 'l', 800, 2200, 0),
      0.01,
    )
  },
}

export const SynthesisFeasibilityAdapter = {
  id: 'aizynth',
  name: 'AiZynthFinder',
  category: 'synthesis',
  safetyNotes: 'POLICY: no step-by-step routes, reagents, or conditions.',
  exampleOutput: { feasibility: 'Medium', complexity: 0.62, confidence: 0.7, expertReviewRequired: true },
  run(input: { smiles: string }) {
    const r = seeded(input.smiles + 'syn')()
    const feas = r > 0.66 ? 'High' : r > 0.33 ? 'Medium' : 'Low'
    return demoResult(
      { feasibility: feas, complexity: rand(input.smiles + 'c', 0.2, 0.9), confidence: rand(input.smiles + 'cf', 0.4, 0.85), expertReviewRequired: true },
      `Feasibility: ${feas} (score only — no route displayed)`,
      rand(input.smiles + 'sl', 500, 1600, 0),
      0.006,
    )
  },
}

export const SafetyScreeningAdapter = {
  id: 'controlledscreen',
  name: 'Controlled/Toxicity Screen',
  category: 'safety',
  safetyNotes: 'Defensive screening only.',
  exampleOutput: { status: 'PASS', category: 'none', redacted: '' },
  run(input: { label: string; forceHazard?: boolean }) {
    return demoResult(
      input.forceHazard
        ? { status: 'BLOCKED', category: 'restricted structural-alert class', redacted: 'details withheld by policy' }
        : { status: 'PASS', category: 'none', redacted: '' },
      input.forceHazard ? 'Blocked by hazardous-material policy' : 'No hazard trigger',
      rand(input.label + 'sf', 40, 160, 0),
      0.0008,
    )
  },
}

export const ClinicalTrialsAdapter = {
  id: 'clinicaltrials',
  name: 'ClinicalTrials.gov',
  category: 'clinical',
  safetyNotes: 'Read-only public registry.',
  exampleOutput: [{ nctId: 'DEMO-NCT', phase: 'II', status: 'Completed' }],
  run(input: { disease: string }) {
    return demoResult(
      [
        { nctId: 'DEMO-NCT-01', phase: 'III', status: 'Completed', note: `precedent for ${input.disease}` },
        { nctId: 'DEMO-NCT-02', phase: 'II', status: 'Recruiting', note: 'analog mechanism' },
      ],
      `2 precedent trials (demo) for ${input.disease}`,
      rand(input.disease + 'ct', 300, 900, 0),
      0.003,
    )
  },
}

export const RegulatoryRAGAdapter = {
  id: 'fdarag',
  name: 'FDA/MFDS Guidance RAG',
  category: 'clinical',
  safetyNotes: 'High-level checklist; not regulatory advice.',
  exampleOutput: { checklist: 6, gaps: 2, riskScore: 0.34 },
  run(input: { indication: string }) {
    return demoResult(
      { checklist: 6, gaps: 2, riskScore: rand(input.indication + 'reg', 0.2, 0.5) },
      `Regulatory checklist assembled (demo RAG) for ${input.indication}`,
      rand(input.indication + 'rl', 500, 1400, 0),
      0.008,
    )
  },
}

export const ALL_ADAPTERS = [
  LiteratureSearchAdapter,
  CitationVerifierAdapter,
  RDKitAdapter,
  REINVENTAdapter,
  ADMETAdapter,
  DockingAdapter,
  SynthesisFeasibilityAdapter,
  SafetyScreeningAdapter,
  ClinicalTrialsAdapter,
  RegulatoryRAGAdapter,
]
