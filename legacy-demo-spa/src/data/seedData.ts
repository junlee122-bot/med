import type {
  CheckpointEntry,
  ClinicalProtocolDraft,
  DatasetEntry,
  EvidenceItem,
  Hypothesis,
  MoleculeCandidate,
  MoleculeDescriptors,
  Project,
  RegulatoryCheck,
  SafetyFlag,
  TargetCandidate,
  TrainingJob,
  EvaluationResult,
} from '@/types'
import { RDKitAdapter, rand, seeded } from '@/lib/adapters'
import {
  clamp01,
  lipinskiViolations,
  moleculeComposite,
  recommendationFor,
  targetScore,
} from '@/lib/scoring'
import { screenMolecule } from '@/lib/safety'
import { CLINICAL_DISCLAIMER } from '@/lib/constants'

// A fixed base timestamp keeps the seed reproducible (no Date.now at build).
const T0 = '2026-06-30T09:00:00.000Z'
function tOffset(mins: number): string {
  return new Date(new Date(T0).getTime() + mins * 60000).toISOString()
}

export const DEMO_PROJECT_ID = 'proj-nsclc-egfr-demo'

// ============================================================================
// Demo project
// ============================================================================
export function buildDemoProject(): Project {
  return {
    id: DEMO_PROJECT_ID,
    name: 'NSCLC EGFR Retrospective Discovery Demo',
    disease: 'Non-small cell lung cancer',
    indication: 'EGFR-altered NSCLC retrospective rediscovery scenario',
    patientPopulation: 'Advanced/metastatic NSCLC harboring activating EGFR alterations, incl. acquired-resistance subpopulations',
    unmetNeed:
      'Durable response after resistance emerges; CNS-penetrant options; reduced dose-limiting toxicity and clearer biomarker-guided selection.',
    discoveryGoal: 'full_pipeline',
    mode: 'demo',
    status: 'complete',
    scientificConstraints: {
      knownTargets: ['EGFR'],
      excludedTargets: [],
      mechanismPreferences: ['Mutant-selective inhibition', 'CNS penetration'],
      biomarkerRequirements: ['EGFR alteration status', 'ctDNA clearance'],
      modality: 'small_molecule',
    },
    safetyConstraints: {
      excludeControlled: true,
      excludeHighToxicityOptimization: true,
      noSynthesisRecipe: true,
      humanReviewRequired: true,
    },
    evaluationPlan: {
      retrospectiveRediscovery: true,
      tdcAdmet: true,
      dockingEnrichment: true,
      citationVerification: true,
      selfCorrection: true,
      costLatency: true,
    },
    createdAt: tOffset(0),
    updatedAt: tOffset(120),
    owner: 'demo@helixforge.ai',
    summary:
      'End-to-end Field 4 demonstration: evidence mining → target rationale → molecule optimization loop → safety gate → clinical/regulatory strategy → evaluation report. All scientific outputs are Demo Simulation unless explicitly labeled otherwise.',
    humanResponsibilityAccepted: true,
    seeded: true,
  }
}

// ============================================================================
// Evidence (8 items: 6 demo-verified, 1 contradictory, 1 fabricated)
// ============================================================================
export function buildEvidence(): EvidenceItem[] {
  const base: Omit<EvidenceItem, 'id' | 'projectId' | 'retrievedAt'>[] = [
    {
      sourceName: 'PubMed (demo)',
      sourceType: 'demo',
      title: 'EGFR activating alterations as oncogenic drivers in NSCLC — demo synthesis',
      authors: 'Demo Evidence Consortium',
      year: 2021,
      identifierType: 'DEMO',
      identifier: 'DEMO-EV-001',
      claim: 'Activating EGFR alterations are validated oncogenic drivers in a defined NSCLC subpopulation.',
      evidenceDirection: 'supports',
      confidence: 0.86,
      verificationStatus: 'demo',
      relatedTarget: 'EGFR',
      notes: 'Placeholder demo record — not a real citation.',
    },
    {
      sourceName: 'Open Targets (demo)',
      sourceType: 'demo',
      title: 'Disease-target association profile for EGFR × NSCLC — demo export',
      authors: 'Open Targets (simulated)',
      year: 2022,
      identifierType: 'OpenTargets',
      identifier: 'DEMO-OT-EGFR',
      claim: 'Genetic + somatic + drug evidence datatypes converge on a high EGFR association score for NSCLC.',
      evidenceDirection: 'supports',
      confidence: 0.82,
      verificationStatus: 'demo',
      relatedTarget: 'EGFR',
    },
    {
      sourceName: 'Europe PMC (demo)',
      sourceType: 'demo',
      title: 'CNS penetration considerations for EGFR-directed small molecules — demo review',
      authors: 'Demo Neuro-Oncology Group',
      year: 2020,
      identifierType: 'DEMO',
      identifier: 'DEMO-EV-003',
      claim: 'CNS-penetrant chemotypes address a recognized unmet need for brain-metastatic disease.',
      evidenceDirection: 'supports',
      confidence: 0.74,
      verificationStatus: 'demo',
      relatedTarget: 'EGFR',
    },
    {
      sourceName: 'ChEMBL (demo)',
      sourceType: 'demo',
      title: 'Bioactivity landscape & tractability signal for EGFR — demo slice',
      authors: 'ChEMBL (simulated)',
      year: 2023,
      identifierType: 'DEMO',
      identifier: 'DEMO-EV-004',
      claim: 'Rich bioactivity data and multiple approved comparators indicate high small-molecule tractability.',
      evidenceDirection: 'supports',
      confidence: 0.8,
      verificationStatus: 'demo',
      relatedTarget: 'EGFR',
    },
    {
      sourceName: 'ClinicalTrials.gov (demo)',
      sourceType: 'demo',
      title: 'Biomarker-selected trial precedent in EGFR-altered NSCLC — demo summary',
      authors: 'Registry (simulated)',
      year: 2022,
      identifierType: 'ClinicalTrials',
      identifier: 'DEMO-NCT-001',
      claim: 'Biomarker-selected trial designs show feasibility of ctDNA-guided enrollment.',
      evidenceDirection: 'supports',
      confidence: 0.71,
      verificationStatus: 'demo',
      relatedTarget: 'EGFR',
    },
    {
      sourceName: 'Semantic Scholar (demo)',
      sourceType: 'demo',
      title: 'Resistance mechanisms after EGFR inhibition — demo meta-view',
      authors: 'Demo Resistance Atlas',
      year: 2021,
      identifierType: 'DEMO',
      identifier: 'DEMO-EV-006',
      claim: 'Acquired resistance is heterogeneous; combination and next-generation strategies are motivated.',
      evidenceDirection: 'supports',
      confidence: 0.69,
      verificationStatus: 'demo',
      relatedTarget: 'EGFR',
    },
    {
      // Contradictory evidence item
      sourceName: 'Europe PMC (demo)',
      sourceType: 'demo',
      title: 'Subgroup non-response and toxicity signal — contradictory demo record',
      authors: 'Demo Contrarian Cohort',
      year: 2023,
      identifierType: 'DEMO',
      identifier: 'DEMO-EV-007',
      claim: 'A subgroup shows limited benefit and elevated toxicity, tempering universal efficacy claims.',
      evidenceDirection: 'contradicts',
      confidence: 0.63,
      verificationStatus: 'demo',
      relatedTarget: 'EGFR',
      notes: 'Retained deliberately: uncertainty must be represented, not hidden.',
    },
    {
      // Fabricated citation (injection demo). Verifier will FAIL this.
      sourceName: 'PubMed',
      sourceType: 'real',
      title: 'Definitive proof of universal cure via EGFR modulation (fabricated example)',
      authors: 'Nonexistent et al.',
      year: 2025,
      identifierType: 'PMID',
      identifier: 'PMID:00000000',
      claim: 'Overstated fabricated claim used to demonstrate citation rejection.',
      evidenceDirection: 'supports',
      confidence: 0.0,
      verificationStatus: 'failed',
      relatedTarget: 'EGFR',
      notes: 'Injected fake citation — caught by Citation Verifier and demoted.',
    },
  ]
  return base.map((b, i) => ({
    ...b,
    id: `ev-${String(i + 1).padStart(3, '0')}`,
    projectId: DEMO_PROJECT_ID,
    retrievedAt: tOffset(8 + i),
  }))
}

