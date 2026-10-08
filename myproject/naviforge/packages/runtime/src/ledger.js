/**
 * Append-only source-of-truth for a run. Records are never rewritten; model
 * context is a compact, lossy projection via `projectTraceRecords` in working-set.ts.
 */
export class RunLedger {
    entries = [];
    append(record) {
        this.entries.push(record);
    }
    all() {
        return this.entries;
    }
    at(index) {
        return this.entries.at(index);
    }
}
