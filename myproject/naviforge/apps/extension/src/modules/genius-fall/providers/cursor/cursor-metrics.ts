import type { MetricValue, QuotaMetricDef } from '../../types.js'
import { normalizeCursorSnapshot, type CursorNormalized } from './cursor-normalize.js'
import type { CursorRawSnapshot } from './cursor-api.js'

export const CURSOR_METRICS: readonly QuotaMetricDef[] = [
  { id: 'spend', title: '个人额度', section: 'summary', order: 0 },
  { id: 'cycle', title: '账单周期', section: 'billing', order: 0 },
  { id: 'plan', title: '套餐', section: 'billing', order: 1 },
  { id: 'auto_api_split', title: 'Auto / API 占比', section: 'billing', order: 2 },
  { id: 'team_spend', title: '团队额度', section: 'team', order: 0 },
  { id: 'models', title: '按模型用量', section: 'details', order: 0 },
] as const

function norm(raw: unknown): CursorNormalized {
  return normalizeCursorSnapshot(raw as CursorRawSnapshot)
}

export function extractCursorMetric(metricId: string, raw: unknown): MetricValue | null {
  const data = norm(raw)
  switch (metricId) {
    case 'spend': {
      const { totalSpendUsd, limitUsd, percentUsed } = data.planUsage
      if (totalSpendUsd == null && limitUsd == null && percentUsed == null) return null
      const spent = totalSpendUsd ?? 0
      const remaining =
        totalSpendUsd != null && limitUsd != null ? Math.max(0, limitUsd - totalSpendUsd) : null
      return {
        kind: 'currency',
        spentUsd: spent,
        limitUsd,
        remainingUsd: remaining,
        percentUsed,
      }
    }
    case 'cycle': {
      const { billingCycleStart, billingCycleEnd } = data.planUsage
      if (!billingCycleStart || !billingCycleEnd) return null
      return { kind: 'countdown', cycleStart: billingCycleStart, cycleEnd: billingCycleEnd }
    }
    case 'plan': {
      const parts = [data.planName, data.isTeam ? '团队' : null].filter(Boolean)
      if (!parts.length) return null
      return { kind: 'text', text: parts.join(' · ') }
    }
    case 'auto_api_split': {
      const { autoPercentUsed, apiPercentUsed } = data.planUsage
      if (autoPercentUsed == null && apiPercentUsed == null) return null
      const items = [
        autoPercentUsed != null ? { label: 'Auto', value: `${autoPercentUsed.toFixed(1)}%` } : null,
        apiPercentUsed != null ? { label: 'API', value: `${apiPercentUsed.toFixed(1)}%` } : null,
      ].filter((x): x is { label: string; value: string } => x != null)
      return { kind: 'list', items }
    }
    case 'team_spend': {
      if (!data.isTeam || !data.teamUsage) return null
      const t = data.teamUsage
      if (t.spentUsd == null && t.limitUsd == null) return null
      const remaining =
        t.spentUsd != null && t.limitUsd != null ? Math.max(0, t.limitUsd - t.spentUsd) : null
      return {
        kind: 'currency',
        spentUsd: t.spentUsd ?? 0,
        limitUsd: t.limitUsd,
        remainingUsd: remaining,
        percentUsed: t.percentUsed,
      }
    }
    case 'models': {
      if (!data.modelRows.length) return null
      return {
        kind: 'list',
        items: data.modelRows.map((row) => ({
          label: row.model,
          value: `$${row.costUsd.toFixed(2)}`,
          hint: `in ${row.inputTokens.toLocaleString()} · out ${row.outputTokens.toLocaleString()}`,
        })),
      }
    }
    default:
      return null
  }
}