// ============================================================================
// Targets (5 ranked)
// ============================================================================
export function buildTargets(): TargetCandidate[] {
  const raw: (Partial<TargetCandidate> & { symbol: string; name: string; rationale: string; moleculeStrategy: string })[] = [
    {
      symbol: 'EGFR',
      name: 'Epidermal growth factor receptor',
      diseaseRelevance: 0.94,
      tractability: 0.9,
      novelty: 0.35,
      safetyConcern: 0.3,
      biomarkerAvailability: 0.9,
      clinicalPrecedent: 0.95,
      evidenceCount: 6,
      evidenceConfidence: 0.85,
      rationale:
        'Strongest converging evidence: validated oncogenic driver, high tractability, established biomarker strategy and clinical precedent. Primary hypothesis anchor.',
      moleculeStrategy: 'Mutant-selective, CNS-penetrant small-molecule inhibitor with resistance-aware profiling.',
    },
    {
      symbol: 'MET',
      name: 'MET receptor tyrosine kinase',
      diseaseRelevance: 0.72,
      tractability: 0.74,
      novelty: 0.55,
      safetyConcern: 0.35,
      biomarkerAvailability: 0.66,
      clinicalPrecedent: 0.7,
      evidenceCount: 3,
      evidenceConfidence: 0.66,
      rationale: 'Bypass-resistance mechanism; combination rationale with EGFR. Moderate precedent and biomarker maturity.',
      moleculeStrategy: 'Combination-oriented inhibitor; evaluate as resistance-directed add-on hypothesis.',
    },
    {
      symbol: 'KRAS',
      name: 'KRAS GTPase',
      diseaseRelevance: 0.6,
      tractability: 0.55,
      novelty: 0.7,
      safetyConcern: 0.45,
      biomarkerAvailability: 0.6,
      clinicalPrecedent: 0.58,
      evidenceCount: 2,
      evidenceConfidence: 0.55,
      rationale: 'Historically difficult target; allele-specific tractability improving. Higher novelty, higher risk.',
      moleculeStrategy: 'Allele-specific covalent approach — exploratory, expert review required.',
    },
    {
      symbol: 'ERBB2',
      name: 'HER2 / ERBB2',
      diseaseRelevance: 0.55,
      tractability: 0.68,
      novelty: 0.5,
      safetyConcern: 0.32,
      biomarkerAvailability: 0.62,
      clinicalPrecedent: 0.66,
      evidenceCount: 2,
      evidenceConfidence: 0.58,
      rationale: 'Related ERBB-family node; relevant subset with exon-level alterations. Secondary hypothesis.',
      moleculeStrategy: 'Selective ERBB-family inhibitor for defined alteration subset.',
    },
    {
      symbol: 'ALK',
      name: 'Anaplastic lymphoma kinase',
      diseaseRelevance: 0.4,
      tractability: 0.7,
      novelty: 0.6,
      safetyConcern: 0.3,
      biomarkerAvailability: 0.7,
      clinicalPrecedent: 0.72,
      evidenceCount: 1,
      evidenceConfidence: 0.48,
      rationale: 'Distinct oncogenic subset; low overlap with EGFR cohort. Included for landscape completeness (exploratory).',
      moleculeStrategy: 'Out-of-scope for primary EGFR hypothesis; retained as comparator context.',
    },
  ]
  const scored = raw.map((r) => {
    const score = targetScore(r)
    return {
      ...r,
      id: `tgt-${r.symbol.toLowerCase()}`,
      projectId: DEMO_PROJECT_ID,
      confidence: clamp01(r.evidenceConfidence!),
      score,
      nextActions: [
        'Confirm biomarker assay strategy with expert review',
        'Enumerate resistance-aware chemotypes',
        'Assemble comparator set from public bioactivity data',
      ],
      status: 'ranked' as const,
      evidenceIds: ['ev-001', 'ev-002', 'ev-004'],
    } as TargetCandidate
  })
  scored.sort((a, b) => b.score - a.score)
  scored.forEach((t, i) => {
    t.rank = i + 1
    t.status = i === 0 ? 'selected' : i >= 4 ? 'exploratory' : 'ranked'
  })
  return scored
}

