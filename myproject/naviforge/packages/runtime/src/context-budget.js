import { estimateTokens, estimateToolsTokens } from './working-set.js';
/** Prime/Pi-style proactive compaction thresholds (fraction of maxInputTokens). */
export const CONTEXT_BUDGET_RATIOS = {
    soft: 0.65,
    hard: 0.8,
    stop: 0.92,
};
export function estimateInputTokens(opts) {
    const tools = opts.toolsTokens ?? (opts.tools ? estimateToolsTokens(opts.tools) : 0);
    return estimateTokens(opts.system) + estimateTokens(opts.user) + tools;
}
export function inputTokenRatio(opts) {
    if (opts.maxInputTokens <= 0)
        return 0;
    return Math.min(1, estimateInputTokens(opts) / opts.maxInputTokens);
}
export function l1ProjectionCap(maxInputTokens, ratio) {
    if (ratio >= CONTEXT_BUDGET_RATIOS.hard) {
        return Math.max(2_000, Math.floor(maxInputTokens * 0.35));
    }
    if (ratio >= CONTEXT_BUDGET_RATIOS.soft) {
        return Math.max(3_000, Math.floor(maxInputTokens * 0.5));
    }
    return maxInputTokens;
}
