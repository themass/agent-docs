/** Codes that mean "settings gate" — retrying another path still wastes the run. */
export declare const HARD_DENY_ERROR_CODES: Set<string>;
export declare function privacyHintFor(code: string, locale?: string): string | undefined;
export declare function isCspEvalError(message: string): boolean;
export type RunLimitOptions = {
    /** Consecutive identical tool+error.code failures before ask_user (0 = off). */
    sameFailureLimit?: number;
    /** Max successful identical screenshot/scroll/snapshot actions per URL before blocking (0 = off). */
    sameActionLimit?: number;
    /** Wall-clock ms from run start (0 = off). */
    runTimeoutMs?: number;
    /** Cumulative LLM tokens for this run (0 = off). */
    runTokenBudget?: number;
    /** Estimated tokens in a single model input (system + user; 0 = off). */
    maxInputTokens?: number;
};
export declare const DEFAULT_RUN_LIMITS: {
    readonly maxSteps: 30;
    readonly sameFailureLimit: 2;
    readonly sameActionLimit: 2;
    readonly runTimeoutMs: number;
    readonly runTokenBudget: 200000;
    readonly maxInputTokens: 32000;
};
export declare function sameActionLoopResult(tool: string, count: number, locale?: string): string;
export declare function hardDenyQuestion(tool: string, code: string, hint?: string, locale?: string): string;
export declare function sameFailureQuestion(tool: string, code: string, count: number, locale?: string): string;
export type ListOpenHint = {
    index: number;
    title: string;
    url?: string;
};
/** Format concrete list rows so navigate/click recovery can avoid empty {} loops. */
export declare function formatListOpenConstraint(items: ListOpenHint[]): string;
export declare function listHintsFromToolData(data: unknown): ListOpenHint[];
