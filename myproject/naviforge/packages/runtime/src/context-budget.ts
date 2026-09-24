import { estimateTokens, estimateToolsTokens } from './working-set.js'
import type { OpenAiFunctionTool } from '@naviforge/shared'

/** Prime/Pi-style proactive compaction thresholds (fraction of maxInputTokens). */
export const CONTEXT_BUDGET_RATIOS = {
  soft: 0.65,
  hard: 0.8,
  stop: 0.92,
} as const

export function estimateInputTokens(opts: {
  system: string
  user: string
  tools?: readonly OpenAiFunctionTool[]
  toolsTokens?: number
}): number {
  const tools =
    opts.toolsTokens ?? (opts.tools ? estimateToolsTokens(opts.tools) : 0)
  return estimateTokens(opts.system) + estimateTokens(opts.user) + tools
}

export function inputTokenRatio(opts: {
  system: string
  user: string
  tools?: readonly OpenAiFunctionTool[]
  toolsTokens?: number
  maxInputTokens: number
}): number {
  if (opts.maxInputTokens <= 0) return 0
  return Math.min(
    1,
    estimateInputTokens(opts) / opts.maxInputTokens
  )
}

export function l1ProjectionCap(maxInputTokens: number, ratio: number): number {
  if (ratio >= CONTEXT_BUDGET_RATIOS.hard) {
    return Math.max(2_000, Math.floor(maxInputTokens * 0.35))
  }
  if (ratio >= CONTEXT_BUDGET_RATIOS.soft) {
    return Math.max(3_000, Math.floor(maxInputTokens * 0.5))
  }
  return maxInputTokens
}
