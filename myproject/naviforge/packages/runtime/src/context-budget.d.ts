import type { OpenAiFunctionTool } from '@naviforge/shared';
/** Prime/Pi-style proactive compaction thresholds (fraction of maxInputTokens). */
export declare const CONTEXT_BUDGET_RATIOS: {
    readonly soft: 0.65;
    readonly hard: 0.8;
    readonly stop: 0.92;
};
export declare function estimateInputTokens(opts: {
    system: string;
    user: string;
    tools?: readonly OpenAiFunctionTool[];
    toolsTokens?: number;
}): number;
export declare function inputTokenRatio(opts: {
    system: string;
    user: string;
    tools?: readonly OpenAiFunctionTool[];
    toolsTokens?: number;
    maxInputTokens: number;
}): number;
export declare function l1ProjectionCap(maxInputTokens: number, ratio: number): number;