// ============================================================================
// Hypotheses (3)
// ============================================================================
export function buildHypotheses(): Hypothesis[] {
  return [
    {
      id: 'hyp-001',
      projectId: DEMO_PROJECT_ID,
      targetId: 'tgt-egfr',
      targetSymbol: 'EGFR',
      statement:
        'A mutant-selective, CNS-penetrant EGFR inhibitor could extend durable benefit in EGFR-altered NSCLC, including CNS-metastatic subpopulations.',
      mechanismSummary:
        'Selective inhibition of activating/resistance EGFR alterations while sparing wild-type reduces on-target toxicity; CNS penetration addresses brain-metastatic unmet need.',
      testability: 0.78,
      evidenceIds: ['ev-001', 'ev-002', 'ev-003', 'ev-004'],
      confidence: 0.72,
      limitations:
        'In-silico hypothesis only. No wet-lab validation performed. Contradictory subgroup evidence (ev-007) tempers universal efficacy; requires expert review.',
      status: 'verified',
      validationPlan:
        'Retrospective rediscovery check → comparator benchmarking → prospective biomarker-selected design (expert-led).',
    },
    {
      id: 'hyp-002',
      projectId: DEMO_PROJECT_ID,
      targetId: 'tgt-met',
      targetSymbol: 'MET',
      statement:
        'MET pathway co-targeting may mitigate a recognized bypass-resistance mechanism when combined with EGFR inhibition.',
      mechanismSummary:
        'MET amplification/activation can bypass EGFR blockade; combination hypotheses are motivated by resistance heterogeneity.',
      testability: 0.62,
      evidenceIds: ['ev-006'],
      confidence: 0.58,
      limitations: 'Weaker evidence base; combination toxicity and patient-selection strategy require expert design.',
      status: 'draft',
      validationPlan: 'Resistance-cohort evidence expansion → combination feasibility review.',
    },
    {
      id: 'hyp-003',
      projectId: DEMO_PROJECT_ID,
      targetId: 'tgt-egfr',
      targetSymbol: 'EGFR',
      statement:
        'ctDNA clearance kinetics could serve as an early biomarker for benefit, enabling adaptive trial designs.',
      mechanismSummary:
        'Molecular-response biomarkers may correlate with durable clinical benefit and support adaptive enrollment.',
      testability: 0.66,
      evidenceIds: ['ev-005'],
      confidence: 0.6,
      limitations: 'Biomarker qualification is non-trivial; not a validated surrogate endpoint. Expert biostatistics required.',
      status: 'draft',
      validationPlan: 'Precedent scan → biomarker qualification plan (expert-led).',
    },
  ]
}

// ============================================================================
// Molecules (12 candidates incl. 2 invalid + 2 blocked)
// ============================================================================
interface MolSeed {
  label: string
  smiles: string
  source: MoleculeCandidate['source']
  affinity: number
  qed: number
  novelty: number
  tox: { hERG: number; Ames: number; DILI: number }
  feas: 'High' | 'Medium' | 'Low'
  descriptors: MoleculeDescriptors
  forceHazard?: boolean
  invalid?: boolean
}

