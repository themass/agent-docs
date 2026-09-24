/** Display-ready metric value — UI renders by `kind` without knowing the platform. */
export type MetricValue =
  | {
      kind: 'gauge'
      used: number
      limit: number | null
      unit?: string
      subtitle?: string
    }
  | {
      kind: 'currency'
      spentUsd: number
      limitUsd: number | null
      remainingUsd: number | null
      percentUsed: number | null
    }
  | { kind: 'text'; text: string; muted?: boolean }
  | { kind: 'countdown'; cycleStart: string; cycleEnd: string }
  | { kind: 'list'; items: Array<{ label: string; value: string; hint?: string }> }
  | { kind: 'badge'; text: string; tone?: 'ok' | 'warn' | 'error' | 'muted' }

export type MetricSection = 'summary' | 'billing' | 'team' | 'details'

/** Metric catalog entry — add rows here per platform; framework stays unchanged. */
export type QuotaMetricDef = {
  id: string
  title: string
  section: MetricSection
  order?: number
}

export type ProviderFetchResult = {
  ok: boolean
  fetchedAt: string
  error?: string
  raw?: unknown
}

export type ProviderSnapshot = ProviderFetchResult & {
  providerId: string
  metrics: Array<{ def: QuotaMetricDef; value: MetricValue | null }>
}

/**
 * One file per agent platform: implement this interface and call `registerQuotaProvider`.
 * Framework code (orchestrator / UI) only depends on this contract.
 */
export type QuotaProvider = {
  readonly id: string
  readonly label: string
  readonly description: string
  /** false → UI shows「即将支持」占位，不发起 fetch */
  readonly implemented: boolean
  connectionHint(): string
  fetchRaw(signal?: AbortSignal): Promise<unknown>
  metrics(): readonly QuotaMetricDef[]
  extractMetric(metricId: string, raw: unknown): MetricValue | null
}

export type GeniusFallPrefs = {
  enabledIds: string[]
}
