# Context compression

NaviForge keeps a three-level context strategy:

1. **L0 — audit ledger:** `TraceRecord` is append-only. Records are never edited or deleted, including compaction records.
2. **L1 — deterministic working set:** the runtime projects audit records into typed context items. It keeps the active task, user constraints and pending questions, the latest page/network observations, unresolved errors, and recent steps. Repeated observations coalesce to the newest item. Tool arguments and arbitrary raw result payloads remain audit-only.
3. **L2 — pinned compaction:** only input-limit pressure or repeated L1 pressure invokes the dedicated compactor once. Its `context.compaction` record states the covered audit range, summary, preserved constraints, open work, and token use. Later L1 projections treat it as a pinned source; they do not rewrite history.

## Two limits (do not conflate)

| Setting | Default | What it does |
|--------|---------|----------------|
| **`maxInputTokens`** | 32k | Estimated **single prompt** size (system + user). **L1 fit + L2 compaction trigger.** Shown as the main bar in Context Meter. |
| **`runTokenBudget`** | 200k | **Cumulative API usage** across all turns in one Run (prompt + completion tokens summed). Stops the run when exceeded. **Does not trigger compaction.** |

Estimation uses ~2 characters per token (conservative for CJK-heavy DOM text).

## Cursor / DSH comparison

Cursor and DSH UIs often show **“context ~200k”** — that number is the **model context window** (how much history fits in one request), not cumulative spend.

- When their meter approaches the window, they **summarize / compact** conversation history so the next request still fits.
- NaviForge’s equivalent knob is **`maxInputTokens`** (Settings → Models → Agent runtime → **单次上下文上限**).
- Our default **32k** is intentionally conservative: browser-agent prompts include DOM snapshots, tool traces, and network excerpts — much heavier than a typical chat thread.
- To behave closer to Cursor/DSH on a 200k model, raise **`maxInputTokens`** to ~200000 (compaction will fire much later). Keep **`runTokenBudget`** as a separate cost guard.

If L2 fails, the runtime retries with the minimal deterministic L1 projection. If that still cannot fit the input cap, it stops before the model request and leaves the audit ledger intact. Cross-run `ThreadMemorySlots` are stored separately from this per-run projection.

Telemetry: `metrics.context` records (from `WorkingSetHook`) expose block breakdown for the side-panel Context Meter; they are not sent to the model.
