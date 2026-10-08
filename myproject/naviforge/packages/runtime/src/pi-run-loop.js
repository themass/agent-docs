import { discoverCatalogPage } from './catalog-crawl/discover.js';
import { snapshotWithRetry } from './exec-turn.js';
import { classifyPageState, enrichItemsWithSnapshotFeed, formatPageState, looksLikeLoginUrl, } from './page-state.js';
const NAV_TOOLS = new Set(['dom_navigate', 'tabs_open', 'tabs_switch', 'dom_click']);
/** Trace marker: this run is driven by the Pi-shaped loop, not the old inline loop. */
export const PI_LOOP_NOTE = 'LOOP: pi runLoop (prepareNextTurn → steer → one tool)';
/**
 * Build PAGE STATE from current snap + friction; inject into ctx and trace.
 * Idempotent for a given (url, snapshot revision): several call sites invoke
 * this defensively (run start, PreflightHook, after a click) and when
 * nothing has changed the page since the last call there is nothing new to
 * compute — recomputing anyway just re-emits an identical PAGE STATE note,
 * doubling prompt tokens and ledger noise for no new information.
 */
export async function attachPageState(ctx) {
    const cacheKey = { url: ctx.snap.url, revision: ctx.snap.revision };
    const cached = ctx.gates.lastPageStateFor;
    if (ctx.pageState && cached && cached.url === cacheKey.url && cached.revision === cacheKey.revision) {
        return;
    }
    const dom = ctx.agent.planes.dom;
    const friction = ctx.gates.lastPageFriction;
    const frictionHere = friction && friction.url === ctx.snap.url ? friction.report : undefined;
    const login = Boolean(frictionHere?.kinds.includes('login')) || looksLikeLoginUrl(ctx.snap.url);
    const blocking = Boolean(frictionHere?.blocking) || looksLikeLoginUrl(ctx.snap.url);
    let items = [];
    if (!login && !blocking && dom.extractContent) {
        const listed = await dom.extractContent(8).catch(() => undefined);
        if (listed?.ok) {
            items = listed.data.items
                .filter((item) => item.title?.trim())
                .slice(0, 8)
                .map((item) => ({ title: item.title.trim(), url: item.url }));
        }
    }
    if (!login && !blocking && items.length < 3 && dom.executeJs) {
        const discover = await discoverCatalogPage(dom).catch(() => null);
        if (discover?.listSample?.length) {
            items = discover.listSample
                .filter((row) => row.title?.trim() && row.url)
                .slice(0, 8)
                .map((row) => ({ title: row.title.trim(), url: row.url }));
        }
        else if (discover?.sections?.length) {
            items = discover.sections
                .slice(0, 8)
                .map((section) => ({ title: section.name, url: section.url }));
        }
    }
    if (!login && !blocking) {
        items = enrichItemsWithSnapshotFeed(items, ctx.snap);
    }
    const state = classifyPageState({
        url: ctx.snap.url,
        title: ctx.snap.title,
        login,
        blocking,
        items,
    });
    ctx.pageState = state;
    ctx.gates.lastPageStateFor = cacheKey;
    ctx.syncRuntimePageState();
    ctx.pageStateText = formatPageState(state);
    ctx.recordNote(ctx.pageStateText);
    ctx.emit(ctx.createRecord('run.note', {
        topic: 'page_state',
        text: ctx.pageStateText.slice(0, 1_600),
    }));
}
/**
 * Pi `prepareNextTurn`: after navigation, wait until the page is stable,
 * refresh the snapshot, then inject PAGE STATE for the next model turn.
 */
export async function prepareNextTurn(ctx) {
    const tool = ctx.toolCall?.tool;
    const dom = ctx.agent.planes.dom;
    if (tool && NAV_TOOLS.has(tool) && dom.wait) {
        await dom.wait({ kind: 'stable', timeoutMs: 2500 }).catch(() => undefined);
        const snap = await snapshotWithRetry(dom);
        if (snap.ok)
            ctx.snap = snap.data;
    }
    await attachPageState(ctx);
}
