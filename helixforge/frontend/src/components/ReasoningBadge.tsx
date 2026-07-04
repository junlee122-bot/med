import { Badge } from '@/components/ui'

// Maps a reasoning-source type to a Badge tone so provenance is always visible.
const REASONING_TONE: Record<string, string> = {
  REAL_LLM_OUTPUT: 'green',
  RECORDED_LLM_OUTPUT: 'cyan',
  DETERMINISTIC_FALLBACK: 'slate',
  LLM_BUDGET_BLOCKED: 'amber',
  LLM_SAFETY_BLOCKED: 'red',
  LLM_TOOL_ERROR: 'red',
  LLM_OUTPUT_INVALID: 'amber',
}

export function ReasoningBadge({ type }: { type: string }) {
  if (!type) return null
  return <Badge tone={REASONING_TONE[type] || 'slate'}>{type.replace(/_/g, ' ')}</Badge>
}