const MOL_SEEDS: MolSeed[] = [
  {
    label: 'HF-EGFR-001', smiles: 'CN1C=NC2=C1C(=O)N(C)C(=O)N2C', source: 'generated',
    affinity: -9.6, qed: 0.68, novelty: 0.62, tox: { hERG: 0.24, Ames: 0.16, DILI: 0.28 }, feas: 'High',
    descriptors: { mw: 194.2, logP: -0.07, hbd: 0, hba: 6, tpsa: 58.4, rotatableBonds: 0, aromaticRings: 1 },
  },
  {
    label: 'HF-EGFR-002', smiles: 'CC(=O)Oc1ccccc1C(=O)O', source: 'generated',
    affinity: -8.2, qed: 0.55, novelty: 0.44, tox: { hERG: 0.31, Ames: 0.22, DILI: 0.34 }, feas: 'High',
    descriptors: { mw: 180.2, logP: 1.19, hbd: 1, hba: 4, tpsa: 63.6, rotatableBonds: 3, aromaticRings: 1 },
  },
  {
    label: 'HF-EGFR-003', smiles: 'COc1cc2ncnc(Nc3ccc(F)cc3)c2cc1OC', source: 'generated',
    affinity: -10.8, qed: 0.74, novelty: 0.7, tox: { hERG: 0.36, Ames: 0.19, DILI: 0.3 }, feas: 'Medium',
    descriptors: { mw: 349.4, logP: 3.6, hbd: 1, hba: 5, tpsa: 66.8, rotatableBonds: 5, aromaticRings: 3 },
  },
  {
    label: 'HF-EGFR-004', smiles: 'CC(C)Cc1ccc(cc1)C(C)C(=O)O', source: 'generated',
    affinity: -7.1, qed: 0.5, novelty: 0.4, tox: { hERG: 0.78, Ames: 0.4, DILI: 0.62 }, feas: 'High',
    descriptors: { mw: 206.3, logP: 3.5, hbd: 1, hba: 2, tpsa: 37.3, rotatableBonds: 4, aromaticRings: 1 },
  },
  {
    label: 'HF-EGFR-005', smiles: 'CC(=O)Nc1ccc(O)cc1', source: 'generated',
    affinity: -8.9, qed: 0.6, novelty: 0.5, tox: { hERG: 0.28, Ames: 0.2, DILI: 0.42 }, feas: 'High',
    descriptors: { mw: 151.2, logP: 0.46, hbd: 2, hba: 2, tpsa: 49.3, rotatableBonds: 1, aromaticRings: 1 },
  },
  {
    label: 'HF-EGFR-006', smiles: 'COc1cc(C=O)ccc1O', source: 'generated',
    affinity: -8.6, qed: 0.58, novelty: 0.52, tox: { hERG: 0.55, Ames: 0.48, DILI: 0.5 }, feas: 'Medium',
    descriptors: { mw: 152.1, logP: 1.2, hbd: 1, hba: 3, tpsa: 46.5, rotatableBonds: 2, aromaticRings: 1 },
  },
  {
    label: 'HF-EGFR-007', smiles: 'NC(=O)c1cccnc1', source: 'generated',
    affinity: -9.1, qed: 0.63, novelty: 0.58, tox: { hERG: 0.22, Ames: 0.18, DILI: 0.26 }, feas: 'High',
    descriptors: { mw: 122.1, logP: -0.37, hbd: 1, hba: 3, tpsa: 55.98, rotatableBonds: 1, aromaticRings: 1 },
  },
  {
    label: 'HF-EGFR-008', smiles: 'Cc1ccc(cc1)S(=O)(=O)N', source: 'generated',
    affinity: -9.4, qed: 0.66, novelty: 0.65, tox: { hERG: 0.3, Ames: 0.24, DILI: 0.3 }, feas: 'Medium',
    descriptors: { mw: 171.2, logP: 0.6, hbd: 1, hba: 3, tpsa: 68.5, rotatableBonds: 1, aromaticRings: 1 },
    forceHazard: true,
  },
  {
    label: 'HF-EGFR-009', smiles: 'CCOC(=O)c1ccc(N)cc1', source: 'generated',
    affinity: -9.0, qed: 0.61, novelty: 0.56, tox: { hERG: 0.26, Ames: 0.2, DILI: 0.29 }, feas: 'High',
    descriptors: { mw: 165.2, logP: 1.9, hbd: 1, hba: 3, tpsa: 52.3, rotatableBonds: 3, aromaticRings: 1 },
  },
  {
    label: 'HF-EGFR-010', smiles: 'O=C(O)c1ccccc1O', source: 'generated',
    affinity: -8.0, qed: 0.52, novelty: 0.46, tox: { hERG: 0.34, Ames: 0.26, DILI: 0.33 }, feas: 'High',
    descriptors: { mw: 138.1, logP: 1.19, hbd: 2, hba: 3, tpsa: 57.5, rotatableBonds: 1, aromaticRings: 1 },
    forceHazard: true,
  },
  {
    label: 'HF-EGFR-INV-01', smiles: 'CC(C)(C', source: 'generated',
    affinity: 0, qed: 0, novelty: 0, tox: { hERG: 0, Ames: 0, DILI: 0 }, feas: 'Low',
    descriptors: { mw: 0, logP: 0, hbd: 0, hba: 0, tpsa: 0, rotatableBonds: 0, aromaticRings: 0 },
    invalid: true,
  },
  {
    label: 'HF-EGFR-INV-02', smiles: 'c1ccccc1C2CCC', source: 'generated',
    affinity: 0, qed: 0, novelty: 0, tox: { hERG: 0, Ames: 0, DILI: 0 }, feas: 'Low',
    descriptors: { mw: 0, logP: 0, hbd: 0, hba: 0, tpsa: 0, rotatableBonds: 0, aromaticRings: 0 },
    invalid: true,
  },
]

