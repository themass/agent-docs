import { getQuotaProvider } from './registry.js'
import type { ProviderFetchResult, ProviderSnapshot, QuotaProvider } from './types.js'

export async function refreshProvider(
  provider: QuotaProvider,
  signal?: AbortSignal
): Promise<ProviderSnapshot> {
  const fetchedAt = new Date().toISOString()
  if (!provider.implemented) {
    return {
      providerId: provider.id,
      ok: false,
      fetchedAt,
      error: '即将支持',
      metrics: provider.metrics().map((def) => ({ def, value: null })),
    }
  }
  let result: ProviderFetchResult
  try {
    const raw = await provider.fetchRaw(signal)
    result = { ok: true, fetchedAt, raw }
  } catch (error) {
    result = {
      ok: false,
      fetchedAt,
      error: error instanceof Error ? error.message : String(error),
    }
  }
  const metrics = provider.metrics().map((def) => ({
    def,
    value: result.ok && result.raw != null ? provider.extractMetric(def.id, result.raw) : null,
  }))
  return { providerId: provider.id, ...result, metrics }
}

export async function refreshProviderById(
  providerId: string,
  signal?: AbortSignal
): Promise<ProviderSnapshot | null> {
  const provider = getQuotaProvider(providerId)
  if (!provider) return null
  return refreshProvider(provider, signal)
}

export async function refreshEnabled(
  enabledIds: readonly string[],
  signal?: AbortSignal
): Promise<ProviderSnapshot[]> {
  const out: ProviderSnapshot[] = []
  for (const id of enabledIds) {
    const provider = getQuotaProvider(id)
    if (!provider) continue
    out.push(await refreshProvider(provider, signal))
  }
  return out
}
