import type { ContextBlockMetric, ContextBreakdown, ContextCompactionMetric } from './types.js'

/** CJK-heavy pages; ~2 chars/token is conservative. */
export function estimateTokens(text: string): number {
  return Math.ceil(text.length / 2)
}

export type BuildContextBreakdownInput = {
  /** @deprecated Prefer `systemBlocks` for segmented UI. */
  system?: string
  systemBlocks?: Array<{ id: string; label: string; text: string }>
  blocks: Array<{ id: string; label: string; text: string }>
  limitInputTokens: number
  runTokenBudget: number
  runTotalTokens: number
  pressured?: boolean
  compaction?: ContextCompactionMetric
}

function toBlockMetric(block: { id: string; label: string; text: string }): ContextBlockMetric {
  return {
    id: block.id,
    label: block.label,
    chars: block.text.length,
    tokens: estimateTokens(block.text),
  }
}

export function buildContextBreakdown(input: BuildContextBreakdownInput): ContextBreakdown {
  const systemParts =
    input.systemBlocks?.length
      ? input.systemBlocks
      : input.system
        ? [{ id: 'system', label: 'System prompt', text: input.system }]
        : []
  const systemTokens = systemParts.reduce((sum, block) => sum + estimateTokens(block.text), 0)
  const userBlockMetrics = input.blocks.map(toBlockMetric)
  const userTotalTokens = userBlockMetrics.reduce((sum, block) => sum + block.tokens, 0)
  const blockMetrics: ContextBlockMetric[] = [
    ...systemParts.map(toBlockMetric),
    ...userBlockMetrics,
  ]
  const grandTotalTokens = systemTokens + userTotalTokens
  return {
    limitInputTokens: input.limitInputTokens,
    runTokenBudget: input.runTokenBudget,
    runTotalTokens: input.runTotalTokens,
    systemTokens,
    blocks: blockMetrics,
    userTotalTokens,
    grandTotalTokens,
    pressured: Boolean(input.pressured),
    compaction: input.compaction,
  }
}

export function contextUsageRatio(breakdown: ContextBreakdown): number {
  if (breakdown.limitInputTokens <= 0) return 0
  return Math.min(1, breakdown.grandTotalTokens / breakdown.limitInputTokens)
}

export function runBudgetRatio(breakdown: ContextBreakdown): number {
  if (breakdown.runTokenBudget <= 0) return 0
  return Math.min(1, breakdown.runTotalTokens / breakdown.runTokenBudget)
}
