import assert from 'node:assert/strict';
import { buildTaskContract } from './task-contract.js';
import { createRuntimeState, reduceRuntimeState } from './runtime-state.js';
import { evaluateEvidence } from './evaluator.js';
const media = buildTaskContract('分析这个页面里的视频，名称和播放链接');
assert.equal(media.deliverable, 'media');
assert.equal(media.capabilities.network, 'required');
assert.ok(media.requiredEvidence.includes('media_url'));
const state = createRuntimeState(media);
const withPage = reduceRuntimeState(state, {
    type: 'evidence',
    evidence: { kind: 'page', source: 'page_state', summary: 'media list', confidence: 0.9 },
});
const withTitle = reduceRuntimeState(withPage, {
    type: 'evidence',
    evidence: { kind: 'dom', source: 'media_title', summary: 'video title', confidence: 0.9 },
});
const partial = evaluateEvidence(media, withTitle.evidence.records);
assert.equal(partial.status, 'needs_recovery');
assert.ok(partial.missing.includes('media_url'));
const complete = evaluateEvidence(media, [
    ...withTitle.evidence.records,
    { id: 'network-1', kind: 'network', source: 'network_media', summary: 'https://cdn.test/a.m3u8', at: Date.now() },
]);
assert.equal(complete.status, 'complete');
console.log('task-contract.self-check ok');
