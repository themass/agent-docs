export function createCapabilityState(status, reason) {
    return { status, attempts: 0, epoch: 0, ...(reason ? { reason } : {}) };
}
export function createCapabilityRegistry(input = {}) {
    const initial = (name) => createCapabilityState(input[name] === false ? 'unavailable' : 'available');
    return {
        dom: initial('dom'),
        tabs: initial('tabs'),
        network: initial('network'),
        search: initial('search'),
        fetch: initial('fetch'),
        workspace: initial('workspace'),
        hitl: initial('hitl'),
    };
}
export function transitionCapability(registry, name, status, input = {}) {
    const current = registry[name];
    const attempts = input.incrementAttempt ? current.attempts + 1 : status === 'available' ? 0 : current.attempts;
    const next = {
        status,
        attempts,
        epoch: status === 'available' && current.status !== 'available' ? current.epoch + 1 : current.epoch,
        ...(input.reason ? { reason: input.reason } : {}),
        ...(input.retryAt != null ? { retryAt: input.retryAt } : {}),
    };
    return { ...registry, [name]: next };
}
export function capabilityUsable(state) {
    return state?.status === 'available';
}
export function capabilityRetryable(state, now = Date.now()) {
    return state?.status === 'starting' || (state?.status === 'transient_error' && (state.retryAt ?? 0) <= now);
}
