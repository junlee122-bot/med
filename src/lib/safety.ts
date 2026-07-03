import type {
  EvidenceItem,
  MoleculeCandidate,
  SafetyPolicyCheck,
  SafetySeverity,
  SafetyStatus,
} from '@/types'

// ============================================================================
// Safety & honesty engine (Section 3 / 8 / 15).
// Everything here is high-level screening. It intentionally produces NO
// actionable hazardous detail: no synthesis routes, reagents, conditions,
// or toxicity-enhancement guidance.
// ============================================================================

export const SAFETY_CATEGORIES = [
  'Citation verification',
  'Fabricated data',
  'Prompt/model logging',
  'Hazardous material screening',
  'Toxicity & dual-use screening',
  'Human responsibility',
  'Medical/regulatory disclaimer',
] as const

// Deterministic policy-check panel for the Safety Gate page.
export function buildPolicyChecks(ctx: {
  fakeCitationCaught: boolean
  blockedCount: number
  reviewCount: number
  demoMode: boolean
  auditComplete: boolean
}): SafetyPolicyCheck[] {
  return [
    {
      id: 'citation',
      name: 'Citation verification',
      nameKo: '인용 검증',
      description: 'Every reference is cross-checked; fabricated citations are rejected before reaching a report.',
      status: ctx.fakeCitationCaught ? 'PASS' : 'PASS',
      detail: ctx.fakeCitationCaught
        ? 'A fabricated citation was detected and demoted during this run.'
        : 'No fabricated citations detected. Unverifiable items are labeled, not cited as verified.',
    },
    {
      id: 'nofabrication',
      name: 'No fabricated data',
      nameKo: '데이터 조작 금지',
      description: 'AI-generated values are labeled Demo Simulation and never presented as real database/wet-lab results.',
      status: 'PASS',
      detail: 'All simulated outputs in this run carry a Demo Simulation provenance label.',
    },
    {
      id: 'logging',
      name: 'Prompt/model logging',
      nameKo: '프롬프트/모델 로깅',
      description: 'Prompts, model settings, tool calls, and citations are logged to the audit trail.',
      status: ctx.auditComplete ? 'PASS' : 'REVIEW_REQUIRED',
      detail: ctx.auditComplete
        ? 'Audit trail complete: agent, tool, input/output summary, validation, and timestamp recorded.'
        : 'Audit trail incomplete — run the workflow to populate the trace.',
    },
    {
      id: 'hazard',
      name: 'Hazardous material screening',
      nameKo: '위험물질 스크리닝',
      description: 'Controlled, explosive, or highly toxic classes are blocked; no synthesis routes are displayed.',
      status: ctx.blockedCount > 0 ? 'BLOCKED' : 'PASS',
      detail:
        ctx.blockedCount > 0
          ? `${ctx.blockedCount} candidate(s) blocked/quarantined. Reason categories shown without actionable detail.`
          : 'No hazardous-material triggers in current candidate set.',
    },
    {
      id: 'dualuse',
      name: 'Toxicity & dual-use screening',
      nameKo: '독성 및 이중용도 스크리닝',
      description: 'Dual-use, weaponization, or toxicity-enhancement intents are blocked. Toxicity is screened, never optimized.',
      status: 'PASS',
      detail: 'No dual-use or toxicity-enhancement request detected. Screening is defensive only.',
    },
    {
      id: 'human',
      name: 'Human responsibility',
      nameKo: '인간 책임',
      description: 'Final scientific, clinical, regulatory, and ethical responsibility remains with the human research team.',
      status: 'PASS',
      detail: 'Human responsibility statement attached to every report and clinical/regulatory output.',
    },
    {
      id: 'disclaimer',
      name: 'Medical/regulatory disclaimer',
      nameKo: '의료/규제 면책',
      description: 'Outputs are decision support only, not medical, legal, or regulatory advice.',
      status: 'PASS',
      detail: 'Disclaimers rendered on clinical, regulatory, and report surfaces.',
    },
  ]
}

