import { formatPageSignalsForPrompt, minePageSignals, } from '@naviforge/observe';
import { WORKING_SET } from './working-set.js';
import { markObservationSeen } from './loop-gate-state.js';
async function collectScriptBodies(network, externalScriptSrcs) {
    const bodies = [];
    const seen = new Set();
    const push = (items) => {
        for (const item of items) {
            if (seen.has(item.url))
                continue;
            seen.add(item.url);
            bodies.push(item);
        }
    };
    if (network?.listScriptBodies) {
        const listed = await network.listScriptBodies({ limit: 6 });
        if (listed.ok)
            push(listed.data);
    }
    if (network?.fetchScriptContents && externalScriptSrcs.length) {
        const missing = externalScriptSrcs.filter((url) => !seen.has(url)).slice(0, 6);
        if (missing.length) {
            const fetched = await network.fetchScriptContents(missing);
            if (fetched.ok)
                push(fetched.data);
        }
    }
    return bodies;
}
export async function hydratePageSignals(opts) {
    if (!opts.dom.collectPageSignalRaw) {
        const bundle = { url: opts.url, signals: [] };
        return { text: formatPageSignalsForPrompt(bundle), bundle };
    }
    const raw = await opts.dom.collectPageSignalRaw();
    if (!raw.ok) {
        const bundle = { url: opts.url, signals: [] };
        return {
            text: `PAGE SIGNALS (${opts.url})\n(collect failed: ${raw.error.message})`,
            bundle,
        };
    }
    let networkUrls = [];
    if (opts.network) {
        const listed = await opts.network.list({ limit: 160 });
        if (listed.ok)
            networkUrls = listed.data.map((event) => event.url);
    }
    const scriptBodies = [
        ...(opts.scriptBodies ?? []),
        ...(await collectScriptBodies(opts.network, raw.data.externalScriptSrcs)),
    ];
    const bundle = minePageSignals(raw.data, {
        networkUrls,
        scriptBodies: scriptBodies.length ? scriptBodies : undefined,
    });
    return { text: formatPageSignalsForPrompt(bundle), bundle };
}
/** List/catalog pages expose detail links; streams live on play/detail pages. */
export function formatListPageMediaHint(bundle, task, brief) {
    if (!isMediaEvidenceTask(task))
        return undefined;
    if (brief?.role === 'play')
        return undefined;
    const hasPlayback = bundle.signals.some((s) => s.kind === 'resolved' && s.label === 'playback' && s.resolvedUrl);
    if (hasPlayback && brief?.role !== 'list')
        return undefined;
    if (brief?.role === 'list' || (brief?.listItemCount ?? 0) >= 3) {
        return [
            'NOTE: 当前页为列表/目录页，HTML 通常只有详情/播放页链接，不含直链流。',
            '可播放地址可能是 m3u8/mpd/mp4/webm 或内嵌播放页 — 须 spawn 打开各 URL，读 PAGE SIGNALS；无直链写 playPageUrl。',
            '列表页禁止 execute_js 挖媒体；用 system_spawn_readonly_tasks（每批 ≤3）。',
        ].join('\n');
    }
    return undefined;
}
export async function applyPageSignalsToCtx(ctx, opts) {
    const url = opts?.url ?? ctx.snap.url;
    const { text, bundle } = await hydratePageSignals({
        dom: ctx.agent.planes.dom,
        network: ctx.agent.planes.network,
        url,
        scriptBodies: opts?.scriptBodies,
    });
    const listHint = formatListPageMediaHint(bundle, ctx.task, opts?.pageBrief);
    const fullText = listHint ? `${text}\n\n${listHint}` : text;
    ctx.pageSignalsText = fullText;
    const sigKey = `page_signals|${url}`;
    markObservationSeen(ctx.gates, sigKey, fullText.slice(0, WORKING_SET.evidenceChars));
    ctx.gates.stepsWithoutNewObs = 0;
    ctx.recordNote(`EVIDENCE: ${fullText.slice(0, WORKING_SET.evidenceChars)}`);
    ctx.emit(ctx.createRecord('run.note', {
        topic: 'page_signals',
        text: formatPageSignalsForPrompt(bundle, 1_600),
    }));
    ctx.emit(ctx.createRecord('run.log', {
        message: `page signals refreshed (${bundle.signals.length} signals) for ${url}`,
    }));
    return bundle;
}
export function isMediaEvidenceTask(task) {
    return /播放|视频|m3u8|mp4|stream|playback|media url|播放地址|流地址/i.test(task);
}
/** E / F6: high-confidence resolved playback → skip model when unambiguous single-item task. */
export function tryMediaPlaybackDeterministicResult(bundle, task, opts) {
    if (!isMediaEvidenceTask(task))
        return undefined;
    if (opts?.strategy === 'spawn-media' || opts?.strategy === 'current-page-list' || opts?.strategy === 'full-catalog') {
        return undefined;
    }
    if (!opts?.strategy && /所有|全部|每个|各条|批量|每一|all|every/i.test(task))
        return undefined;
    const playback = bundle.signals.filter((s) => s.kind === 'resolved' && s.label === 'playback' && (s.confidence ?? 0) >= 0.9 && s.resolvedUrl);
    if (!playback.length)
        return undefined;
    const uniqueUrls = [...new Set(playback.map((s) => s.resolvedUrl))];
    if (uniqueUrls.length === 1) {
        const p = playback.find((s) => s.resolvedUrl === uniqueUrls[0]) ?? playback[0];
        return `可播放地址（PAGE SIGNALS，${p.label ?? 'stream'}）：\n${p.resolvedUrl}\n\n来源：${p.source}${p.reason ? ` (${p.reason})` : ''}`;
    }
    // F6: multiple CDN candidates — leave to model + PAGE SIGNALS / HITL
    return undefined;
}
export function formatPlaybackCandidatesForHitl(bundle) {
    const playback = bundle.signals.filter((s) => s.kind === 'resolved' && s.label === 'playback' && s.resolvedUrl);
    if (playback.length < 2)
        return undefined;
    return [
        '多个候选播放地址（请确认或选择）：',
        ...playback.slice(0, 6).map((s, i) => `${i + 1}. ${s.resolvedUrl} — ${s.reason ?? s.source}`),
    ].join('\n');
}
