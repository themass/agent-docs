import assert from 'node:assert/strict';
import { DeliverableVerifyHook } from './builtin-hooks.js';
import { buildTaskContract } from './task-contract.js';
import { evaluateEvidence } from './evaluator.js';
import { tryMediaHomePreflightDone } from './media-home-harvest.js';
import { createRuntimeState, reduceRuntimeState } from './runtime-state.js';
/**
 * End-to-end deterministic smoke fixture for the minimum useful Browser Agent
 * promise: homepage card -> retry transient Network attach -> media request ->
 * title + Network provenance.  It intentionally uses a generic card-shaped
 * accessibility snapshot, not a site/domain recipe.
 */
const snap = {
    revision: 7,
    url: 'https://example.test/home',
    title: 'Example home',
    header: '',
    content: [
        '*[13]<div >在线电影',
        '*[23]<img />',
        '*[24]<img />',
        'HD',
        '0:28:55',
        '从零实现一个浏览器 Agent',
        '站点官方 · 17.0万次观看',
    ].join('\n'),
    footer: '',
};
const task = '抓取当前网页首页视频的名称和原地址';
const contract = buildTaskContract(task);
let state = reduceRuntimeState(createRuntimeState(contract), {
    type: 'page_state',
    page: {
        url: snap.url,
        title: snap.title,
        role: 'list',
        blocked: false,
        items: [{ title: '从零实现一个浏览器 Agent', clickIndex: 24 }],
    },
    snapshot: { revision: snap.revision, url: snap.url, title: snap.title },
});
let startCalls = 0;
const clicks = [];
const notes = [];
const fakeCtx = {
    task,
    taskContract: contract,
    gates: { deliverable: 'media' },
    snap,
    pageState: state.page,
    runtimeState: state,
    metadata: {},
    agent: {
        planes: {
            dom: {
                click: async (index) => {
                    clicks.push(index);
                    return { ok: true, data: { clicked: true } };
                },
                wait: async () => ({ ok: true, data: { waited: true } }),
                // Re-snapshot after click (post-action-verify) must keep working on a
                // generic plane — same snapshot/url is a legitimate 'no DOM change' case.
                snapshot: async () => ({ ok: true, data: snap }),
                // Force the smoke path to prove that PAGE STATE works even when a
                // structured extraction has no rows.
                extractContent: async () => ({ ok: true, data: { items: [], candidates: 0 } }),
            },
            network: {
                digest: async () => ({
                    ok: false,
                    error: { code: 'not_attached', message: 'debugger attach pending', recoverable: true },
                }),
                start: async () => {
                    startCalls += 1;
                    return startCalls === 1
                        ? { ok: false, error: { code: 'attach_failed', message: 'temporary attach failure', recoverable: true } }
                        : { ok: true, data: { attached: true } };
                },
                clear: async () => ({ ok: true, data: { cleared: true } }),
                wait: async (opts) => {
                    assert.match(opts.urlRegex ?? '', /m3u8/);
                    return {
                        ok: true,
                        data: {
                            id: 'request-1',
                            method: 'GET',
                            url: 'https://cdn.example.test/video/master.m3u8?token=redacted',
                            mimeType: 'application/vnd.apple.mpegurl',
                            type: 'Media',
                            ts: Date.now(),
                        },
                    };
                },
                list: async () => ({ ok: true, data: [] }),
            },
        },
    },
    refreshNetwork: async () => undefined,
    createRecord: (type, payload) => ({ type, payload, at: Date.now() }),
    emit: () => undefined,
    syncRuntimePageState: () => {
        if (!fakeCtx.pageState)
            return;
        state = reduceRuntimeState(state, {
            type: 'page_state',
            page: fakeCtx.pageState,
            snapshot: { revision: fakeCtx.snap.revision, url: fakeCtx.snap.url, title: fakeCtx.snap.title },
        });
        fakeCtx.runtimeState = state;
    },
    recordNote: (note) => notes.push(note),
    recordEvidence: (input) => {
        state = reduceRuntimeState(state, { type: 'evidence', evidence: input });
        fakeCtx.runtimeState = state;
    },
};
const result = await tryMediaHomePreflightDone(fakeCtx);
assert.match(result ?? '', /从零实现一个浏览器 Agent/);
assert.match(result ?? '', /master\.m3u8/);
assert.deepEqual(clicks, [24], 'must click the card, never the category node at index 13');
assert.equal(startCalls, 2, 'first transient attach failure must be retried by the media candidate path');
assert.equal(fakeCtx.runtimeState.capabilities.network.status, 'available');
const evaluation = evaluateEvidence(contract, fakeCtx.runtimeState.evidence.records);
assert.equal(evaluation.status, 'complete', `missing: ${evaluation.missing.join(', ')}`);
assert.ok(fakeCtx.runtimeState.evidence.records.some((item) => item.source === 'network_media'));
assert.ok(fakeCtx.runtimeState.evidence.records.some((item) => item.source === 'media_title'));
assert.ok(notes.some((note) => note.includes('recoverable')), 'retry must be auditable');
// A model cannot satisfy a strict source-address request by merely inventing a
// URL-shaped string. Completion is allowed only after Network provenance (or
// after it explicitly reports the shortfall).
const verify = new DeliverableVerifyHook();
const blocked = verify.beforeTool({
    task,
    taskContract: contract,
    gates: { deliverable: 'media' },
    runtimeState: createRuntimeState(contract),
    toolCall: { tool: 'system_done', arguments: { result: '播放源：https://cdn.example.test/fake.m3u8' } },
});
assert.equal(blocked.kind, 'skip_tool');
const permitted = verify.beforeTool({
    task,
    taskContract: contract,
    gates: { deliverable: 'media' },
    runtimeState: fakeCtx.runtimeState,
    toolCall: { tool: 'system_done', arguments: { result: result ?? '' } },
});
assert.equal(permitted.kind, 'continue');
console.log('media-smoke.self-check ok');
