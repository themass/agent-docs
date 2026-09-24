import type { CursorRawSnapshot } from './cursor-api.js'

export type CursorPlanUsage = {
  totalSpendUsd: number | null
  limitUsd: number | null
  percentUsed: number | null
  autoPercentUsed: number | null
  apiPercentUsed: number | null
  billingCycleStart: string | null
  billingCycleEnd: string | null
}

export type CursorTeamUsage = {
  kind: 'pooled' | 'individual' | null
  spentUsd: number | null
  limitUsd: number | null
  percentUsed: number | null
}

export type CursorModelRow = {
  model: string
  inputTokens: number
  outputTokens: number
  cacheReadTokens: number
  cacheWriteTokens: number
  costUsd: number
}

export type CursorNormalized = {
  planName: string | null
  planUsage: CursorPlanUsage
  teamUsage: CursorTeamUsage | null
  isTeam: boolean
  modelRows: CursorModelRow[]
}

export function normalizeCursorSnapshot(raw: CursorRawSnapshot): CursorNormalized {
  const fromSummary = normalizeFromUsageSummary(raw.usageSummary)
  const planUsageRaw = dig(raw.periodUsage, ['planUsage']) ?? dig(raw.periodUsage, ['PlanUsage'])
  const spendLimit =
    dig(raw.periodUsage, ['spendLimitUsage']) ?? dig(raw.periodUsage, ['SpendLimitUsage'])

  const planUsage: CursorPlanUsage = fromSummary?.planUsage ?? {
    totalSpendUsd: readMoney(planUsageRaw, ['totalSpend', 'total_spend']),
    limitUsd: readMoney(planUsageRaw, ['limit', 'spendLimit', 'spend_limit']),
    percentUsed: readNumber(planUsageRaw, ['totalPercentUsed', 'total_percent_used']),
    autoPercentUsed: readNumber(planUsageRaw, ['autoPercentUsed', 'auto_percent_used']),
    apiPercentUsed: readNumber(planUsageRaw, ['apiPercentUsed', 'api_percent_used']),
    billingCycleStart:
      readString(planUsageRaw, 'billingCycleStart') ??
      readString(planUsageRaw, 'billing_cycle_start'),
    billingCycleEnd:
      readString(planUsageRaw, 'billingCycleEnd') ?? readString(planUsageRaw, 'billing_cycle_end'),
  }

  const teamUsage = fromSummary?.teamUsage ?? normalizeTeamUsage(spendLimit)
  const planName =
    readString(dig(raw.planInfo, ['planInfo']), 'planName') ??
    readString(dig(raw.planInfo, ['PlanInfo']), 'planName') ??
    readString(raw.planInfo, 'planName') ??
    readString(raw.stripeProfile, 'membershipType') ??
    readString(raw.usageSummary, 'membershipType') ??
    null

  const isTeam = Boolean(
    readString(raw.stripeProfile, 'teamId') ||
      readString(raw.stripeProfile, 'team_id') ||
      readString(raw.usageSummary, 'limitType') === 'team' ||
      teamUsage?.kind === 'pooled'
  )

  return {
    planName,
    planUsage,
    teamUsage,
    isTeam,
    modelRows: normalizeModelRows(raw.usageEvents),
  }
}

function normalizeTeamUsage(spendLimit: unknown): CursorTeamUsage | null {
  if (!spendLimit || typeof spendLimit !== 'object') return null
  const pooled = dig(spendLimit, ['pooled']) ?? dig(spendLimit, ['Pooled'])
  const individual = dig(spendLimit, ['individual']) ?? dig(spendLimit, ['Individual'])
  const block = pooled ?? individual
  if (!block) return null
  return {
    kind: pooled ? 'pooled' : individual ? 'individual' : null,
    spentUsd: readMoney(block, ['spent', 'totalSpend', 'total_spend']),
    limitUsd: readMoney(block, ['limit', 'spendLimit']),
    percentUsed: readNumber(block, ['percentUsed', 'percent_used', 'totalPercentUsed']),
  }
}

