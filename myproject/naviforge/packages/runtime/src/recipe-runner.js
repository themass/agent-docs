import { hydratePageSignals, tryMediaPlaybackDeterministicResult, } from './page-signals-hydrate.js';
function findClickIndex(snap, textIncludes) {
    for (const line of snap.content.split('\n')) {
        if (!textIncludes || !line.includes(textIncludes))
            continue;
        const match = /^\[(\d+)\]/.exec(line.trim());
        if (match)
            return Number(match[1]);
    }
    return undefined;
}
async function runStep(step, opts) {
    const { dom, network, task, url } = opts;
    let snap = opts.snap;
    switch (step.use) {
        case 'dom_snapshot': {
            const result = await dom.snapshot({ mode: step.mode ?? 'compact' });
            if (!result.ok)
                return { ok: false, error: result.error.message };
            snap = result.data;
            return { ok: true, snap };
        }
        case 'page_signals_playback': {
            const { bundle } = await hydratePageSignals({ dom, network, url });
            const playback = tryMediaPlaybackDeterministicResult(bundle, task);
            if (!playback)
                return { ok: false, error: 'no resolved playback in PAGE SIGNALS' };
            return { ok: true, snap, payload: playback };
        }
        case 'dom_click': {
            if (step.selector && dom.clickSelector) {
                const clicked = await dom.clickSelector(step.selector);
                if (!clicked.ok)
                    return { ok: false, error: clicked.error.message };
                return { ok: true, snap };
            }
            if (!step.textIncludes)
                return { ok: false, error: 'dom_click needs textIncludes or selector' };
            const refreshed = await dom.snapshot({ mode: 'compact' });
            if (!refreshed.ok)
                return { ok: false, error: refreshed.error.message };
            snap = refreshed.data;
            const index = findClickIndex(snap, step.textIncludes);
            if (index == null)
                return { ok: false, error: `no element matching "${step.textIncludes}"` };
            const clicked = await dom.click(index, snap.revision);
            if (!clicked.ok)
                return { ok: false, error: clicked.error.message };
            return { ok: true, snap };
        }
        case 'dom_wait': {
            if (!dom.wait)
                return { ok: false, error: 'dom.wait unsupported' };
            const waited = await dom.wait({
                kind: step.kind,
                text: step.text,
                timeoutMs: step.timeout_ms,
            });
            if (!waited.ok)
                return { ok: false, error: waited.error.message };
            return { ok: true, snap, payload: waited.data.message };
        }
        case 'network_wait': {
            if (!network)
                return { ok: false, error: 'network plane unavailable' };
            const digest = await network.digest(1);
            if (!digest.ok) {
                const started = await network.start();
                if (!started.ok)
                    return { ok: false, error: started.error.message };
            }
            const waited = await network.wait({
                urlIncludes: step.urlIncludes,
                timeoutMs: step.timeout_ms ?? 15_000,
            });
            if (!waited.ok)
                return { ok: false, error: waited.error.message };
            const mediaUrl = waited.data.url;
            return {
                ok: true,
                snap,
                payload: `mediaUrl: ${mediaUrl}\nformat: ${/\.m3u8|mpegurl/i.test(mediaUrl) ? 'hls' : 'unknown'}`,
            };
        }
        default:
            return { ok: false, error: `unknown step ${step.use}` };
    }
}
export async function runSiteRecipe(opts) {
    let snap = opts.snap;
    let lastPayload;
    for (const step of opts.recipe.steps) {
        const result = await runStep(step, {
            dom: opts.dom,
            network: opts.network,
            snap,
            task: opts.task,
            url: opts.url,
        });
        if (!result.ok) {
            if (step.optional)
                continue;
            return { ok: false, error: result.error, recoverable: true };
        }
        snap = result.snap;
        if (result.payload) {
            lastPayload = result.payload;
            if (step.use === 'page_signals_playback') {
                return { ok: true, text: result.payload, recipeId: opts.recipe.id };
            }
        }
    }
    const text = lastPayload ??
        `Recipe "${opts.recipe.title}" completed (${opts.recipe.steps.length} steps).`;
    return { ok: true, text, recipeId: opts.recipe.id };
}