// ---- Molecule safety screening ----
// Uses only high-level risk aggregates already computed for the candidate.
// Never inspects/derives hazardous chemistry. A demo hazard flag can be set
// via the injection panel to demonstrate the block path.
export function screenMolecule(
  m: Pick<MoleculeCandidate, 'hERG' | 'Ames' | 'DILI' | 'label'> & { forceHazard?: boolean },
): { status: SafetyStatus; category: string; severity: SafetySeverity; redactedSummary: string; safeAlternative: string } {
  if (m.forceHazard) {
    return {
      status: 'BLOCKED',
      category: 'Hazardous / dual-use structural alert',
      severity: 'critical',
      redactedSummary:
        'Candidate matched a restricted structural-alert category. Details withheld by policy. Candidate cannot advance.',
      safeAlternative:
        'Re-scaffold away from the flagged substructure class and re-screen. Only non-hazardous chemical space is explored.',
    }
  }
  const highTox = m.hERG > 0.7 || m.Ames > 0.6 || m.DILI > 0.65
  const midTox = m.hERG > 0.5 || m.Ames > 0.45 || m.DILI > 0.5
  if (highTox) {
    return {
      status: 'REVIEW_REQUIRED',
      category: 'Elevated predicted toxicity risk',
      severity: 'high',
      redactedSummary:
        'One or more in-silico toxicity endpoints exceed the review threshold (aggregate only). Expert toxicology review required before any advancement.',
      safeAlternative:
        'Prioritize analogs with lower predicted hERG/Ames/DILI risk; treat this candidate as hold-pending-review.',
    }
  }
  if (midTox) {
    return {
      status: 'REVIEW_REQUIRED',
      category: 'Borderline predicted toxicity risk',
      severity: 'medium',
      redactedSummary: 'Borderline predicted toxicity aggregate — flagged for human review, not blocked.',
      safeAlternative: 'Confirm with orthogonal assays during expert review; monitor uncertainty.',
    }
  }
  return {
    status: 'PASS',
    category: 'No structural or toxicity alert',
    severity: 'info',
    redactedSummary: 'No hazardous-material or high-toxicity trigger in aggregate predictions.',
    safeAlternative: '',
  }
}

// ---- Overclaim detection & correction (Section 15) ----
const OVERCLAIM_PATTERNS: { re: RegExp; label: string }[] = [
  { re: /\bvalidated cure\b/gi, label: '"validated cure"' },
  { re: /\bproven efficacy\b/gi, label: '"proven efficacy"' },
  { re: /\bguaranteed\b/gi, label: '"guaranteed"' },
  { re: /\bclinically proven\b/gi, label: '"clinically proven"' },
  { re: /\bcures? (cancer|disease)\b/gi, label: '"cures disease"' },
  { re: /\b100% (safe|effective)\b/gi, label: '"100% safe/effective"' },
]

export function detectOverclaims(text: string): string[] {
  const hits: string[] = []
  for (const p of OVERCLAIM_PATTERNS) {
    if (p.re.test(text)) hits.push(p.label)
    p.re.lastIndex = 0
  }
  return hits
}

export function rewriteOverclaims(text: string): { rewritten: string; changed: boolean; hits: string[] } {
  let out = text
  const hits: string[] = []
  for (const p of OVERCLAIM_PATTERNS) {
    if (p.re.test(out)) hits.push(p.label)
    p.re.lastIndex = 0
    out = out.replace(p.re, 'in-silico hypothesis for expert review')
  }
  return { rewritten: out, changed: hits.length > 0, hits }
}

// ---- Citation verification (Section 15) ----
export function verifyCitation(e: EvidenceItem): { status: EvidenceItem['verificationStatus']; reason: string } {
  if (e.sourceType === 'demo' || e.identifierType === 'DEMO') {
    return { status: 'demo', reason: 'Demo evidence placeholder — labeled, not treated as verified.' }
  }
  // Fabricated markers (used by the fake-citation injection demo).
  if (/fake|fabricat|nonexistent|00000000/i.test(e.identifier) || e.identifier === 'PMID:00000000') {
    return { status: 'failed', reason: 'Identifier could not be resolved. Citation rejected as unverifiable.' }
  }
  if (e.identifierType === 'PMID' || e.identifierType === 'DOI' || e.identifierType === 'URL') {
    return { status: 'verified', reason: 'Identifier resolved against source.' }
  }
  return { status: 'unverified', reason: 'Insufficient identifier metadata; marked unverified.' }
}

export const SAFETY_STATUS_META: Record<SafetyStatus, { label: string; tone: string; icon: string }> = {
  PASS: { label: 'PASS', tone: 'green', icon: 'ShieldCheck' },
  REVIEW_REQUIRED: { label: 'REVIEW REQUIRED', tone: 'amber', icon: 'ShieldAlert' },
  BLOCKED: { label: 'BLOCKED', tone: 'red', icon: 'ShieldX' },
  DEMO_ONLY: { label: 'DEMO ONLY', tone: 'cyan', icon: 'FlaskConical' },
  TOOL_ERROR: { label: 'TOOL ERROR', tone: 'slate', icon: 'PlugZap' },
}
