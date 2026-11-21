import test from 'node:test';
import assert from 'node:assert/strict';
import { validateEvent, createTracker, retellLength } from '../src/data/events.js';
import { indexBundle } from '../src/data/facts.js';
import { localTurn } from '../src/data/local-help.js';
import { ApiError, createApi } from '../src/data/api.js';
import { createRepo } from '../src/data/repo.js';
import { ASK_ACTIONS, EVENT_KINDS } from '../src/core/vocab.js';
import { bundle, pack, memKv } from './helpers.mjs';
import { situationOf, pickToday, hookOf } from '../src/views/selectors.js';

const ev = o => ({ workId: 'work-chun-wang', step: 'arrive', kind: 'step_enter', ...o });

test('events: whitelist only, no free text can pass', () => {
  assert.equal(validateEvent(ev({})), null);
  assert.equal(validateEvent(ev({ kind: 'layer_open', ref: 'WORLD' })), null);
  for (const bad of [ev({ kind: 'ask', ref: '我家住在北京' }), ev({ kind: 'retell_submit', step: 'recite', ref: '杜甫被困在长安' }),
    ev({ kind: 'step_leave' }), ev({ kind: 'step_leave', ms: -1 }), ev({ kind: 'line_tap', step: 'meet', ref: '3' }),
    ev({ kind: 'line_tap', step: 'read', ref: '0' }), ev({ kind: 'score' }), ev({ workId: '../x' })])
    assert.notEqual(validateEvent(bad), null, JSON.stringify(bad));
  assert.equal(retellLength('x'.repeat(21)), 'len_21_60');
});

test('events: vocabularies match the server (StudentVocabulary)', () => {
  assert.equal(EVENT_KINDS.length, 9);
  assert.deepEqual([...ASK_ACTIONS].sort(), ['ask_why', 'basis', 'decline', 'hint', 'open_layer', 'recite_prompt', 'rephrase']);
});

test('tracker: nothing is queued before consent; a refused batch cannot wedge the queue', async () => {
  const kv = memKv(); let consent = false; const sent = [];
  const api = { post: async (_p, batch) => { sent.push(batch); throw new ApiError('http', 400, 'x'); } };
  const t = createTracker({ api, kv, getDevice: async () => ({ deviceKey: 'k' }), allowed: () => consent, setTimer: () => 0 });
  assert.equal(t.track(ev({})), false);
  assert.equal(t.pending(), 0);
  consent = true;
  assert.equal(t.track(ev({})), true);
  await t.flush();
  assert.equal(sent.length, 1);
  assert.equal(t.pending(), 0);                                           // 400 => dropped
});

test('facts: ids match the agent scheme; unbadged dramatization is skipped but still consumes its index', () => {
  const b = bundle();
  const idx = indexBundle(b);
  assert.ok(idx.facts.has('arrive/WORLD/0') && idx.facts.has('meet/PERSON/0') && idx.facts.has('return/PERSON/0'));
  assert.equal(idx.facts.get('meet/PERSON/0').owner, 'poet');
  const broken = structuredClone(b);
  delete broken.steps.find(s => s.step === 'meet').roleplay.layers[0].lines[0].badge;
  assert.equal(indexBundle(broken).facts.has('meet/PERSON/0'), false);
});

test('local help: answers from the bundle, and cannot grade a retell', () => {
  const index = indexBundle(bundle());
  const open = localTurn({ action: 'open_layer', step: 'arrive', args: { layer: 'CITY' }, index, pack: pack() });
  assert.equal(open.role, 'narrator');
  assert.ok(open.basis.every(b => index.facts.has(b.id)));
  const dram = localTurn({ action: 'basis', step: 'meet', args: {}, index, pack: pack() });
  assert.equal(dram.badge, 'DRAMATIZATION');
  const hint5 = localTurn({ action: 'hint', step: 'return', args: { line_seq: 5 }, index, pack: pack() });
  assert.match(hint5.say, /烽火/);                                       // every reader gets the note: there is no grade split
  const retell = localTurn({ action: 'evaluate_retell', step: 'recite', args: { text: 'x' }, index, pack: pack() });
  assert.equal(retell.evaluation, null);
  assert.ok(!JSON.stringify(retell).match(/score|分数|错/));
});

test('api + repo: offline falls back to cache, 404 deletes the cache, bundles are cache-first', async () => {
  const kv = memKv(); let mode = 'ok'; const calls = [];
  const fetchImpl = async url => {
    calls.push(url);
    if (mode === 'down') throw new TypeError('offline');
    if (mode === '404') return { ok: false, status: 404, headers: { get: () => null }, json: async () => ({}) };
    return { ok: true, status: 200, headers: { get: () => 'demo-fixture' }, json: async () => ({ errno: 0, data: { n: calls.length } }) };
  };
  const seen = []; const repo = createRepo({ api: createApi({ base: '/x', fetchImpl }), kv, onSource: s => seen.push(s) });
  const first = await repo.works();
  mode = 'down';
  assert.deepEqual(await repo.works(), first);
  assert.equal(seen.at(-1), 'offline-cache');
  mode = '404';
  await assert.rejects(repo.works());
  mode = 'down';
  await assert.rejects(repo.works());                                     // cache was deleted
  const n = calls.length;
  mode = 'ok'; await repo.bundle('h'); await repo.bundle('h');
  assert.equal(calls.length, n + 1);
});

