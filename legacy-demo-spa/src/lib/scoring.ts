import type {
  MoleculeCandidate,
  MoleculeWeights,
  Recommendation,
  SafetyStatus,
  TargetCandidate,
  TargetWeights,
} from '@/types'

// ============================================================================
// Transparent scoring system (Section 11). All formulas are pure & editable.
// ============================================================================

export const DEFAULT_TARGET_WEIGHTS: TargetWeights = {
  diseaseRelevance: 0.25,
  tractability: 0.2,
  clinicalPrecedent: 0.15,
  biomarkerAvailability: 0.15,
  novelty: 0.1,
  evidenceConfidence: 0.1,
  safetyConcern: 0.15, // subtracted
}

export const DEFAULT_MOLECULE_WEIGHTS: MoleculeWeights = {
  binding: 0.2,
  admet: 0.18,
  qed: 0.12,
  lipinski: 0.1,
  syntheticFeasibility: 0.1,
  novelty: 0.1,
  targetRationale: 0.1,
  confidence: 0.1,
}

export function clamp01(x: number): number {
  return Math.max(0, Math.min(1, x))
}

export function round(x: number, dp = 1): number {
  const f = Math.pow(10, dp)
  return Math.round(x * f) / f
}

// ---- Target Opportunity Score → 0-100 ----
export function targetScore(t: Partial<TargetCandidate>, w: TargetWeights = DEFAULT_TARGET_WEIGHTS): number {
  const raw =
    w.diseaseRelevance * (t.diseaseRelevance ?? 0) +
    w.tractability * (t.tractability ?? 0) +
    w.clinicalPrecedent * (t.clinicalPrecedent ?? 0) +
    w.biomarkerAvailability * (t.biomarkerAvailability ?? 0) +
    w.novelty * (t.novelty ?? 0) +
    w.evidenceConfidence * (t.evidenceConfidence ?? 0) -
    w.safetyConcern * (t.safetyConcern ?? 0)
  // Positive-weight max (when safetyConcern=0) is sum of positive weights.
  const maxPos =
    w.diseaseRelevance + w.tractability + w.clinicalPrecedent + w.biomarkerAvailability + w.novelty + w.evidenceConfidence
  const norm = clamp01(raw / maxPos)
  return round(norm * 100, 1)
}

// Feature label for scoring transparency panels.
export function targetScoreBreakdown(t: Partial<TargetCandidate>, w: TargetWeights = DEFAULT_TARGET_WEIGHTS) {
  return [
    { key: 'Disease relevance', value: (t.diseaseRelevance ?? 0), weight: w.diseaseRelevance, sign: 1 },
    { key: 'Tractability', value: (t.tractability ?? 0), weight: w.tractability, sign: 1 },
    { key: 'Clinical precedent', value: (t.clinicalPrecedent ?? 0), weight: w.clinicalPrecedent, sign: 1 },
    { key: 'Biomarker availability', value: (t.biomarkerAvailability ?? 0), weight: w.biomarkerAvailability, sign: 1 },
    { key: 'Novelty', value: (t.novelty ?? 0), weight: w.novelty, sign: 1 },
    { key: 'Evidence confidence', value: (t.evidenceConfidence ?? 0), weight: w.evidenceConfidence, sign: 1 },
    { key: 'Safety concern (penalty)', value: (t.safetyConcern ?? 0), weight: w.safetyConcern, sign: -1 },
  ]
}

// ---- Safety penalty ----
export function safetyPenalty(status: SafetyStatus): number {
  switch (status) {
    case 'PASS':
      return 0
    case 'REVIEW_REQUIRED':
      return 15
    case 'BLOCKED':
      return 100 // effectively forces "do not advance"
    case 'DEMO_ONLY':
      return 5
    case 'TOOL_ERROR':
      return 10
    default:
      return 0
  }
}

// ---- Molecule Composite Score → 0-100 ----
export interface MoleculeScoreInputs {
  bindingNormalized: number // 0-1
  admetScore: number // 0-1
  qed: number // 0-1
  lipinskiPass: boolean
  lipinskiViolations: number
  synthesisFeasibility: 'High' | 'Medium' | 'Low'
  novelty: number
  targetRationale: number // 0-1
  confidence: number // 0-1
  uncertainty: number // 0-1
  safetyStatus: SafetyStatus
}

export function feasibilityToScore(f: 'High' | 'Medium' | 'Low'): number {
  return f === 'High' ? 0.9 : f === 'Medium' ? 0.6 : 0.3
}

