import { normalizeCursorSnapshot } from './providers/cursor/cursor-normalize.js'
import { extractCursorMetric } from './providers/cursor/cursor-metrics.js'
import { listQuotaProviders, getQuotaProvider } from './registry.js'
import { registerStubProvider } from './providers/stub-provider.js'

function assert(cond: unknown, msg: string): void {
  if (!cond) throw new Error(msg)
}

function run(): void {
  const raw = {
    periodUsage: {
      planUsage: {
        totalSpend: 12.4,
        limit: 50,
        totalPercentUsed: 24.8,
        autoPercentUsed: 20,
        apiPercentUsed: 4.8,
        billingCycleStart: '2026-08-01T00:00:00.000Z',
        billingCycleEnd: '2026-09-01T00:00:00.000Z',
      },
    },
    planInfo: { planInfo: { planName: 'Pro' } },
    usageEvents: {
      aggregatedUsageEvents: [
        {
          model: 'claude-4',
          inputTokens: 1000,
          outputTokens: 200,
          cost: 1.5,
        },
      ],
    },
    stripeProfile: null,
  }

  const norm = normalizeCursorSnapshot(raw)
  assert(norm.planUsage.totalSpendUsd === 12.4, 'spend')
  assert(norm.planName === 'Pro', 'plan name')
  assert(norm.modelRows.length === 1, 'model rows')

  const spend = extractCursorMetric('spend', raw)
  assert(spend?.kind === 'currency' && spend.spentUsd === 12.4, 'spend metric')

  const before = listQuotaProviders().length
  registerStubProvider({ id: '__self_check__', label: 'Test', description: 'x' })
  assert(listQuotaProviders().length === before + 1, 'register')
  assert(getQuotaProvider('__self_check__')?.id === '__self_check__', 'get')
}

run()
console.log('genius-fall.self-check: ok')
