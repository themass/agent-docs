import { formatWebSearchTrace } from './search-plane.js';
import { formatFetchTextTrace } from './fetch-plane.js';
/**
 * Pure working-set projector. `RunLedger` is the append-only source; this module
 * never mutates the log. `WorkingSetHook` projects into `ctx.messages`; compile formats that.
 *
 * Layers:
 *   L0 ingest — cap each line when it is recorded (`RunLedger.append`)
 *   L1 select — coalesce duplicate evidence/extracts, keep pinned + recent, fold the rest
 *   L2 (optional LLM) — not here; thread memory does semantic merge across runs
 */
export const WORKING_SET = {
    /** Target size of the 近期轨迹 block. */
    traceChars: 8_000,
    /** Ordinary tool traces (clicks, extract lists, MCP). */
    observationChars: 1_200,
    /** Latest page body / PAGE EVIDENCE / EVIDENCE:. */
    evidenceChars: 3_000,
    /** USER CORRECTION: / USER ANSWER: / FOLLOW-UP: / CONSTRAINT: / GUIDANCE: / COMPACTION:. */
    pinnedChars: 2_000,
    /** Recent non-pinned traces kept in full (after coalesce). */
    recentKeep: 6,
    /** History size that triggers in-place L1 rewrite. */
    foldChars: 16_000,
};
/** Dedicated L2 fallback: deterministic, bounded, and safe to run without another model call. */
export function createDeterministicCompactor() {
    return {
        async compact(input) {
            const tools = input.records
                .filter((record) => record.type === 'tool.result')
                .slice(-6)
                .map((record) => record.payload.tool);
            return {
                summary: `Prior context contains ${input.records.length} audit records; recent tools: ${tools.join(', ') || 'none'}.`,
                preservedConstraints: input.constraints,
                openWork: input.openWork,
                tokenUsage: 0,
                mode: 'deterministic',
            };
        },
    };
}
/** Map runtime `run.note` lines into CONTEXT item kinds (see CONTEXT_PROJECTION.md). */
export function projectRunNote(text) {
    const line = text.trim();
    if (!line)
        return null;
    if (/^GUIDANCE:/i.test(line))
        return { kind: 'constraint', pinned: true };
    if (/^CONSTRAINT:/i.test(line))
        return { kind: 'constraint', pinned: true };
    if (/^EVIDENCE:/i.test(line))
        return { kind: 'observation', pinned: true };
    if (/^PAGE SIGNALS/i.test(line))
        return { kind: 'observation', pinned: true };
    if (/^PREFLIGHT:/i.test(line))
        return { kind: 'observation', pinned: false };
    if (/^(USER ANSWER:|USER CORRECTION:|FOLLOW-UP:|INTAKE )/i.test(line)) {
        return { kind: 'constraint', pinned: true };
    }
    return null;
}
/**
 * L1 is a deterministic, read-only TraceRecord projection. It never serializes
 * raw payload objects: tool arguments and arbitrary result bodies stay audit-only.
 */
