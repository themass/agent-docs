import type { TraceRecord } from '@naviforge/session';
import { type LlmConfig } from './llm.js';
import { type ContextCompactor } from './working-set.js';
export type CreateContextCompactorOptions = {
    llm: LlmConfig;
    signal?: AbortSignal;
};
export declare function serializeRecordsForCompaction(records: readonly TraceRecord[]): string;
/** LLM semantic L2 with deterministic fallback (pi / DSH / MAF). */
export declare function createLlmContextCompactor(opts: CreateContextCompactorOptions): ContextCompactor;
/** Default compactor for production runs: LLM when configured, else deterministic only. */
export declare function createContextCompactor(opts: CreateContextCompactorOptions): ContextCompactor;
export declare function estimatePromptTokens(opts: {
    system: string;
    user: string;
    tools?: readonly import('@naviforge/shared').OpenAiFunctionTool[];
}): number;