export function buildMolecules(): MoleculeCandidate[] {
  return MOL_SEEDS.map((s, i) => {
    const validity = RDKitAdapter.validateSmiles(s.smiles)
    const isValid = !s.invalid && validity.valid
    const lv = lipinskiViolations(s.descriptors)
    const bindingNormalized = clamp01((-s.affinity - 5) / 7)
    const admetScore = clamp01(1 - (s.tox.hERG * 0.4 + s.tox.Ames * 0.3 + s.tox.DILI * 0.3))
    const uncertainty = rand(s.label + 'unc', 0.1, 0.34)
    const screen = screenMolecule({ ...s.tox, label: s.label, forceHazard: s.forceHazard })
    const safetyStatus = !isValid ? 'TOOL_ERROR' : screen.status
    const composite = isValid
      ? moleculeComposite({
          bindingNormalized,
          admetScore,
          qed: s.qed,
          lipinskiPass: lv === 0,
          lipinskiViolations: lv,
          synthesisFeasibility: s.feas,
          novelty: s.novelty,
          targetRationale: 0.82,
          confidence: 1 - uncertainty,
          uncertainty,
          safetyStatus,
        })
      : 0
    const recommendation = recommendationFor({
      compositeScore: composite,
      safetyStatus,
      uncertainty,
      validityStatus: isValid ? 'valid' : 'invalid',
    })
    const criticComments: string[] = []
    if (!isValid) criticComments.push(`Structure rejected by Cheminformatics Validator: ${validity.reason}. Regeneration requested.`)
    if (screen.status === 'BLOCKED') criticComments.push('Quarantined by Safety Auditor — reason category shown without actionable detail.')
    if (screen.status === 'REVIEW_REQUIRED') criticComments.push('Elevated predicted toxicity aggregate — routed for expert toxicology review.')
    if (isValid && composite >= 70) criticComments.push('Meets advance threshold; still requires human expert confirmation (in-silico only).')

    const mol: MoleculeCandidate = {
      id: `mol-${String(i + 1).padStart(3, '0')}`,
      projectId: DEMO_PROJECT_ID,
      targetId: 'tgt-egfr',
      label: s.label,
      smiles: s.smiles,
      source: s.source,
      sourceType: 'demo',
      validityStatus: isValid ? 'valid' : 'invalid',
      validityReason: isValid ? undefined : validity.reason,
      descriptors: s.descriptors,
      bindingScore: s.affinity,
      bindingNormalized,
      poseConfidence: isValid ? rand(s.label + 'pose', 0.45, 0.85) : 0,
      admetScore,
      qed: s.qed,
      lipinskiPass: lv === 0,
      lipinskiViolations: lv,
      saScore: rand(s.label + 'sa', 2.0, 5.5, 1),
      hERG: s.tox.hERG,
      Ames: s.tox.Ames,
      DILI: s.tox.DILI,
      cyp: rand(s.label + 'cyp', 0.15, 0.6),
      bbb: rand(s.label + 'bbb', 0.2, 0.8),
      solubility: rand(s.label + 'sol', 0.3, 0.9),
      clearance: rand(s.label + 'cl', 0.2, 0.8),
      bioavailability: rand(s.label + 'ba', 0.35, 0.9),
      novelty: s.novelty,
      ipDistance: rand(s.label + 'ip', 0.4, 0.85),
      uncertainty,
      synthesisFeasibility: s.feas,
      routeConfidence: rand(s.label + 'rc', 0.4, 0.85),
      estimatedComplexity: rand(s.label + 'ec', 0.2, 0.9),
      requiresExpertReview: true,
      safetyStatus,
      compositeScore: composite,
      recommendation,
      evidenceIds: ['ev-001', 'ev-004'],
      criticComments,
      optimizationHistory: isValid
        ? [
            { iteration: 0, action: 'Seed generation', compositeScoreBefore: 0, compositeScoreAfter: Math.max(0, composite - rand(s.label + 'o1', 8, 16)), note: 'Initial candidate from demo generator' },
            { iteration: 1, action: 'Descriptor-guided tweak', compositeScoreBefore: Math.max(0, composite - rand(s.label + 'o1', 8, 16)), compositeScoreAfter: Math.max(0, composite - rand(s.label + 'o2', 3, 7)), note: 'Adjusted logP / TPSA balance' },
            { iteration: 2, action: 'Multi-objective re-rank', compositeScoreBefore: Math.max(0, composite - rand(s.label + 'o2', 3, 7)), compositeScoreAfter: composite, note: 'Re-scored with current weights' },
          ]
        : [],
      createdAt: tOffset(40 + i),
    }
    return mol
  })
}

// ============================================================================
// Safety flags (2 blocked candidates + fake citation)
// ============================================================================
export function buildSafetyFlags(molecules: MoleculeCandidate[]): SafetyFlag[] {
  const flags: SafetyFlag[] = []
  molecules
    .filter((m) => m.safetyStatus === 'BLOCKED')
    .forEach((m, i) => {
      const screen = screenMolecule({ hERG: m.hERG, Ames: m.Ames, DILI: m.DILI, label: m.label, forceHazard: true })
      flags.push({
        id: `sf-blk-${i + 1}`,
        projectId: DEMO_PROJECT_ID,
        entityType: 'molecule',
        entityId: m.id,
        entityLabel: m.label,
        severity: 'critical',
        category: screen.category,
        status: 'BLOCKED',
        redactedSummary: screen.redactedSummary,
        safeAlternative: screen.safeAlternative,
        createdAt: tOffset(70 + i),
      })
    })
  molecules
    .filter((m) => m.safetyStatus === 'REVIEW_REQUIRED')
    .forEach((m, i) => {
      const screen = screenMolecule({ hERG: m.hERG, Ames: m.Ames, DILI: m.DILI, label: m.label })
      flags.push({
        id: `sf-rev-${i + 1}`,
        projectId: DEMO_PROJECT_ID,
        entityType: 'molecule',
        entityId: m.id,
        entityLabel: m.label,
        severity: screen.severity,
        category: screen.category,
        status: 'REVIEW_REQUIRED',
        redactedSummary: screen.redactedSummary,
        safeAlternative: screen.safeAlternative,
        createdAt: tOffset(74 + i),
      })
    })
  flags.push({
    id: 'sf-cite-1',
    projectId: DEMO_PROJECT_ID,
    entityType: 'evidence',
    entityId: 'ev-008',
    entityLabel: 'PMID:00000000 (fabricated)',
    severity: 'high',
    category: 'Fabricated / unverifiable citation',
    status: 'REVIEW_REQUIRED',
    redactedSummary: 'Citation could not be resolved. Demoted to failed; excluded from verified evidence and reports.',
    safeAlternative: 'Replaced by a labeled demo placeholder; hypothesis confidence reduced accordingly.',
    createdAt: tOffset(30),
    resolvedAt: tOffset(31),
  })
  return flags
}

