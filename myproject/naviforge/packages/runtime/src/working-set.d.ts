import type { TraceRecord } from '@naviforge/session';
import type { OpenAiFunctionTool } from '@naviforge/shared';
/**
 * Pure working-set projector. `RunLedger` is the append-only source; this module
 * never mutates the log. `WorkingSetHook` projects into `ctx.messages`; compile formats that.
 *
 * Layers:
 *   L0 ingest — cap each line when it is recorded (`RunLedger.append`)
 *   L1 select — coalesce duplicate evidence/extracts, keep pinned + recent, fold the rest
 *   L2 (optional LLM) — not here; thread memory does semantic merge across runs
 */
export declare const WORKING_SET: {
    /** Target size of the 近期轨迹 block. */
    readonly traceChars: 8000;
    /** Ordinary tool traces (clicks, extract lists, MCP). */
    readonly observationChars: 1200;
    /** Latest page body / PAGE EVIDENCE / EVIDENCE:. */
    readonly evidenceChars: 3000;
    /** USER CORRECTION: / USER ANSWER: / FOLLOW-UP: / CONSTRAINT: / GUIDANCE: / COMPACTION:. */
    readonly pinnedChars: 2000;
    /** Recent non-pinned traces kept in full (after coalesce). */
    readonly recentKeep: 6;
    /** History size that triggers in-place L1 rewrite. */
    readonly foldChars: 16000;
};
export type ContextItem = {
    kind: 'task' | 'constraint' | 'observation' | 'error' | 'step' | 'compaction';
    content: string;
    pinned: boolean;
    sourceRecordIds: string[];
};
export type TraceProjection = {
    items: ContextItem[];
    prompt: string;
    estimatedTokens: number;
    pressured: boolean;
};
export type ContextCompactionInput = {
    records: readonly TraceRecord[];
    constraints: string[];
    openWork: string[];
};
export type ContextCompactionResult = {
    summary: string;
    preservedConstraints: string[];
    openWork: string[];
    tokenUsage: number;
    /** How the summary was produced (audit marker in session JSONL). */
    mode?: 'deterministic' | 'llm';
};
export type ContextCompactor = {
    compact: (input: ContextCompactionInput) => Promise<ContextCompactionResult>;
};
/** Dedicated L2 fallback: deterministic, bounded, and safe to run without another model call. */
export declare function createDeterministicCompactor(): ContextCompactor;
/** Map runtime `run.note` lines into CONTEXT item kinds (see CONTEXT_PROJECTION.md). */
export declare function projectRunNote(text: string): {
    kind: ContextItem['kind'];
    pinned: boolean;
} | null;
/**
 * L1 is a deterministic, read-only TraceRecord projection. It never serializes
 * raw payload objects: tool arguments and arbitrary result bodies stay audit-only.
 */
export declare function projectTraceRecords(records: readonly TraceRecord[], opts: {
    maxInputTokens: number;
    ownerRunId?: string;
}): TraceProjection;
export declare function promptWouldExceedInputLimit(opts: {
    system: string;
    user: string;
    maxInputTokens: number;
    toolsTokens?: number;
}): boolean;
/** CJK-heavy pages; ~2 chars/token is conservative. English is cheaper. */
export declare function estimateTokens(text: string): number;
export declare function estimateToolsTokens(tools: readonly OpenAiFunctionTool[]): number;
export declare function promptWouldExceedBudget(opts: {
    system: string;
    user: string;
    runTotalTokens: number;
    tokenBudget: number;
}): boolean;
