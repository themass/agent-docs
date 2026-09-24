import type { TraceRecord } from '@naviforge/session'

/**
 * Append-only source-of-truth for a run. Records are never rewritten; model
 * context is a compact, lossy projection via `projectTraceRecords` in working-set.ts.
 */
export class RunLedger {
  private readonly entries: TraceRecord[] = []

  append(record: TraceRecord): void {
    this.entries.push(record)
  }

  all(): readonly TraceRecord[] {
    return this.entries
  }

  at(index: number): TraceRecord | undefined {
    return this.entries.at(index)
  }
}