// ============================================================================
// Clinical protocol draft (1)
// ============================================================================
export function buildClinical(recommendedId: string, recommendedLabel: string): ClinicalProtocolDraft {
  return {
    id: 'clin-001',
    projectId: DEMO_PROJECT_ID,
    candidateId: recommendedId,
    candidateLabel: recommendedLabel,
    indication: 'EGFR-altered advanced/metastatic NSCLC (biomarker-selected)',
    targetProductProfile:
      'Oral, mutant-selective, CNS-penetrant EGFR inhibitor intended for biomarker-selected advanced NSCLC, positioned to extend durable benefit with a manageable tolerability profile. (Draft TPP — high-level planning artifact.)',
    phase: 'Phase I/II (biomarker-selected, adaptive)',
    population: 'Adults with EGFR-altered advanced/metastatic NSCLC; resistance and CNS-metastatic strata as expansion cohorts.',
    endpoints: [
      { name: 'Safety & tolerability (DLT, AE profile)', type: 'primary', description: 'Phase I dose-finding primary; expert-defined.' },
      { name: 'Objective response rate (investigator-assessed)', type: 'primary', description: 'Phase II efficacy signal in biomarker-selected cohort.' },
      { name: 'Progression-free survival', type: 'secondary', description: 'Key secondary; requires adequate follow-up.' },
      { name: 'ctDNA molecular response', type: 'secondary', description: 'Exploratory biomarker; not a validated surrogate.' },
      { name: 'CNS response (in CNS-metastatic stratum)', type: 'secondary', description: 'Addresses stated unmet need.' },
    ],
    inclusionLogic: [
      'Confirmed EGFR alteration by validated assay',
      'Measurable disease per standard criteria',
      'Adequate organ function (expert-defined thresholds)',
      'Prior-therapy criteria per stratum',
    ],
    exclusionLogic: [
      'Concurrent condition precluding participation (expert-defined)',
      'Known intolerance to class (where applicable)',
      'Criteria that would confound biomarker interpretation',
    ],
    biomarkerStrategy:
      'Prospective EGFR alteration selection; longitudinal ctDNA for molecular-response exploration; CNS assessment in the relevant stratum. Biomarker qualification is out of scope and expert-led.',
    comparator: 'Standard-of-care per line/region (expert-selected); single-arm signal-seeking acceptable in early phase.',
    risks: [
      { risk: 'On-target/off-tumor toxicity', severity: 'high', mitigation: 'Mutant-selective design; dose-finding; stringent monitoring (expert-led).' },
      { risk: 'Acquired resistance limiting durability', severity: 'high', mitigation: 'Resistance-aware profiling; combination hypotheses in reserve.' },
      { risk: 'Biomarker/endpoint mismatch', severity: 'medium', mitigation: 'Pre-specified biomarker plan; avoid over-reliance on unqualified surrogates.' },
      { risk: 'Population/competitive-landscape mismatch', severity: 'medium', mitigation: 'Precedent scan; niche positioning in resistance/CNS strata.' },
      { risk: 'Regulatory uncertainty', severity: 'medium', mitigation: 'Early alignment; checklist-driven gap analysis (see Regulatory).' },
    ],
    disclaimer: CLINICAL_DISCLAIMER,
    confidence: 0.62,
    createdAt: tOffset(90),
  }
}

// ============================================================================
// Regulatory checklist (1)
// ============================================================================
export function buildRegulatory(): RegulatoryCheck[] {
  const items: Omit<RegulatoryCheck, 'id' | 'projectId'>[] = [
    { jurisdiction: 'FDA', checklistItem: 'Nonclinical package adequacy (tox, PK) for IND-enabling', status: 'gap', evidenceNeeded: 'GLP tox studies, PK/ADME package (wet-lab, expert-led)', riskLevel: 'high', notes: 'In-silico only; nonclinical data not generated by this system.', sourceIds: ['DEMO-FDA-01'] },
    { jurisdiction: 'FDA', checklistItem: 'CMC / manufacturability readiness', status: 'gap', evidenceNeeded: 'CMC development plan (out of scope; no synthesis route produced)', riskLevel: 'medium', notes: 'Feasibility summarized only; no route detail by policy.', sourceIds: ['DEMO-FDA-02'] },
    { jurisdiction: 'FDA', checklistItem: 'Biomarker strategy & companion-diagnostic pathway', status: 'partial', evidenceNeeded: 'Assay validation plan; CDx co-development strategy', riskLevel: 'medium', notes: 'Biomarker plan drafted; qualification expert-led.', sourceIds: ['DEMO-FDA-03'] },
    { jurisdiction: 'FDA', checklistItem: 'Trial design & endpoint acceptability', status: 'partial', evidenceNeeded: 'Endpoint justification; statistical analysis plan', riskLevel: 'medium', notes: 'High-level design drafted; SAP is expert-led.', sourceIds: ['DEMO-FDA-04'] },
    { jurisdiction: 'MFDS', checklistItem: 'IND submission dossier alignment (KR)', status: 'gap', evidenceNeeded: 'KR-specific nonclinical/clinical dossier', riskLevel: 'high', notes: 'Requires local regulatory expertise.', sourceIds: ['DEMO-MFDS-01'] },
    { jurisdiction: 'MFDS', checklistItem: 'Ethics/IRB & informed-consent framework', status: 'partial', evidenceNeeded: 'IRB submission, consent materials', riskLevel: 'low', notes: 'Framework noted; execution expert-led.', sourceIds: ['DEMO-MFDS-02'] },
    { jurisdiction: 'ICH', checklistItem: 'ICH E6(R2) GCP alignment', status: 'partial', evidenceNeeded: 'Quality-management & monitoring plan', riskLevel: 'low', notes: 'Referenced at high level.', sourceIds: ['DEMO-ICH-01'] },
  ]
  return items.map((it, i) => ({ ...it, id: `reg-${String(i + 1).padStart(3, '0')}`, projectId: DEMO_PROJECT_ID }))
}

