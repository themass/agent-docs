import assert from 'node:assert/strict';
import { buildTaskContract } from './task-contract.js';
import { createRuntimeState, reduceRuntimeState } from './runtime-state.js';
import { attachPageState } from './pi-run-loop.js';
function makeCtx(snap) {
    const contract = buildTaskContract('分析这个页面里的视频，名称和播放链接');
    let state = createRuntimeState(contract);
    let emittedPageStateNotes = 0;
    const ctx = {
        task: '分析这个页面里的视频，名称和播放链接',
        taskContract: contract,
        gates: {},
        snap,
        pageState: undefined,
        runtimeState: state,
        metadata: {},
        agent: {
            planes: {
                dom: {
                    extractContent: async () => ({ ok: true, data: { items: [], candidates: 0 } }),
                },
            },
        },
        createRecord: (type, payload) => ({ type, payload, at: Date.now() }),
        emit: (record) => {
            if (record.type === 'run.note' && record.payload.topic === 'page_state') {
                emittedPageStateNotes += 1;
            }
        },
        recordNote: () => undefined,
        syncRuntimePageState: () => {
            state = reduceRuntimeState(state, {
                type: 'page_state',
                page: ctx.pageState,
                snapshot: { revision: snap.revision, url: snap.url, title: snap.title },
            });
            ctx.runtimeState = state;
        },
    };
    return { ctx: ctx, pageStateNoteCount: () => emittedPageStateNotes };
}
// --- Calling attachPageState twice for the same (url, revision) — e.g. once
// at run start (agent.ts) and once more from PreflightHook (builtin-hooks.ts)
// before any navigation/click happens in between — must only compute and
// emit PAGE STATE once. Regression for the duplicate PAGE STATE notes seen
// twice in a row in tests/message.txt (token waste, no new information).
{
    const snap = {
        revision: 1,
        url: 'https://example.test/home',
        title: 'Home',
        header: '',
        content: '',
        footer: '',
    };
    const { ctx, pageStateNoteCount } = makeCtx(snap);
    await attachPageState(ctx);
    assert.equal(pageStateNoteCount(), 1, 'first call computes and emits PAGE STATE');
    await attachPageState(ctx);
    assert.equal(pageStateNoteCount(), 1, 'second call with unchanged (url, revision) must not re-emit');
}
// --- A new snapshot revision (real navigation/DOM mutation) must bust the
// cache and recompute — idempotency must not become staleness.
{
    const snap = {
        revision: 1,
        url: 'https://example.test/home',
        title: 'Home',
        header: '',
        content: '',
        footer: '',
    };
    const { ctx, pageStateNoteCount } = makeCtx(snap);
    await attachPageState(ctx);
    assert.equal(pageStateNoteCount(), 1);
    ctx.snap = { ...snap, revision: 2 };
    await attachPageState(ctx);
    assert.equal(pageStateNoteCount(), 2, 'a new revision must trigger a fresh PAGE STATE compute');
}
console.log('pi-run-loop self-check ok');
