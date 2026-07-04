import type { BusinessAssumptions } from '@/types'

// Business/social value model (Section 18). Ranges, not guarantees.
export const DEFAULT_BUSINESS: BusinessAssumptions = {
  literatureTriageHours: 40,
  targetPrioritizationDays: 10,
  moleculeScreeningCount: 500,
  costPerResearcherHour: 85,
  workflowsPerMonth: 6,
  percentTimeSaved: 55,
  llmToolRunCost: 0.5,
}

export interface BusinessValue {
  timeSavedHours: number
  grossSaved: number
  costSaved: number
  perWorkflowHours: number
  qualitative: string
}

export function computeBusinessValue(a: BusinessAssumptions): BusinessValue {
  const manualHoursPerWorkflow = a.literatureTriageHours + a.targetPrioritizationDays * 8 + a.moleculeScreeningCount * 0.05
  const savedFraction = Math.max(0, Math.min(1, a.percentTimeSaved / 100))
  const perWorkflowHours = Math.round(manualHoursPerWorkflow * savedFraction)
  const timeSavedHours = perWorkflowHours * a.workflowsPerMonth
  const grossSaved = Math.round(timeSavedHours * a.costPerResearcherHour)
  const runCost = a.llmToolRunCost * a.workflowsPerMonth
  const costSaved = Math.round(grossSaved - runCost)
  return {
    timeSavedHours,
    grossSaved,
    costSaved,
    perWorkflowHours,
    qualitative:
      'Value comes from narrowing the search space, documenting rationale, and accelerating candidate prioritization — not from replacing wet-lab validation or expert review.',
  }
}
