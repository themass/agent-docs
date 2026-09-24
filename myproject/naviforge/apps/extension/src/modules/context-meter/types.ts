import type { ContextBreakdown } from '@naviforge/context-metrics'
import { contextUsageRatio, runBudgetRatio } from '@naviforge/context-metrics'
import type { TraceRecord } from '@naviforge/session'
import { latestContextBreakdown } from '@naviforge/context-metrics'

export type ContextMeterProps = {
  records: readonly TraceRecord[]
  tokenUsage?: { lastPrompt: number; lastCompletion: number; runTotal: number } | null
  className?: string
}

export function selectContextBreakdown(records: readonly TraceRecord[]): ContextBreakdown | null {
  return latestContextBreakdown(records)
}

export function formatContextMeterLabel(breakdown: ContextBreakdown): string {
  const pct = Math.round(contextUsageRatio(breakdown) * 100)
  return `context ${formatContextTokens(breakdown.grandTotalTokens)} / ${formatContextTokens(breakdown.limitInputTokens)} (${pct}%)`
}

export function formatContextTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(1)}k`
  return String(tokens)
}

export { contextUsageRatio, runBudgetRatio }
