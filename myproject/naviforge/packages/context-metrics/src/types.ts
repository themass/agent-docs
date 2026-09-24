/** Token/context breakdown for UI meters (Cursor / DSH-style). */

export type ContextBlockMetric = {
  id: string
  label: string
  chars: number
  tokens: number
}

export type ContextCompactionMetric = {
  beforeTokens: number
  afterTokens: number
  coveredRecords: number
}

export type ContextBreakdown = {
  /** Single-prompt input cap (estimated). */
  limitInputTokens: number
  /** Cumulative run usage cap; 0 = unlimited. */
  runTokenBudget: number
  runTotalTokens: number
  systemTokens: number
  blocks: ContextBlockMetric[]
  userTotalTokens: number
  grandTotalTokens: number
  /** L1 projection still over limit before fitting. */
  pressured: boolean
  compaction?: ContextCompactionMetric
}

export type MetricsContextPayload = {
  turn?: number
  breakdown: ContextBreakdown
}
