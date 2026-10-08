import { CONTINUE } from './hooks.js';
import { resolveDeliverable } from './deliverable.js';
import { collectMediaFeedTitles } from './media-home-harvest.js';
import { formatFeedEvidenceNote } from './page-feed-evidence.js';
import { WORKING_SET } from './working-set.js';
import { transitionCapability } from './capability-state.js';
export function deliverableRequiresNetworkPlane(deliverable) {
    return deliverable === 'media';
}
/** @deprecated use deliverableRequiresNetworkPlane — script 任务不强制 debugger。 */
export function taskNeedsNetworkPlane(deliverable) {
    return deliverableRequiresNetworkPlane(deliverable);
}
function networkFailureDetail(ctx) {
    const text = ctx.networkText.trim();
    if (text.startsWith('NETWORK: error '))
        return text.slice('NETWORK: error '.length);
    if (text.includes('digest failed'))
        return text;
    return undefined;
}
function networkDigestBroken(ctx) {
    return (ctx.networkText.includes('NETWORK: error') ||
        ctx.networkText.includes('digest failed'));
}
function markNetworkUnavailable(ctx, note) {
    ctx.runtimeState = {
        ...ctx.runtimeState,
        capabilities: transitionCapability(ctx.runtimeState.capabilities, 'network', 'unavailable', {
            reason: note,
            incrementAttempt: true,
        }),
    };
    ctx.networkText = 'NETWORK: (unavailable — DOM fallback; retry requires capability recovery)';
    ctx.syncTools();
    ctx.recordNote(note);
    ctx.recordNote('PLAN: network unavailable — 允许通用 DOM fallback；若 Task Contract 要求 network evidence，必须 recovery/ask_user，不得伪装 complete。');
}
function markNetworkTransient(ctx, note) {
    const retryAt = Date.now() + 500;
    ctx.runtimeState = {
        ...ctx.runtimeState,
        capabilities: transitionCapability(ctx.runtimeState.capabilities, 'network', 'transient_error', {
            reason: note,
            retryAt,
            incrementAttempt: true,
        }),
    };
    // Keep the Network plane and public network tool visible. Media extraction
    // is timing-sensitive and the next candidate click may make attach succeed.
    ctx.networkText = `NETWORK: (transient error — retry after ${retryAt})`;
    ctx.recordNote(note);
    ctx.recordNote('PLAN: network transient_error — 保留 Network capability，媒体 candidate click 后由 deterministic path 重试。');
}
function passiveObserveTool(tool, args) {
    if (tool === 'system_extract_page')
        return true;
    if (tool !== 'browser_observe')
        return false;
    const action = String(args.action ?? 'read');
    if (action === 'snapshot' || action === 'discover')
        return false;
    if (action === 'extract')
        return true;
    if (action === 'read') {
        const mode = String(args.mode ?? 'body');
        return mode === 'dom' || mode === 'body' || mode === 'list' || mode === '';
    }
    return false;
}
function extractResultEmpty(data) {
    if (!data || typeof data !== 'object')
        return false;
    const d = data;
    if (Array.isArray(d.items))
        return d.items.length === 0;
    if (typeof d.count === 'number')
        return d.count === 0;
    if (typeof d.text === 'string')
        return d.text.trim().length === 0;
    if (typeof d.body === 'string')
        return d.body.trim().length === 0;
    return false;
}
async function sleepMs(ms) {
    await new Promise((resolve) => setTimeout(resolve, ms));
}
async function networkDigestHealthy(ctx, network, attempts = 4) {
    for (let i = 0; i < attempts; i += 1) {
        const digest = await network.digest(1);
        if (digest.ok) {
            await ctx.refreshNetwork();
            if (!networkDigestBroken(ctx))
                return true;
        }
        if (i < attempts - 1)
            await sleepMs(80 * (i + 1));
    }
    return false;
}
/** P0: try Network health; never hard-stop the run — degrade to DOM-only media path. */
export class NetworkPlaneHealthHook {
    name = 'network-plane-health';
    // Runs in runTaskPreflight before PreflightHook writes gates.deliverable in
    // array order (see createRunHooks) — relies on resolveDeliverable(ctx.task)
    // as a direct fallback, same classifier PreflightHook itself falls back to.
    // This is the one declared `optional: true` the review in
    // docs/BEST_PRACTICES_REVIEW.md section 4 names explicitly as the concrete example of
    // a currently-safe-but-fragile early read; validateHookOrdering surfaces it as
    // a warning rather than silently relying on memory.
    reads = [{ key: 'deliverable', optional: true }];
    async runTaskPreflight(ctx) {
        const deliverable = ctx.gates.deliverable ?? resolveDeliverable(ctx.task);
        const network = ctx.agent.planes.network;
        if (ctx.networkUnavailable) {
            return undefined;
        }
        if (deliverable === 'media' && !network) {
            markNetworkUnavailable(ctx, 'Network plane 未挂载 — 以通用 DOM fallback 继续；若任务要求播放源，后续必须 recovery 或明确 shortfall。');
            return undefined;
        }
        if (!network || !deliverableRequiresNetworkPlane(deliverable))
            return undefined;
        if (await networkDigestHealthy(ctx, network))
            return undefined;
        const started = await network.start();
        if (!started.ok) {
            if (await networkDigestHealthy(ctx, network, 3))
                return undefined;
            markNetworkTransient(ctx, `Network 附加失败（${started.error.message}）— 已自动降级为 DOM 模式，Run 继续。`);
            return undefined;
        }
        if (await networkDigestHealthy(ctx, network))
            return undefined;
        const detail = networkFailureDetail(ctx);
        markNetworkTransient(ctx, `Network digest 暂时异常${detail ? `（${detail}）` : ''} — 保留 capability，等待媒体 candidate click 后重试。`);
        return undefined;
    }
    onStart(_ctx) {
        return CONTINUE;
    }
}
/** P1: inject snapshot feed + block passive observe loops on media harvest. */
export class MediaHarvestMilestoneHook {
    name = 'media-harvest-milestone';
    // mediaPassiveObserveEmpty starts undefined and this hook reads it via
    // `?? 0` in afterTool/beforeTool before writing it later in the same call —
    // safe without an earlier writer.
    reads = [{ key: 'deliverable', optional: true }, { key: 'mediaPassiveObserveEmpty', optional: true }];
    writes = ['mediaPassiveObserveEmpty'];
    async runTaskPreflight(ctx) {
        const deliverable = ctx.gates.deliverable ?? resolveDeliverable(ctx.task);
        if (deliverable !== 'media' && deliverable !== 'data')
            return undefined;
        const labels = collectMediaFeedTitles(ctx.snap, 16);
        if (labels.length < 3)
            return undefined;
        const note = formatFeedEvidenceNote(labels);
        ctx.recordNote(note.slice(0, WORKING_SET.evidenceChars + 40));
        const networkHint = ctx.networkUnavailable ? '（Network 已降级）' : '';
        ctx.recordNote(`PLAN: media — snapshot 已有列表文案。下一步：browser_act click 进详情${networkHint ? '' : ' → network read mode=media|hls'}；禁止重复 browser_observe extract。${networkHint}`);
        return undefined;
    }
    afterTool(ctx) {
        const deliverable = ctx.gates.deliverable ?? resolveDeliverable(ctx.task);
        if (deliverable !== 'media' && deliverable !== 'data')
            return;
        const tool = ctx.toolCall?.tool;
        const result = ctx.toolResult;
        if (!tool || !result?.ok)
            return;
        if (!passiveObserveTool(tool, ctx.toolCall?.arguments ?? {}))
            return;
        if (!extractResultEmpty(result.data)) {
            ctx.gates.mediaPassiveObserveEmpty = 0;
            return;
        }
        ctx.gates.mediaPassiveObserveEmpty = (ctx.gates.mediaPassiveObserveEmpty ?? 0) + 1;
        if (ctx.gates.mediaPassiveObserveEmpty >= 2) {
            ctx.recordNote('CONSTRAINT: structured extract/read 已空转 2 次 — 禁止再 browser_observe extract/read/dom。改用 browser_act click 列表项，或 network action=read mode=media|hls，或 system_done 附 shortfall。');
        }
    }
    beforeTool(ctx) {
        const deliverable = ctx.gates.deliverable ?? resolveDeliverable(ctx.task);
        if (deliverable !== 'media' && deliverable !== 'data')
            return CONTINUE;
        const empty = ctx.gates.mediaPassiveObserveEmpty ?? 0;
        if (empty < 2)
            return CONTINUE;
        const call = ctx.toolCall;
        if (!call)
            return CONTINUE;
        if (!passiveObserveTool(call.tool, call.arguments ?? {}))
            return CONTINUE;
        return {
            kind: 'skip_tool',
            note: 'CONSTRAINT: 已禁止重复 extract/read。请 browser_act click 一条 feed，或 system_done 附 shortfall（含标题列表）。',
            log: 'media milestone blocks passive observe',
            result: {
                ok: true,
                data: { skipped: true, reason: 'media_milestone_passive_observe', emptyStreak: empty },
            },
        };
    }
}
const NETWORK_BUILTIN_TOOLS = new Set([
    'network',
    'network_digest',
    'network_list',
    'network_get_body',
    'network_media_hints',
    'network_resolve_hls',
    'network_wait',
    'network_intercept',
    'network_clear_intercepts',
]);
/** Block network tool calls after degrade — avoids list_failed HITL loops. */
export class NetworkDegradedToolGateHook {
    name = 'network-degraded-tool-gate';
    beforeTool(ctx) {
        if (!ctx.networkUnavailable)
            return CONTINUE;
        const tool = ctx.toolCall?.tool;
        if (!tool || !NETWORK_BUILTIN_TOOLS.has(tool))
            return CONTINUE;
        return {
            kind: 'skip_tool',
            note: 'CONSTRAINT: Network 已降级 — 禁止 network 工具。请用 PAGE FEED / browser_act / system_done（标题 + shortfall）。',
            log: 'network degraded blocks network tool',
            result: {
                ok: true,
                data: {
                    skipped: true,
                    reason: 'network_degraded',
                    hint: 'Network plane unavailable for this run; use DOM feed titles and shortfall in system_done.',
                },
            },
        };
    }
}
