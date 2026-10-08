export type CapabilityStatus = 'available' | 'starting' | 'transient_error' | 'unavailable' | 'forbidden'

export type CapabilityState = {
  status: CapabilityStatus
  attempts: number
  epoch: number
  reason?: string
  retryAt?: number
}

export type CapabilityName = 'dom' | 'tabs' | 'network' | 'search' | 'fetch' | 'workspace' | 'hitl'

export type CapabilityRegistry = Record<CapabilityName, CapabilityState>

export function createCapabilityState(status: CapabilityStatus, reason?: string): CapabilityState {
  return { status, attempts: 0, epoch: 0, ...(reason ? { reason } : {}) }
}

export function createCapabilityRegistry(input: Partial<Record<CapabilityName, boolean>> = {}): CapabilityRegistry {
  const initial = (name: CapabilityName): CapabilityState =>
    createCapabilityState(input[name] === false ? 'unavailable' : 'available')
  return {
    dom: initial('dom'),
    tabs: initial('tabs'),
    network: initial('network'),
    search: initial('search'),
    fetch: initial('fetch'),
    workspace: initial('workspace'),
    hitl: initial('hitl'),
  }
}

export function transitionCapability(
  registry: CapabilityRegistry,
  name: CapabilityName,
  status: CapabilityStatus,
  input: { reason?: string; retryAt?: number; incrementAttempt?: boolean } = {}
): CapabilityRegistry {
  const current = registry[name]
  const attempts = input.incrementAttempt ? current.attempts + 1 : status === 'available' ? 0 : current.attempts
  const next: CapabilityState = {
    status,
    attempts,
    epoch: status === 'available' && current.status !== 'available' ? current.epoch + 1 : current.epoch,
    ...(input.reason ? { reason: input.reason } : {}),
    ...(input.retryAt != null ? { retryAt: input.retryAt } : {}),
  }
  return { ...registry, [name]: next }
}

export function capabilityUsable(state: CapabilityState | undefined): boolean {
  return state?.status === 'available'
}

export function capabilityRetryable(state: CapabilityState | undefined, now = Date.now()): boolean {
  return state?.status === 'starting' || (state?.status === 'transient_error' && (state.retryAt ?? 0) <= now)
}