export function moleculeComposite(
  m: MoleculeScoreInputs,
  w: MoleculeWeights = DEFAULT_MOLECULE_WEIGHTS,
): number {
  const lipinskiScore = clamp01(1 - m.lipinskiViolations * 0.25)
  const base =
    w.binding * clamp01(m.bindingNormalized) +
    w.admet * clamp01(m.admetScore) +
    w.qed * clamp01(m.qed) +
    w.lipinski * lipinskiScore +
    w.syntheticFeasibility * feasibilityToScore(m.synthesisFeasibility) +
    w.novelty * clamp01(m.novelty) +
    w.targetRationale * clamp01(m.targetRationale) +
    w.confidence * clamp01(m.confidence)
  const maxPos =
    w.binding + w.admet + w.qed + w.lipinski + w.syntheticFeasibility + w.novelty + w.targetRationale + w.confidence
  let score = (base / maxPos) * 100
  score -= safetyPenalty(m.safetyStatus)
  score -= m.uncertainty * 12 // uncertainty penalty
  return round(Math.max(0, score), 1)
}

export function moleculeScoreBreakdown(m: MoleculeCandidate, w: MoleculeWeights = DEFAULT_MOLECULE_WEIGHTS) {
  const lipinskiScore = clamp01(1 - m.lipinskiViolations * 0.25)
  return [
    { key: 'Binding (norm.)', value: m.bindingNormalized, weight: w.binding, sign: 1 },
    { key: 'ADMET', value: m.admetScore, weight: w.admet, sign: 1 },
    { key: 'QED', value: m.qed, weight: w.qed, sign: 1 },
    { key: 'Lipinski', value: lipinskiScore, weight: w.lipinski, sign: 1 },
    { key: 'Synthetic feasibility', value: feasibilityToScore(m.synthesisFeasibility), weight: w.syntheticFeasibility, sign: 1 },
    { key: 'Novelty', value: m.novelty, weight: w.novelty, sign: 1 },
    { key: 'Target rationale', value: 0.8, weight: w.targetRationale, sign: 1 },
    { key: 'Confidence', value: 1 - m.uncertainty, weight: w.confidence, sign: 1 },
  ]
}

// ---- Recommendation levels ----
export function recommendationFor(m: {
  compositeScore: number
  safetyStatus: SafetyStatus
  uncertainty: number
  validityStatus: 'valid' | 'invalid' | 'pending'
}): Recommendation {
  if (m.validityStatus === 'invalid') return 'reject'
  if (m.safetyStatus === 'BLOCKED') return 'quarantined'
  if (m.safetyStatus === 'REVIEW_REQUIRED') return 'hold'
  if (m.compositeScore >= 70 && m.uncertainty < 0.35) return 'advance'
  if (m.compositeScore >= 50) return 'optimize'
  return 'hold'
}

export const RECOMMENDATION_LABEL: Record<Recommendation, { label: string; tone: string }> = {
  advance: { label: 'Advance to expert review', tone: 'green' },
  optimize: { label: 'Needs optimization', tone: 'amber' },
  hold: { label: 'Hold pending evidence', tone: 'slate' },
  quarantined: { label: 'Quarantined by safety gate', tone: 'red' },
  reject: { label: 'Reject', tone: 'red' },
}

// ---- Confidence modifiers (Section 11) ----
export interface ConfidenceContext {
  citationUnverified: boolean
  demoSimulation: boolean
  dockingFailed: boolean
  highAdmetUncertainty: boolean
  contradictoryEvidence: boolean
  safetyReviewRequired: boolean
  missingClinicalPrecedent: boolean
}

export function adjustConfidence(base: number, ctx: Partial<ConfidenceContext>): number {
  let c = base
  if (ctx.citationUnverified) c -= 0.12
  if (ctx.demoSimulation) c -= 0.08
  if (ctx.dockingFailed) c -= 0.1
  if (ctx.highAdmetUncertainty) c -= 0.1
  if (ctx.contradictoryEvidence) c -= 0.09
  if (ctx.safetyReviewRequired) c -= 0.15
  if (ctx.missingClinicalPrecedent) c -= 0.07
  return clamp01(c)
}

// Lipinski violation counter from descriptors.
export function lipinskiViolations(d: { mw: number; logP: number; hbd: number; hba: number }): number {
  let v = 0
  if (d.mw > 500) v++
  if (d.logP > 5) v++
  if (d.hbd > 5) v++
  if (d.hba > 10) v++
  return v
}
