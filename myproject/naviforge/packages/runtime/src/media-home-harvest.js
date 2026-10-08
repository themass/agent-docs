import { resolveDeliverable } from './deliverable.js';
import { collectMediaFeedTitlesFromParts, isLikelyVideoEntryTitle, isTopicBucketSnapshotTitle, } from '@naviforge/extract';
import { extractFeedLabelsFromSnapshot } from './page-feed-evidence.js';
import { attachPageState } from './pi-run-loop.js';
import { looksLikeHomeUrl } from './page-state.js';
import { tryMediaFeedDeterministicHarvest } from './media-feed-deterministic.js';
import { parseIndexedSnapshotLines } from './snapshot-index-lines.js';
export { isLikelyVideoEntryTitle, isTopicBucketSnapshotTitle } from '@naviforge/extract';
function stripSnapshotMarkup(title) {
    return title
        .replace(/<[^>]*>/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}
/** Section tab that opens a video list (generic UI copy, not a site id). */
export function isVideoSectionNavTitle(title) {
    const t = stripSnapshotMarkup(title);
    return /^(在线电影|短视频|视频列表|视频区|国产精品|美女主播)/.test(t);
}
function looksLikeDetailMediaUrl(url) {
    if (!url)
        return false;
    try {
        const path = new URL(url).pathname;
        return /\/(video|play|watch|v\/|detail|movie|av)/i.test(path);
    }
    catch {
        return /\/(video|play|watch|v\/|detail)/i.test(url);
    }
}
export function pickFeedClickIndex(snap, pageState) {
    return pickHomeExploreClickIndex(snap, pageState);
}
/**
 * Accessibility snapshots often put a card's title on following lines instead
 * of attaching it to the indexed image node.  The old picker therefore saw
 * only the category chips and clicked “在线电影” (a navigation bucket) rather
 * than a real video card.  Recover the image index when the following block
 * contains a duration and a video-like title.
 */
function pickIndexedMediaCardIndex(snap) {
    const lines = [snap.header, snap.content, snap.footer]
        .filter(Boolean)
        .join('\n')
        .split('\n');
    const indexed = /^\*?\[(\d+)\]\s*(.*)$/;
    for (let i = 0; i < lines.length; i += 1) {
        const match = indexed.exec(lines[i]?.trim() ?? '');
        if (!match)
            continue;
        const index = Number(match[1]);
        const label = match[2].trim();
        if (!/^<(?:img|a)\b/i.test(label))
            continue;
        const following = [];
        for (let j = i + 1; j < lines.length; j += 1) {
            if (indexed.test(lines[j]?.trim() ?? ''))
                break;
            following.push(lines[j]?.trim() ?? '');
        }
        const block = following.filter(Boolean).join(' ');
        if (/\b\d{1,2}:\d{2}(?::\d{2})?\b/.test(block)) {
            const title = following.find((line) => isLikelyVideoEntryTitle(line));
            if (title)
                return index;
        }
    }
    return undefined;
}
/** Prefer a video card index; else a video section tab; else first non-nav index. */
export function pickHomeExploreClickIndex(snap, pageState) {
    if (pageState?.role === 'login' || pageState?.blocked)
        return undefined;
    // PAGE STATE may have recovered a card from structured extraction even when
    // the current accessibility snapshot contains only the card container.  Do
    // not let a short category label such as “在线电影” win over that candidate.
    const pageStateCard = pageState?.items.find((item) => item.clickIndex != null &&
        (looksLikeDetailMediaUrl(item.url) || isLikelyVideoEntryTitle(item.title)));
    if (pageStateCard?.clickIndex != null)
        return pageStateCard.clickIndex;
    const mediaCard = pickIndexedMediaCardIndex(snap);
    if (mediaCard != null)
        return mediaCard;
    const lines = parseIndexedSnapshotLines(snap, 64);
    for (const row of lines) {
        if (isLikelyVideoEntryTitle(row.title))
            return row.index;
    }
    for (const row of lines) {
        if (isVideoSectionNavTitle(row.title))
            return row.index;
    }
    for (const row of lines) {
        if (!isTopicBucketSnapshotTitle(row.title))
            return row.index;
    }
    return undefined;
}
function pushVideoTitle(out, seen, raw, limit) {
    if (out.length >= limit)
        return;
    if (!isLikelyVideoEntryTitle(raw))
        return;
    const title = stripSnapshotMarkup(raw);
    const key = title.slice(0, 48);
    if (seen.has(key))
        return;
    seen.add(key);
    out.push(title);
}
export function collectMediaFeedTitles(snap, limit = 24) {
    const fromExtract = collectMediaFeedTitlesFromParts({ header: snap.header, content: snap.content, footer: snap.footer }, limit);
    if (fromExtract.length >= 1)
        return fromExtract;
    const fromLabels = extractFeedLabelsFromSnapshot(snap, limit * 2);
    const out = [];
    const seen = new Set();
    for (const label of fromLabels) {
        if (/^(Current Page|Interactive elements|Start of page|End of page)/i.test(label))
            continue;
        pushVideoTitle(out, seen, label, limit);
    }
    return out;
}
/** VIDEO rows already merged into PAGE STATE (feed_clicks / click_index). */
export function mediaRowsFromPageState(page, limit = 24) {
    if (!page || page.blocked || page.role === 'login')
        return [];
    const rows = [];
    const seen = new Set();
    for (const item of page.items) {
        const raw = item.title?.trim() ?? '';
        const title = stripSnapshotMarkup(raw);
        if (title.length < 4)
            continue;
        if (/^\[?\d+\]?\s*<(?:div|span|a)\b/i.test(raw) && isTopicBucketSnapshotTitle(title))
            continue;
        if (isTopicBucketSnapshotTitle(title) && item.clickIndex == null)
            continue;
        if (isVideoSectionNavTitle(title) && item.clickIndex == null)
            continue;
        const feedCard = item.clickIndex != null;
        if (!feedCard && !isLikelyVideoEntryTitle(title))
            continue;
        if (!feedCard && item.url && !looksLikeDetailMediaUrl(item.url))
            continue;
        const key = title.slice(0, 48);
        if (seen.has(key))
            continue;
        seen.add(key);
        rows.push({
            title,
            pageUrl: item.url,
            clickIndex: item.clickIndex,
        });
        if (rows.length >= limit)
            break;
    }
    return rows;
}
export function formatMediaHomeHarvestResult(input) {
    const lines = ['视频名称与源地址：', ''];
    input.rows.forEach((row, i) => {
        const parts = [`${i + 1}. ${row.title}`];
        if (row.streamUrl)
            parts.push(`   播放源: ${row.streamUrl}`);
        else if (row.pageUrl)
            parts.push(`   页面: ${row.pageUrl}`);
        else if (row.clickIndex != null) {
            parts.push(`   打开: click index=${row.clickIndex}（Network 可用时可进详情捕 m3u8/mp4）`);
        }
        lines.push(parts.join('\n'));
    });
    if (input.shortfall) {
        lines.push('', `shortfall: ${input.shortfall}`);
    }
    return lines.join('\n');
}
function parseStreamUrlFromHarvest(text) {
    const match = text.match(/https?:\/\/[^\s]+/i);
    return match?.[0];
}
async function refreshSnapshot(ctx) {
    const snap = await ctx.agent.planes.dom.snapshot();
    if (!snap.ok)
        return false;
    ctx.snap = snap.data;
    await attachPageState(ctx);
    return true;
}
async function tryExtractMediaRows(ctx, n = 16) {
    const dom = ctx.agent.planes.dom;
    if (!dom.extractContent)
        return [];
    const extracted = await dom.extractContent(n);
    if (!extracted.ok || extracted.data.items.length === 0)
        return [];
    const rows = [];
    for (const item of extracted.data.items) {
        const title = item.title?.trim();
        if (!title)
            continue;
        if (isLikelyVideoEntryTitle(title) || looksLikeDetailMediaUrl(item.url)) {
            rows.push({ title, pageUrl: item.url, clickIndex: item.index });
        }
        if (rows.length >= n)
            break;
    }
    return rows;
}
function rowsFromSnapshot(snap, limit = 12) {
    return collectMediaFeedTitles(snap, limit).map((title) => ({ title }));
}
async function scrollHomeFeedIntoView(ctx) {
    const dom = ctx.agent.planes.dom;
    if (!dom.scroll)
        return;
    ctx.recordNote('PREFLIGHT: media-home 滚动首页以露出视频列表（通用）。');
    for (let i = 0; i < 3; i += 1) {
        await dom.scroll({ direction: 'down', amount: 1_100 }).catch(() => undefined);
        await dom.wait?.({ kind: 'network_idle', timeoutMs: 2_000 }).catch(() => undefined);
    }
    await refreshSnapshot(ctx);
}
async function clickHomeFeedExplore(ctx) {
    const dom = ctx.agent.planes.dom;
    const index = pickHomeExploreClickIndex(ctx.snap, ctx.pageState);
    if (index == null || !dom.click) {
        ctx.recordNote('PREFLIGHT: media-home 探测 — 未找到可点的视频区/卡片 index');
        return;
    }
    ctx.recordNote(`PREFLIGHT: media-home 探测 — click index=${index} 后重新 extract/network`);
    const clicked = await dom.click(index, ctx.snap.revision);
    if (!clicked.ok) {
        ctx.recordNote(`PREFLIGHT: media-home feed click failed — ${clicked.error.message}`);
        return;
    }
    await dom.wait?.({ kind: 'network_idle', timeoutMs: 6_000 }).catch(() => undefined);
    await refreshSnapshot(ctx);
}
async function probeHomeFeedSurface(ctx, opts) {
    ctx.recordNote('PREFLIGHT: media-home 探测 — 首页 structured 为空，尝试进入视频区（通用）。');
    if (!opts?.skipScroll)
        await scrollHomeFeedIntoView(ctx);
    await clickHomeFeedExplore(ctx);
}
function recordMediaRowsEvidence(ctx, rows) {
    for (const row of rows) {
        const title = row.title.trim();
        if (!title)
            continue;
        ctx.recordEvidence({
            kind: 'dom',
            source: 'media_title',
            summary: title,
            confidence: row.clickIndex != null ? 0.9 : 0.75,
            data: { title, clickIndex: row.clickIndex, pageUrl: row.pageUrl },
        });
    }
}
function finishMediaHarvest(ctx, rows, streamUrl) {
    recordMediaRowsEvidence(ctx, rows);
    if (streamUrl && rows[0])
        rows[0] = { ...rows[0], streamUrl };
    const shortfall = streamUrl == null
        ? ctx.networkUnavailable
            ? rows.some((r) => r.clickIndex != null)
                ? 'Network 不可用，未能捕获 m3u8/mp4；上列为视频名称与 click index（非直链播放 URL）。'
                : 'Network 不可用，未能捕获 m3u8/mp4；上列为可见视频条目与页面链接（如有）。'
            : rows.some((r) => r.pageUrl)
                ? '未能捕获 m3u8/mp4；上列为详情页链接，播放源需进入详情并开启 Network。'
                : rows.some((r) => r.clickIndex != null)
                    ? '未能捕获 m3u8/mp4；上列为 click index，需进详情页并开启 Network 捕播放源。'
                    : '未能捕获 m3u8/mp4 与详情链接。'
        : undefined;
    ctx.recordNote(streamUrl
        ? `PREFLIGHT: media-home 确定性交卷 — ${rows.length} 条 + 播放源`
        : `PREFLIGHT: media-home 确定性交卷 — ${rows.length} 条（shortfall 播放源）`);
    return formatMediaHomeHarvestResult({ rows, shortfall });
}
/**
 * Generic media-home preflight: scroll / section click / extract / network.
 * Never finishes with homepage channel chips only.
 */
export async function tryMediaHomePreflightDone(ctx) {
    const deliverable = ctx.gates.deliverable ?? resolveDeliverable(ctx.task);
    if (deliverable !== 'media')
        return undefined;
    const onHome = looksLikeHomeUrl(ctx.snap.url);
    let rows = mediaRowsFromPageState(ctx.pageState, 24);
    let streamUrl;
    const sourceRequired = ctx.taskContract.capabilities.network === 'required';
    if (rows.length >= 1) {
        ctx.recordNote(`PREFLIGHT: media-home — PAGE STATE ${rows.length} 条视频候选（candidate state）`);
        if (ctx.agent.planes.network) {
            const harvested = await tryMediaFeedDeterministicHarvest(ctx).catch(() => undefined);
            if (harvested)
                streamUrl = parseStreamUrlFromHarvest(harvested);
        }
        // A source/link request is strict: visible titles are useful evidence, but
        // they must not short-circuit the candidate-click + Network path.
        if (streamUrl || !sourceRequired)
            return finishMediaHarvest(ctx, rows, streamUrl);
        ctx.recordNote('PREFLIGHT: media source evidence required but not captured; force a concrete media candidate click before handing off to the model.');
    }
    rows = await tryExtractMediaRows(ctx, 24);
    if (rows.length < 1 && onHome) {
        await scrollHomeFeedIntoView(ctx);
        rows = rowsFromSnapshot(ctx.snap, 12);
        if (rows.length < 1)
            rows = mediaRowsFromPageState(ctx.pageState, 24);
        if (rows.length < 1)
            rows = await tryExtractMediaRows(ctx, 24);
    }
    if (ctx.agent.planes.network && !streamUrl) {
        const harvested = await tryMediaFeedDeterministicHarvest(ctx).catch(() => undefined);
        if (harvested)
            streamUrl = parseStreamUrlFromHarvest(harvested);
    }
    // For strict source/link tasks, rows already present on the home page are
    // not completion. The old `rows.length < 1` guard skipped the actual card
    // click precisely when PAGE STATE had successfully found the videos.
    if (!streamUrl && sourceRequired && onHome) {
        await probeHomeFeedSurface(ctx, { skipScroll: true });
        rows = await tryExtractMediaRows(ctx, 24);
        if (rows.length < 1) {
            const snapRows = rowsFromSnapshot(ctx.snap, 12);
            if (snapRows.length >= 1)
                rows = snapRows;
        }
        if (!streamUrl && ctx.agent.planes.network) {
            const harvested = await tryMediaFeedDeterministicHarvest(ctx).catch(() => undefined);
            if (harvested)
                streamUrl = parseStreamUrlFromHarvest(harvested);
        }
    }
    if (rows.length >= 1 && (streamUrl || !sourceRequired)) {
        return finishMediaHarvest(ctx, rows, streamUrl);
    }
    if (streamUrl) {
        ctx.recordNote('PREFLIGHT: media-home 确定性交卷 — 仅捕获播放源');
        return formatMediaHomeHarvestResult({
            rows: [{ title: '（Network 捕获）', streamUrl }],
        });
    }
    if (onHome) {
        ctx.recordNote('PREFLIGHT: media-home 未交卷 — 首页已 scroll/click 仍无视频 structured 证据；交给 LLM 或请用户滚到列表后再跑。');
    }
    return undefined;
}
