import type { ToolResult } from '@naviforge/shared';
/** What the loop/UI should do after a failure. Not a second taxonomy beside LoopCommand. */
export type RecoveryStrategy = 'reobserve_and_replan' | 'retry_request' | 'ask_user' | 'stop' | 'protocol_retry' | 'protocol_error' | 'fold_context';
export type RecoveryPlan = {
    strategy: RecoveryStrategy;
    retryable: boolean;
    diagnostic: string;
};
export declare function classifyFailure(error: Extract<ToolResult, {
    ok: false;
}>['error']): RecoveryPlan;
export declare function isTransientRequestError(error: unknown): boolean;
export declare function isAbortError(error: unknown): boolean;
export declare function retry<T>(operation: () => Promise<T>, options: {
    attempts: number;
    delayMs: number;
    signal?: AbortSignal;
    onRetry?: (attempt: number, error: unknown) => void;
}): Promise<T>;
