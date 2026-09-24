import { registerQuotaProvider } from '../registry.js'
import type { QuotaProvider } from '../types.js'

/** Placeholder platform — register only; no framework edits when adding real impl later. */
export function registerStubProvider(input: {
  id: string
  label: string
  description: string
}): QuotaProvider {
  const provider: QuotaProvider = {
    id: input.id,
    label: input.label,
    description: input.description,
    implemented: false,
    connectionHint: () => '即将支持',
    async fetchRaw() {
      return { stub: true }
    },
    metrics: () => [],
    extractMetric: () => null,
  }
  registerQuotaProvider(provider)
  return provider
}