// ============================================================================
// Evaluation results (1 benchmark summary across modules)
// ============================================================================
export function buildEvaluation(workflowId: string): EvaluationResult[] {
  const rows: Omit<EvaluationResult, 'id' | 'projectId' | 'workflowId' | 'createdAt'>[] = [
    // A. Retrospective rediscovery
    { benchmarkName: 'Retrospective Rediscovery', metricName: 'Target rank percentile (EGFR)', value: 98, unit: '%', target: 90, higherIsBetter: true, status: 'pass', interpretation: 'Known driver rediscovered at top rank.' },
    { benchmarkName: 'Retrospective Rediscovery', metricName: 'Known mechanism recovered', value: 1, unit: 'bool', target: 1, higherIsBetter: true, status: 'pass', interpretation: 'Mutant-selective mechanism recovered.' },
    { benchmarkName: 'Retrospective Rediscovery', metricName: 'Candidate similarity band', value: 0.71, target: 0.6, higherIsBetter: true, status: 'pass', interpretation: 'Recovered chemotype family in expected band.' },
    { benchmarkName: 'Retrospective Rediscovery', metricName: 'Evidence verification rate', value: 0.86, target: 0.8, higherIsBetter: true, status: 'pass', interpretation: 'Demo-labeled + verified share above threshold.' },
    { benchmarkName: 'Retrospective Rediscovery', metricName: 'False citation rate', value: 0.0, unit: '%', target: 0, higherIsBetter: false, status: 'pass', interpretation: 'Fabricated citation caught and demoted.' },
    // B. Molecule generation
    { benchmarkName: 'Molecule Generation', metricName: 'Validity', value: 0.83, target: 0.8, higherIsBetter: true, status: 'pass', interpretation: '10/12 valid; 2 invalid caught for self-correction demo.' },
    { benchmarkName: 'Molecule Generation', metricName: 'Uniqueness', value: 1.0, target: 0.9, higherIsBetter: true, status: 'pass', interpretation: 'All candidate structures unique.' },
    { benchmarkName: 'Molecule Generation', metricName: 'Novelty', value: 0.56, target: 0.5, higherIsBetter: true, status: 'pass', interpretation: 'Mean novelty above threshold.' },
    { benchmarkName: 'Molecule Generation', metricName: 'Diversity', value: 0.68, target: 0.6, higherIsBetter: true, status: 'pass', interpretation: 'Adequate scaffold diversity.' },
    { benchmarkName: 'Molecule Generation', metricName: 'Toxicity fail rate', value: 0.17, unit: '%', target: 0.25, higherIsBetter: false, status: 'pass', interpretation: 'Within acceptable range; flagged items quarantined.' },
    // C. ADMET
    { benchmarkName: 'ADMET Prediction', metricName: 'hERG ROC-AUC (demo)', value: 0.82, target: 0.8, higherIsBetter: true, status: 'pass', interpretation: 'Demo classification performance.' },
    { benchmarkName: 'ADMET Prediction', metricName: 'Solubility RMSE (demo)', value: 0.71, unit: 'logS', target: 0.8, higherIsBetter: false, status: 'pass', interpretation: 'Demo regression error within target.' },
    { benchmarkName: 'ADMET Prediction', metricName: 'Calibration (ECE)', value: 0.07, target: 0.1, higherIsBetter: false, status: 'pass', interpretation: 'Reasonably calibrated (demo).' },
    // D. Docking
    { benchmarkName: 'Docking / Enrichment', metricName: 'Enrichment factor (EF1%)', value: 12.4, unit: 'x', target: 5, higherIsBetter: true, status: 'pass', interpretation: 'Demo enrichment above baseline.' },
    { benchmarkName: 'Docking / Enrichment', metricName: 'Docking failure rate', value: 0.08, unit: '%', target: 0.15, higherIsBetter: false, status: 'pass', interpretation: 'Failures recorded and confidence reduced.' },
    // E. Agent
    { benchmarkName: 'Agent Metrics', metricName: 'Task success rate', value: 0.94, target: 0.85, higherIsBetter: true, status: 'pass', interpretation: 'Stages completed with valid artifacts.' },
    { benchmarkName: 'Agent Metrics', metricName: 'Self-correction rate', value: 1.0, target: 0.8, higherIsBetter: true, status: 'pass', interpretation: 'All injected errors detected & corrected.' },
    { benchmarkName: 'Agent Metrics', metricName: 'Tool error recovery rate', value: 1.0, target: 0.9, higherIsBetter: true, status: 'pass', interpretation: 'Fallback to demo recorded; no fake real result.' },
    { benchmarkName: 'Agent Metrics', metricName: 'Cost per completed workflow', value: 0.42, unit: 'USD', target: 1.0, higherIsBetter: false, status: 'pass', interpretation: 'Estimated demo cost within budget.' },
    // F. Safety
    { benchmarkName: 'Safety Metrics', metricName: 'Blocked unsafe outputs', value: 2, target: 1, higherIsBetter: true, status: 'pass', interpretation: '2 candidates quarantined by safety gate.' },
    { benchmarkName: 'Safety Metrics', metricName: 'Audit completeness', value: 1.0, target: 1.0, higherIsBetter: true, status: 'pass', interpretation: 'Every agent/tool/validation event logged.' },
  ]
  return rows.map((r, i) => ({
    ...r,
    id: `eval-${String(i + 1).padStart(3, '0')}`,
    projectId: DEMO_PROJECT_ID,
    workflowId,
    createdAt: tOffset(100 + i),
  }))
}

