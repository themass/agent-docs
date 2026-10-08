import { resolveDeliverable } from './deliverable.js';
import { transitionCapability } from './capability-state.js';
import { clickAndVerify, isKnownInertCandidate } from './post-action-verify.js';
import { pickFeedClickIndex as pickFeedClickIndexFromHome } from './media-home-harvest.js';
/** @deprecated import from media-home-harvest — kept for re-export */
export function pickFeedClickIndex(snap, pageState) {
    return pickFeedClickIndexFromHome(snap, pageState);
}
function isMediaNetworkEvent(event) {
    return /\.m3u8(?:$|[?#])|\.mp4(?:$|[?#])|\.webm(?:$|[?#])|\/(?:video|segment|playlist|manifest)(?:\/|$)|mime[=:]video/i.test(event.url) || /video|mpegurl|mp4|webm/i.test(`${event.mimeType ?? ''} ${event.type ?? ''}`);
}
/**
 * Generic heuristic for a secondary "play" control after landing on a
 * detail-like page: an indexed element whose own label or an `aria-label`
 * nearby reads like a play affordance. This is deliberately pattern-based
 * (icon glyphs / common play words across zh/en UIs), never a per-site
 * selector or domain rule.
 */
function pickPlayLikeControlIndex(snap) {
    const lines = [snap.header, snap.content, snap.footer].filter(Boolean).join('\n').split(/\n+/);
    const indexed = /^\*?\[(\d+)\]\s*(.*)$/;
    const playPattern = /play|播放|▶|立即播放|aria-label="[^"]*(play|播放)[^"]*"/i;
    for (const raw of lines) {
        const match = indexed.exec(raw.trim());
        if (!match)
            continue;
        if (playPattern.test(match[2]))
            return Number(match[1]);
    }
    return undefined;
}
/**
 * Network attach is timing-sensitive right after page load — a single
 * transient failure must not be treated as permanent unavailability. Retry
 * `start()` a few times with a short backoff before giving up; each failure
 * still updates capability-state so other code paths observe the same
 * (transient, not unavailable) truth while retrying.
 */
async function prepareNetwork(ctx, network, attempts = 3) {
    const digest = await network.digest(1);
    if (digest.ok) {
        ctx.runtimeState = {
            ...ctx.runtimeState,
            capabilities: transitionCapability(ctx.runtimeState.capabilities, 'network', 'available'),
        };
        await network.clear().catch(() => undefined);
        await ctx.refreshNetwork();
        return true;
    }
    for (let attempt = 1; attempt <= attempts; attempt += 1) {
        const started = await network.start();
        if (started.ok) {
            ctx.runtimeState = {
                ...ctx.runtimeState,
                capabilities: transitionCapability(ctx.runtimeState.capabilities, 'network', 'available'),
            };
            await network.clear().catch(() => undefined);
            await ctx.refreshNetwork();
            return true;
        }
        ctx.runtimeState = {
            ...ctx.runtimeState,
            capabilities: transitionCapability(ctx.runtimeState.capabilities, 'network', 'transient_error', {
                reason: started.error.message,
                retryAt: Date.now() + 750,
                incrementAttempt: true,
            }),
        };
        if (attempt === attempts) {
            ctx.recordNote(`PREFLIGHT: network start failed after ${attempts} attempts — ${started.error.message}; candidate click path remains recoverable`);
            return false;
        }
        ctx.recordNote(`PREFLIGHT: network start failed (attempt ${attempt}/${attempts}) — ${started.error.message}; recoverable, retrying candidate attach`);
        await new Promise((resolve) => setTimeout(resolve, 150 * attempt));
    }
    return false;
}
async function waitForMediaEvent(network, timeoutMs) {
    const waited = await network.wait({
        urlRegex: '(\\.m3u8|\\.mp4|\\.webm|/video/|mime[=:]video|playlist|manifest)',
        timeoutMs,
    });
    if (waited.ok && isMediaNetworkEvent(waited.data))
        return { url: waited.data.url };
    const listed = await network.list({ limit: 80 });
    if (listed.ok) {
        const media = listed.data.find(isMediaNetworkEvent);
        if (media)
            return { url: media.url };
    }
    return undefined;
}
function recordMediaEvidenceAndFormat(ctx, url, clickIndex, pattern) {
    ctx.recordEvidence({
        kind: 'network',
        source: 'network_media',
        summary: url,
        confidence: 0.9,
        data: { url, pattern, clickIndex },
    });
    return ['媒体源地址（通用 media candidate click + network）：', url, '', `触发方式：click snapshot index ${clickIndex}`].join('\n');
}
/**
 * Generic media candidate smoke path. It deliberately does not trust a
 * non-empty structured extract: navigation/category rows are not media rows.
 * Candidate selection comes from Page State/snapshot, click effect is
 * verified generically (post-action-verify), and Network observes the
 * resulting request. If the first click lands on a detail-like page but no
 * media request appears, a second generic "play control" click is tried
 * before giving up — real players often require an explicit play action.
 */
export async function tryMediaFeedDeterministicHarvest(ctx) {
    const deliverable = ctx.gates.deliverable ?? resolveDeliverable(ctx.task);
    if (deliverable !== 'media')
        return undefined;
    const { dom, network } = ctx.agent.planes;
    if (!network || !dom.click)
        return undefined;
    const index = pickFeedClickIndex(ctx.snap, ctx.pageState);
    if (index == null) {
        ctx.recordNote('PREFLIGHT: media feed deterministic — no actionable media candidate found in Page State/snapshot');
        return undefined;
    }
    if (isKnownInertCandidate(ctx, ctx.snap.url, index)) {
        ctx.recordNote(`PREFLIGHT: media feed deterministic — candidate index=${index} already observed inert on this URL, skipping repeat click`);
        return undefined;
    }
    if (!(await prepareNetwork(ctx, network)))
        return undefined;
    ctx.recordNote(`PREFLIGHT: media feed deterministic — click media candidate index=${index} and verify effect before trusting it as progress.`);
    const clickResult = await clickAndVerify(ctx, { index, waitTimeoutMs: 4_000 });
    if (!clickResult.ok) {
        ctx.recordNote(`PREFLIGHT: media feed click unusable (${clickResult.reason}${clickResult.message ? `: ${clickResult.message}` : ''})`);
        return undefined;
    }
    if (clickResult.verification.noEffect) {
        ctx.recordNote(`PREFLIGHT: media candidate index=${index} click produced no observable change (url/dom/page-state/network all unchanged) — treated as inert, will not retry.`);
        return undefined;
    }
    // One broad wait is important: waiting serially for every extension keeps the
    // agent idle for tens of seconds and can miss a short-lived request.  The
    // plane still applies the precise URL matching; the list fallback handles
    // providers whose media MIME is more reliable than their URL suffix.
    const firstMedia = await waitForMediaEvent(network, 15_000);
    if (firstMedia) {
        return recordMediaEvidenceAndFormat(ctx, firstMedia.url, index, 'candidate_click');
    }
    // The click changed something (new page / new candidates / etc.) but no
    // media request fired yet — this commonly means we landed on a detail
    // page and still need to press an explicit play control before the
    // player issues its network request. Try once, generically.
    if (clickResult.verification.urlChanged || clickResult.verification.revisionChanged) {
        const playIndex = pickPlayLikeControlIndex(ctx.snap);
        if (playIndex != null && !isKnownInertCandidate(ctx, ctx.snap.url, playIndex)) {
            ctx.recordNote(`PREFLIGHT: media feed deterministic — detail page reached, no media request yet; trying generic play control index=${playIndex}.`);
            const playClick = await clickAndVerify(ctx, { index: playIndex, waitTimeoutMs: 4_000 });
            if (playClick.ok && !playClick.verification.noEffect) {
                const secondMedia = await waitForMediaEvent(network, 15_000);
                if (secondMedia) {
                    return recordMediaEvidenceAndFormat(ctx, secondMedia.url, playIndex, 'play_control_click');
                }
            }
        }
    }
    ctx.recordNote('PREFLIGHT: media candidate click completed but no m3u8/mp4/webm captured; continue with Planner/LLM recovery.');
    return undefined;
}
