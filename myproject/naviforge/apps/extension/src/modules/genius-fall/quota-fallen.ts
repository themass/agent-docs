import type { GeniusFallHudState } from './hud-types.js'

type QuotaFields = Pick<
  GeniusFallHudState,
  'percentUsed' | 'remainingUsd' | 'spentUsd' | 'limitUsd'
>

/** Personal quota exhausted. */
export function isPersonalQuotaFallen(fields: QuotaFields): boolean {
  if (fields.percentUsed != null && fields.percentUsed >= 100) return true
  if (fields.remainingUsd != null && fields.remainingUsd <= 0 && (fields.limitUsd ?? 0) > 0) return true
  if (
    fields.spentUsd != null &&
    fields.limitUsd != null &&
    fields.limitUsd > 0 &&
    fields.spentUsd >= fields.limitUsd
  ) {
    return true
  }
  return false
}

export function isQuotaFallen(state: GeniusFallHudState): boolean {
  if (state.loading || !state.ok) return false
  return isPersonalQuotaFallen(state)
}
