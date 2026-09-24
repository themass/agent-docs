import './register-providers.js'
import type { MetricValue } from './types.js'
import { refreshProviderById } from './orchestrator.js'
import type { GeniusFallHudState } from './hud-types.js'
import { normalizeCursorSnapshot } from './providers/cursor/cursor-normalize.js'
import type { CursorRawSnapshot } from './providers/cursor/cursor-api.js'

function pickCurrency(
  metrics: Array<{ def: { id: string }; value: MetricValue | null }>,
  id: string
): Extract<MetricValue, { kind: 'currency' }> | null {
  const row = metrics.find((m) => m.def.id === id)
  if (row?.value?.kind === 'currency') return row.value
  return null
}

function pickCountdown(
  metrics: Array<{ def: { id: string }; value: MetricValue | null }>
): string | null {
  const row = metrics.find((m) => m.def.id === 'cycle')
  if (row?.value?.kind === 'countdown') return row.value.cycleEnd
  return null
}

function modelSpendTotal(raw: CursorRawSnapshot): number | null {
  const norm = normalizeCursorSnapshot(raw)
  const sum = norm.modelRows.reduce((acc, row) => acc + row.costUsd, 0)
  return sum > 0 ? sum : null
}

function enrichPersonalFromRaw(
  raw: CursorRawSnapshot,
  spend: Extract<MetricValue, { kind: 'currency' }> | null
): Pick<
  GeniusFallHudState,
  'spentUsd' | 'limitUsd' | 'percentUsed' | 'remainingUsd' | 'personalDisplay'
> {
  const norm = normalizeCursorSnapshot(raw)
  let spentUsd = spend?.spentUsd ?? null
  let limitUsd = spend?.limitUsd ?? null
  let percentUsed = spend?.percentUsed ?? null
  let remainingUsd = spend?.remainingUsd ?? null

  const individual =
    norm.teamUsage?.kind === 'individual'
      ? norm.teamUsage
      : norm.planUsage.totalSpendUsd != null
        ? {
            spentUsd: norm.planUsage.totalSpendUsd,
            limitUsd: norm.planUsage.limitUsd,
            percentUsed: norm.planUsage.percentUsed,
          }
        : null

  if (spentUsd == null && individual?.spentUsd != null) spentUsd = individual.spentUsd
  if (limitUsd == null && individual?.limitUsd != null) limitUsd = individual.limitUsd
  if (percentUsed == null && individual?.percentUsed != null) percentUsed = individual.percentUsed

  const modelTotal = modelSpendTotal(raw)
  if (spentUsd == null && modelTotal != null) spentUsd = modelTotal

  if (percentUsed == null && spentUsd != null && limitUsd != null && limitUsd > 0) {
    percentUsed = Math.min(100, (spentUsd / limitUsd) * 100)
  }
  if (remainingUsd == null && spentUsd != null && limitUsd != null) {
    remainingUsd = Math.max(0, limitUsd - spentUsd)
  }

  const personalDisplay: GeniusFallHudState['personalDisplay'] =
    percentUsed != null ? 'percent' : spentUsd != null ? 'money' : undefined

  return { spentUsd, limitUsd, percentUsed, remainingUsd, personalDisplay }
}

export async function fetchGeniusFallHudState(): Promise<GeniusFallHudState> {
  const snap = await refreshProviderById('cursor')
  if (!snap?.ok) {
    return {
      ok: false,
      error: snap?.error ?? '无法拉取额度',
      label: 'CURSOR',
      spentUsd: null,
      limitUsd: null,
      percentUsed: null,
      remainingUsd: null,
      cycleEnd: null,
      teamPercent: null,
      updatedAt: snap?.fetchedAt ?? null,
    }
  }
  const spend = pickCurrency(snap.metrics, 'spend')
  const team = pickCurrency(snap.metrics, 'team_spend')
  const personal =
    snap.raw != null
      ? enrichPersonalFromRaw(snap.raw as CursorRawSnapshot, spend)
      : {
          spentUsd: spend?.spentUsd ?? null,
          limitUsd: spend?.limitUsd ?? null,
          percentUsed: spend?.percentUsed ?? null,
          remainingUsd: spend?.remainingUsd ?? null,
          personalDisplay: spend?.percentUsed != null ? ('percent' as const) : undefined,
        }

  return {
    ok: true,
    label: 'CURSOR',
    ...personal,
    cycleEnd: pickCountdown(snap.metrics),
    teamPercent: team?.percentUsed ?? null,
    updatedAt: snap.fetchedAt,
  }
}