// ============================================================================
// Training studio seed data (jobs, datasets, checkpoints)
// ============================================================================
export function buildTrainingJobs(): TrainingJob[] {
  function curve(seed: string, n = 24): { step: number; loss: number; metric: number }[] {
    const r = seeded(seed)
    let loss = 1.6
    let metric = 0.5
    return Array.from({ length: n }, (_, i) => {
      loss = Math.max(0.08, loss - r() * 0.09)
      metric = Math.min(0.95, metric + r() * 0.02)
      return { step: i + 1, loss: Math.round(loss * 1000) / 1000, metric: Math.round(metric * 1000) / 1000 }
    })
  }
  return [
    {
      id: 'job-admet-herg', projectId: DEMO_PROJECT_ID, name: 'ADMET-hERG-ChemProp-demo', jobType: 'admet_finetune',
      modelFamily: 'ChemProp (D-MPNN)', dataset: 'TDC hERG (demo)', objective: 'hERG blocker classification',
      status: 'complete', progress: 100,
      metrics: [{ name: 'ROC-AUC', value: 0.86, target: 0.8 }, { name: 'PR-AUC', value: 0.79 }, { name: 'ECE', value: 0.06 }],
      curve: curve('herg'), checkpointName: 'ckpt-herg-v0', mode: 'demo',
      hyperparameters: { epochs: 30, lr: 0.0005, hidden: 300, depth: 4 },
      logs: ['[demo] loaded TDC hERG split', '[demo] epoch 30/30 · val ROC-AUC 0.86', '[demo] staged checkpoint ckpt-herg-v0', 'Demo Simulation — no model was actually trained.'],
      createdAt: tOffset(10), completedAt: tOffset(28),
    },
    {
      id: 'job-reinvent-egfr', projectId: DEMO_PROJECT_ID, name: 'REINVENT4-EGFR-RL-demo', jobType: 'reinvent_rl',
      modelFamily: 'REINVENT4 (RL)', dataset: 'Seed compounds + scoring fn (demo)', objective: 'Target-conditioned generation for EGFR',
      status: 'complete', progress: 100,
      metrics: [{ name: 'Validity', value: 0.94 }, { name: 'Novelty', value: 0.71 }, { name: 'Diversity', value: 0.68 }, { name: 'Safety fail rate', value: 0.05 }],
      curve: curve('reinvent'), checkpointName: 'ckpt-reinvent-egfr-v0', mode: 'demo',
      hyperparameters: { steps: 500, sigma: 128, batch: 128, safetyPenalty: 'on' },
      logs: ['[demo] initialized prior', '[demo] RL step 500/500 · mean score 0.62', '[demo] safety scoring active — hazardous space penalized', 'Demo Simulation — no model was actually trained.'],
      createdAt: tOffset(12), completedAt: tOffset(34),
    },
    {
      id: 'job-reward-v0', projectId: DEMO_PROJECT_ID, name: 'CompositeReward-v0-demo', jobType: 'reward_model',
      modelFamily: 'Gradient-boosted scorer', dataset: 'Docking+ADMET+expert labels (demo)', objective: 'Learned composite scoring model',
      status: 'complete', progress: 100,
      metrics: [{ name: 'Val R²', value: 0.78 }, { name: 'Spearman', value: 0.81 }, { name: 'MAE', value: 0.09 }],
      curve: curve('reward'), checkpointName: 'ckpt-reward-v0', mode: 'demo',
      hyperparameters: { trees: 400, depth: 6, lr: 0.05 },
      logs: ['[demo] assembled feature matrix', '[demo] feature importance: binding>ADMET>QED>novelty', '[demo] staged ckpt-reward-v0', 'Demo Simulation — no model was actually trained.'],
      createdAt: tOffset(14), completedAt: tOffset(30),
    },
    {
      id: 'job-router', projectId: DEMO_PROJECT_ID, name: 'ToolRouter-small-demo', jobType: 'tool_router',
      modelFamily: 'Distilled router (small)', dataset: 'Task traces (demo)', objective: 'Route simple tasks to smaller models',
      status: 'running', progress: 62,
      metrics: [{ name: 'Routing accuracy', value: 0.9, target: 0.9 }, { name: 'Cost reduction', value: 0.41 }, { name: 'Failure rate', value: 0.04 }],
      curve: curve('router', 16), checkpointName: 'ckpt-router-v0', mode: 'demo',
      hyperparameters: { epochs: 8, lr: 0.001 },
      logs: ['[demo] distilling from orchestrator traces', '[demo] step 10/16 · routing acc 0.90', 'Demo Simulation — no model was actually trained.'],
      createdAt: tOffset(20),
    },
  ]
}

export function buildDatasets(): DatasetEntry[] {
  return [
    { id: 'ds-1', name: 'TDC hERG (demo slice)', source: 'Therapeutics Data Commons', taskType: 'classification', endpoint: 'hERG blocker', size: 13000, licenseStatus: 'Open (demo)', qualityNotes: 'Public benchmark; label noise typical.', split: '80/10/10 scaffold', leakageWarning: false },
    { id: 'ds-2', name: 'TDC Solubility (AqSolDB, demo)', source: 'TDC', taskType: 'regression', endpoint: 'aqueous solubility (logS)', size: 9982, licenseStatus: 'Open (demo)', qualityNotes: 'Aggregated sources; unit harmonization applied.', split: '80/10/10 random', leakageWarning: true },
    { id: 'ds-3', name: 'ChEMBL-derived EGFR actives (demo)', source: 'ChEMBL (simulated)', taskType: 'regression', endpoint: 'pChEMBL', size: 4200, licenseStatus: 'Attribution (demo)', qualityNotes: 'Assay heterogeneity; requires curation.', split: '70/15/15 temporal', leakageWarning: true },
    { id: 'ds-4', name: 'Ames mutagenicity (demo)', source: 'TDC', taskType: 'classification', endpoint: 'Ames', size: 7278, licenseStatus: 'Open (demo)', qualityNotes: 'Standard genotoxicity benchmark.', split: '80/10/10 scaffold', leakageWarning: false },
  ]
}

export function buildCheckpoints(): CheckpointEntry[] {
  return [
    { id: 'ck-1', name: 'ckpt-herg-v0', modelFamily: 'ChemProp', trainingData: 'TDC hERG (demo)', metrics: [{ name: 'ROC-AUC', value: 0.86 }], createdAt: tOffset(28), status: 'validated', notes: 'Demo checkpoint.', mode: 'demo' },
    { id: 'ck-2', name: 'ckpt-reinvent-egfr-v0', modelFamily: 'REINVENT4', trainingData: 'Seed + scoring (demo)', metrics: [{ name: 'Validity', value: 0.94 }, { name: 'Novelty', value: 0.71 }], createdAt: tOffset(34), status: 'staged', notes: 'Safety-constrained generation checkpoint.', mode: 'demo' },
    { id: 'ck-3', name: 'ckpt-reward-v0', modelFamily: 'GBM scorer', trainingData: 'Composite features (demo)', metrics: [{ name: 'Spearman', value: 0.81 }], createdAt: tOffset(30), status: 'staged', notes: 'Learned composite scorer.', mode: 'demo' },
  ]
}