function normalizeFromUsageSummary(
  usageSummary: unknown
): { planUsage: CursorPlanUsage; teamUsage: CursorTeamUsage | null } | null {
  if (!usageSummary || typeof usageSummary !== 'object') return null
  const plan = dig(usageSummary, ['individualUsage', 'plan'])
  const onDemand = dig(usageSummary, ['individualUsage', 'onDemand'])
  const teamOnDemand = dig(usageSummary, ['teamUsage', 'onDemand'])
  const teamPooled = dig(usageSummary, ['teamUsage', 'pooled'])

  const planUsed =
    readMoney(plan, ['used', 'totalSpend', 'spent']) ??
    readMoney(dig(plan, ['breakdown']), ['total', 'used'])
  const onDemandUsed = readMoney(onDemand, ['used', 'spent'])
  const planLimit = readMoney(plan, ['limit'])
  const onDemandLimit = readMoney(onDemand, ['limit'])
  const totalSpendUsd = planUsed ?? onDemandUsed
  const limitUsd = planLimit ?? onDemandLimit

  const planUsage: CursorPlanUsage = {
    totalSpendUsd,
    limitUsd,
    percentUsed:
      readNumber(plan, ['totalPercentUsed']) ??
      readNumber(onDemand, ['totalPercentUsed']) ??
      pctFromUsedLimit(totalSpendUsd, limitUsd),
    autoPercentUsed: readNumber(plan, ['autoPercentUsed']),
    apiPercentUsed: readNumber(plan, ['apiPercentUsed']),
    billingCycleStart: readString(usageSummary, 'billingCycleStart'),
    billingCycleEnd: readString(usageSummary, 'billingCycleEnd'),
  }

  const teamBlock = teamPooled ?? teamOnDemand
  const teamUsage: CursorTeamUsage | null = teamBlock
    ? {
        kind: teamPooled ? 'pooled' : 'individual',
        spentUsd: readMoney(teamBlock, ['used', 'spent']),
        limitUsd: readMoney(teamBlock, ['limit']),
        percentUsed: pctFromUsedLimit(
          readMoney(teamBlock, ['used', 'spent']),
          readMoney(teamBlock, ['limit'])
        ),
      }
    : null

  if (
    planUsage.totalSpendUsd == null &&
    planUsage.limitUsd == null &&
    planUsage.percentUsed == null &&
    !teamUsage
  ) {
    return null
  }
  return { planUsage, teamUsage }
}

function pctFromUsedLimit(used: number | null, limit: number | null): number | null {
  if (used == null || limit == null || limit <= 0) return null
  return Math.min(100, (used / limit) * 100)
}

function normalizeModelRows(usageEvents: unknown): CursorModelRow[] {
  const events =
    dig(usageEvents, ['aggregatedUsageEvents']) ??
    dig(usageEvents, ['AggregatedUsageEvents']) ??
    dig(usageEvents, ['events']) ??
    usageEvents
  if (!Array.isArray(events)) return []
  return events
    .map((row) => {
      if (!row || typeof row !== 'object') return null
      const r = row as Record<string, unknown>
      const model =
        readString(r, 'model') ?? readString(r, 'modelName') ?? readString(r, 'model_name') ?? 'unknown'
      const costUsd = readMoney(r, ['cost', 'totalCost', 'total_cost', 'spend']) ?? 0
      return {
        model,
        inputTokens: readNumber(r, ['inputTokens', 'input_tokens']) ?? 0,
        outputTokens: readNumber(r, ['outputTokens', 'output_tokens']) ?? 0,
        cacheReadTokens: readNumber(r, ['cacheReadTokens', 'cache_read_tokens']) ?? 0,
        cacheWriteTokens: readNumber(r, ['cacheWriteTokens', 'cache_write_tokens']) ?? 0,
        costUsd,
      }
    })
    .filter((r): r is CursorModelRow => r != null)
    .sort((a, b) => b.costUsd - a.costUsd)
}

function dig(obj: unknown, keys: string[]): unknown {
  let cur: unknown = obj
  for (const key of keys) {
    if (!cur || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[key]
  }
  return cur
}

function readString(obj: unknown, key: string): string | null {
  if (!obj || typeof obj !== 'object') return null
  const v = (obj as Record<string, unknown>)[key]
  return typeof v === 'string' && v ? v : null
}

function readNumber(obj: unknown, keys: string | string[]): number | null {
  if (!obj || typeof obj !== 'object') return null
  const list = Array.isArray(keys) ? keys : [keys]
  for (const key of list) {
    const v = (obj as Record<string, unknown>)[key]
    if (typeof v === 'number' && Number.isFinite(v)) return v
  }
  return null
}

/** Cents or dollars — Cursor payloads vary; treat large ints as cents. */
function readMoney(obj: unknown, keys: string | string[]): number | null {
  const n = readNumber(obj, keys)
  if (n == null) return null
  if (Math.abs(n) >= 10_000 && Number.isInteger(n)) return n / 100
  return n
}