/* ---------------------------------------------------------------- 「到」的处境句 */
const arriveOnly = (situation, layers) => ({ steps: [{ step: 'arrive', situation, layers: layers || [] }] });
const sit = o => ({ text: '至德二载的春天，长安。先看哪儿？', kind: 'DRAMATIZATION', badge: '演绎 · 不是史料',
  choices: [{ layer: 'SCENE', label: '看看城' }, { layer: 'CITY', label: '看看这座城' },
    { layer: 'WORLD', label: '看看外面' }, { layer: 'PERSON', label: '看看他' }], ...o });

test('situation: a bundle without one falls back to the four cards (not an error)', () => {
  assert.equal(situationOf({ steps: [{ step: 'arrive' }] }, ['SCENE', 'CITY']), null);
  assert.equal(situationOf({ steps: [] }, []), null);
  assert.equal(situationOf({}, []), null);
});

test('situation: a dramatisation with no badge is not shown (same rule as a spoken line)', () => {
  assert.equal(situationOf(arriveOnly(sit({ badge: undefined })), ['SCENE']), null);
  // …but an unattributed FACT/INTERPRETATION is fine: it carries claim_id instead
  assert.ok(situationOf(arriveOnly(sit({ kind: 'INTERPRETATION', badge: undefined, basis: { claim_id: 'claim-bg-person' } })), ['SCENE']));
});

test('situation: pointers to layers this step does not have are dropped, never left dangling', () => {
  const s = situationOf(arriveOnly(sit({})), ['SCENE', 'PERSON']);
  assert.deepEqual(s.choices.map(c => c.layer), ['SCENE', 'PERSON']);
  assert.deepEqual(s.choices.map(c => c.label), ['看看城', '看看他']);
  // no usable layers at all: the sentence still shows, it just has nothing to point at
  const none = situationOf(arriveOnly(sit({})), []);
  assert.equal(none.text.length > 0, true);
  assert.deepEqual(none.choices, []);
});

test('situation: the sample bundle carries one, and its badge is the fixed OQ-01 wording', () => {
  const s = situationOf(bundle(), ['SCENE', 'CITY', 'WORLD', 'PERSON']);
  assert.ok(s, 'sample bundle must have an arrive situation');
  assert.equal(s.kind, 'DRAMATIZATION');
  assert.equal(s.badge, '演绎 · 不是史料');
  assert.equal(/至德|\d{3}/.test(s.text), false);   // picks no year: the bundle says the date is unsettled
  assert.deepEqual(s.choices.map(c => c.layer), ['SCENE', 'CITY', 'WORLD', 'PERSON']);
  for (const c of s.choices) assert.ok(c.label.length >= 2 && c.label.length <= 12, c.label);
});

/* ---------------------------------------------------------------- 首屏「今天」 */
test('today: a half-walked poem wins; else the first untouched; lessons only; empty is null', () => {
  const W = (id, hasLesson = true) => ({ workId: id, title: id, hasLesson });
  const prog = { b: { lastStep: 'arrive', enteredAt: '2026-11-01T00:00:00Z' }, c: { lastStep: 'meet', enteredAt: '2026-11-05T00:00:00Z' } };
  assert.equal(pickToday([W('a'), W('b'), W('c')], id => prog[id]).work.workId, 'c');      // most recent of the two in progress
  assert.equal(pickToday([W('a'), W('b')], id => (id === 'a' ? { visited: ['read'] } : null)).work.workId, 'b'); // a touched but no lastStep -> b untouched
  assert.equal(pickToday([W('x', false)], () => null), null);
  assert.equal(pickToday([], () => null), null);
});

test('today: the hook sentence only ever comes from the server, never made up', () => {
  assert.equal(hookOf({ hook: '  一封家书？ ' }), '一封家书？');
  assert.equal(hookOf({ hook: '' }), null);
  assert.equal(hookOf({ summary: '待核查：作者归属' }), null);                                // summary is an editor note, not a hook
});

test('local help: free_text offline says it could not read the question; it never claims "not covered" and never echoes the words', () => {
  const index = indexBundle(bundle());
  const r = localTurn({ action: 'free_text', step: 'arrive', args: { text: '他为什么被困在长安' }, index, pack: pack() });
  assert.equal(r.unavailable, true);
  assert.equal(r.source, 'local');
  assert.equal(r.say.includes('没连上'), true);
  assert.equal(r.say.includes('没有讲到'), false);          // that sentence is the agent's verdict on a question it actually read
  assert.equal(r.say.includes('被困'), false);              // the learner's words are not repeated back or kept
  assert.equal(r.badge, 'NONE');                            // an apology is not a fact, an interpretation or a dramatisation
});
