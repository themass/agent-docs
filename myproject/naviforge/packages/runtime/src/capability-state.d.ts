export type CapabilityStatus = 'available' | 'starting' | 'transient_error' | 'unavailable' | 'forbidden';
export type CapabilityState = {
    status: CapabilityStatus;
    attempts: number;
    epoch: number;
    reason?: string;
    retryAt?: number;
};
export type CapabilityName = 'dom' | 'tabs' | 'network' | 'search' | 'fetch' | 'workspace' | 'hitl';
export type CapabilityRegistry = Record<CapabilityName, CapabilityState>;
export declare function createCapabilityState(status: CapabilityStatus, reason?: string): CapabilityState;
export declare function createCapabilityRegistry(input?: Partial<Record<CapabilityName, boolean>>): CapabilityRegistry;
export declare function transitionCapability(registry: CapabilityRegistry, name: CapabilityName, status: CapabilityStatus, input?: {
    reason?: string;
    retryAt?: number;
    incrementAttempt?: boolean;
}): CapabilityRegistry;
export declare function capabilityUsable(state: CapabilityState | undefined): boolean;
export declare function capabilityRetryable(state: CapabilityState | undefined, now?: number): boolean;