export function projectTraceRecords(records, opts) {
    const ownerRunId = opts.ownerRunId;
    const scoped = ownerRunId
        ? records.filter((record) => !record.parentRunId || record.runId === ownerRunId)
        : records.filter((record) => !record.parentRunId);
    const compaction = [...scoped].reverse().find((record) => record.type === 'context.compaction');
    const covered = new Set(compaction?.type === 'context.compaction' ? compaction.payload.coveredRecordIds : []);
    const active = scoped.filter((record) => !covered.has(record.id) ||
        record.type === 'user.task' ||
        record.type === 'user.steer' ||
        record.type === 'context.compaction');
    const items = [];
    const intakeDone = active.some((record) => record.type === 'intake.complete');
    for (const record of active) {
        if (record.type === 'user.steer') {
            for (const text of record.payload.texts)
                items.push(item('constraint', text, true, record.id));
        }
        if (record.type === 'run.ask') {
            if (intakeDone && record.payload.wait === 'intake')
                continue;
            items.push(item('constraint', `Awaiting user: ${record.payload.question}`, true, record.id));
        }
        if (record.type === 'run.note') {
            const mapped = projectRunNote(record.payload.text);
            if (mapped)
                items.push(item(mapped.kind, record.payload.text, mapped.pinned, record.id));
        }
    }
    if (compaction?.type === 'context.compaction') {
        items.push(item('compaction', compaction.payload.summary, true, compaction.id));
        for (const constraint of compaction.payload.preservedConstraints) {
            items.push(item('constraint', constraint, true, compaction.id));
        }
        for (const work of compaction.payload.openWork)
            items.push(item('step', `Open work: ${work}`, true, compaction.id));
    }
    const observations = new Map();
    const errors = [];
    const steps = [];
    for (const record of active) {
        if (record.type === 'tool.result') {
            const observation = safeToolObservation(record);
            if (observation)
                observations.set(observation.key, item('observation', observation.text, false, record.id));
            steps.push(item('step', `${record.payload.tool}: ${record.payload.ok ? 'completed' : 'failed'}`, false, record.id));
        }
        else if (record.type === 'run.network') {
            observations.set('network', item('observation', `Network: ${record.payload.message}`, false, record.id));
        }
        else if (record.type === 'run.error') {
            errors.push(item('error', record.payload.message, true, record.id));
        }
        else if (record.type === 'model.turn') {
            steps.push(item('step', `Model ${record.payload.status}: ${record.payload.summary}`, false, record.id));
        }
    }
    items.push(...observations.values(), ...errors.slice(-4), ...steps.slice(-WORKING_SET.recentKeep));
    const fitted = fitContextItems(items, opts.maxInputTokens);
    const prompt = formatContextItems(fitted);
    return {
        items: fitted,
        prompt,
        estimatedTokens: estimateTokens(prompt),
        pressured: estimateTokens(formatContextItems(items)) > opts.maxInputTokens,
    };
}
export function promptWouldExceedInputLimit(opts) {
    if (opts.maxInputTokens <= 0)
        return false;
    const tools = opts.toolsTokens ?? 0;
    return estimateTokens(opts.system) + estimateTokens(opts.user) + tools >= opts.maxInputTokens;
}
/** CJK-heavy pages; ~2 chars/token is conservative. English is cheaper. */
export function estimateTokens(text) {
    return Math.ceil(text.length / 2);
}
export function estimateToolsTokens(tools) {
    if (!tools.length)
        return 0;
    return estimateTokens(JSON.stringify(tools));
}
export function promptWouldExceedBudget(opts) {
    if (opts.tokenBudget <= 0)
        return false;
    return opts.runTotalTokens + estimateTokens(opts.system) + estimateTokens(opts.user) >= opts.tokenBudget;
}
function clipLine(line, max) {
    if (line.length <= max)
        return line;
    return `${line.slice(0, max)}\n… (truncated)`;
}
function item(kind, content, pinned, sourceRecordId) {
    return { kind, content: clipLine(content.trim(), pinned ? WORKING_SET.pinnedChars : WORKING_SET.observationChars), pinned, sourceRecordIds: [sourceRecordId] };
}
function readArgString(args, key) {
    if (!args || typeof args !== 'object' || Array.isArray(args))
        return '';
    const value = args[key];
    return typeof value === 'string' ? value : '';
}
function safeToolObservation(record) {
    const { tool, ok, error, data, arguments: args } = record.payload;
    if (!ok)
        return { key: `tool:${tool}`, text: `${tool}: ${error?.message ?? 'failed'}` };
    if (tool === 'dom_read') {
        const mode = readArgString(args, 'mode') || 'body';
        const page = data && typeof data === 'object' && !Array.isArray(data) ? data : {};
        const url = typeof page.url === 'string' ? page.url : '';
        const title = typeof page.title === 'string' ? page.title : '';
        if (mode === 'body') {
            const text = typeof page.text === 'string' ? page.text : '';
            return { key: `page|${url}|body`, text: `Page${title ? ` (${title})` : ''}${url ? ` ${url}` : ''}: ${text.slice(0, WORKING_SET.evidenceChars)}` };
        }
        if (mode === 'list' || mode === 'dom') {
            const items = Array.isArray(page.items) ? page.items : [];
            const lines = items.slice(0, 12).map((entry, index) => {
                if (!entry || typeof entry !== 'object')
                    return `${index + 1}. (item)`;
                const row = entry;
                const label = typeof row.title === 'string' ? row.title : typeof row.label === 'string' ? row.label : '(item)';
                const href = typeof row.url === 'string' ? row.url : typeof row.href === 'string' ? row.href : '';
                return `${index + 1}. ${label}${href ? ` — ${href}` : ''}`;
            });
            return {
                key: `dom_read|${url}|${mode}`,
                text: `dom_read ${mode}${title ? ` (${title})` : ''}: ${items.length} items\n${lines.join('\n')}`.slice(0, WORKING_SET.evidenceChars),
            };
        }
        if (mode === 'markdown') {
            const path = typeof page.path === 'string' ? page.path : '';
            return { key: `dom_read|${url}|markdown`, text: `dom_read markdown → ${path || '(path missing)'}` };
        }
        return null;
    }
    if (tool === 'tabs_open' || tool === 'tabs_switch') {
        const url = readArgString(args, 'url');
        return { key: `tab|${url}`, text: `${tool}: ${url || '(active tab)'}` };
    }
    if (tool === 'skill_load') {
        const id = readArgString(args, 'id') || (data && typeof data === 'object' && !Array.isArray(data) && typeof data.id === 'string' ? data.id : '');
        return id ? { key: `skill:${id}`, text: `skill_load: ${id}` } : null;
    }
    if (tool === 'system_extract_page') {
        const count = data && typeof data === 'object' && !Array.isArray(data) && typeof data.count === 'number'
            ? data.count
            : Array.isArray(data?.items) ? data.items.length : 0;
        return { key: 'extract_page', text: `system_extract_page: ${count} items` };
    }
    if (tool.startsWith('network_'))
        return { key: 'network', text: `Network tool ${tool} completed.` };
    if (tool === 'dom_execute_js') {
        const rec = (data ?? {});
        const preview = JSON.stringify(rec.result ?? null).slice(0, WORKING_SET.observationChars);
        return { key: 'dom_execute_js', text: `dom_execute_js: ${preview}` };
    }
    if (tool === 'web_search') {
        const query = readArgString(args, 'query').trim();
        const trace = formatWebSearchTrace(data);
        return { key: query ? `search:${query.toLowerCase()}` : 'search', text: trace };
    }
    if (tool === 'fetch_text') {
        const url = readArgString(args, 'url').trim();
        const trace = formatFetchTextTrace(data);
        let key = 'fetch';
        if (url) {
            try {
                const parsed = new URL(url);
                key = `fetch:${parsed.origin}${parsed.pathname}`.replace(/\/$/, '');
            }
            catch {
                key = `fetch:${url.toLowerCase()}`;
            }
        }
        return { key, text: trace };
    }
    return null;
}
function fitContextItems(items, maxInputTokens) {
    if (maxInputTokens <= 0)
        return items;
    const selected = [...items];
    while (selected.length && estimateTokens(formatContextItems(selected)) > maxInputTokens) {
        const removable = selected.findIndex((entry) => !entry.pinned);
        if (removable >= 0) {
            selected.splice(removable, 1);
            continue;
        }
        const longest = selected.reduce((best, entry, index) => entry.content.length > selected[best].content.length ? index : best, 0);
        const current = selected[longest];
        if (current.content.length <= 140)
            break;
        selected[longest] = {
            ...current,
            content: current.content.slice(0, Math.max(120, Math.floor(current.content.length / 2))),
        };
    }
    return selected;
}
function formatContextItems(items) {
    if (!items.length)
        return 'CONTEXT\n(none)';
    return `CONTEXT\n${items.map((entry) => `${entry.kind.toUpperCase()}: ${entry.content}`).join('\n')}`;
}
