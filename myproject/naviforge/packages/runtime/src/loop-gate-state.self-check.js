import assert from 'node:assert/strict';
import { createAgentGates, hasSynthesisEvidence, recordRunTab, scopeTabsToRun, } from './loop-gate-state.js';
const gates = createAgentGates(2);
recordRunTab(gates, 101);
recordRunTab(gates, 202);
const all = [
    { id: 1, title: 'noise', url: 'https://a', active: false },
    { id: 101, title: 'pi', url: 'https://pi', active: false },
    { id: 202, title: 'prime', url: 'https://prime', active: true },
];
const scoped = scopeTabsToRun(all, gates, 303);
assert.equal(scoped.tabs.length, 2, 'scopes to run tabs');
assert.equal(scoped.scoped, true);
assert.equal(scoped.totalBrowserTabs, 3);
gates.subtaskEvidenceReady = true;
assert.equal(hasSynthesisEvidence(gates), true, 'subtask flag counts as evidence');
const fresh = createAgentGates(2);
fresh.seenObs.add('dom_read|https://x|body');
assert.equal(hasSynthesisEvidence(fresh), true, 'dom_read observation counts');
console.log('loop-gate-state self-check ok');
