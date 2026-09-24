import type { QuotaProvider } from './types.js'

const providers = new Map<string, QuotaProvider>()

/** Register a platform — called from each provider's index (not from framework). */
export function registerQuotaProvider(provider: QuotaProvider): void {
  providers.set(provider.id, provider)
}

export function listQuotaProviders(): QuotaProvider[] {
  return [...providers.values()].sort((a, b) => a.label.localeCompare(b.label))
}

export function getQuotaProvider(id: string): QuotaProvider | undefined {
  return providers.get(id)
}
