import type { TraceRecord } from '@naviforge/session';
/**
 * Append-only source-of-truth for a run. Records are never rewritten; model
 * context is a compact, lossy projection via `projectTraceRecords` in working-set.ts.
 */
export declare class RunLedger {
    private readonly entries;
    append(record: TraceRecord): void;
    all(): readonly TraceRecord[];
    at(index: number): TraceRecord | undefined;
}
