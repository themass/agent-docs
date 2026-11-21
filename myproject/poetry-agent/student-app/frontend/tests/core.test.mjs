import test from 'node:test';
import assert from 'node:assert/strict';
import { parseHash, matchRoute } from '../src/core/router.js';
import { createStore, createKv } from '../src/core/store.js';
import { gaps, lanes, spanText, yearText } from '../src/core/time.js';
import { memKv } from './helpers.mjs';

test('router: params, query, trailing slash, hostile segments', () => {
  const routes = [{ pattern: '/poem/:workId' }, { pattern: '/lesson/:workId/:step' }];
  assert.deepEqual(parseHash('#/lesson/work-x/arrive?a=1'), { path: '/lesson/work-x/arrive', query: { a: '1' } });
  assert.equal(matchRoute(routes, '/poem/work-chun-wang/').params.workId, 'work-chun-wang');
  assert.equal(matchRoute(routes, '/poem/%E0%A4%A'), null);              // malformed escape must not throw
  assert.equal(matchRoute(routes, '/poem/a/b'), null);
});

test('store: prefs persist, consent is tri-state, fontScale is clamped, no score anywhere', () => {
  const kv = memKv();
  const s = createStore(kv);
  assert.equal(s.get('consent'), null);
  s.set('consent', 'no'); s.set('fontScale', 9);
  assert.equal(s.get('fontScale'), 1.6);
  assert.equal(s.get('audience'), undefined);                             // no grade preference exists
  const again = createStore(kv);
  assert.equal(again.get('consent'), 'no');
  assert.equal(again.pinyinOn(), false);                                  // a reading aid, off until turned on
  again.set('pinyin', true);
  assert.equal(createStore(kv).pinyinOn(), true);                         // and it persists
  s.patchProgress('w', { lastStep: 'arrive', visited: ['read', 'arrive'] });
  assert.deepEqual(Object.keys(s.progressOf('w')).sort(), ['enteredAt', 'lastStep', 'visited']);
});

test('kv survives a storage that throws (private mode / quota)', () => {
  const broken = { getItem() { throw new Error('x'); }, setItem() { throw new Error('x'); }, removeItem() { throw new Error('x'); } };
  const kv = createKv(broken);
  assert.equal(kv.set('a', { b: 1 }), false);
  assert.deepEqual(kv.get('a'), { b: 1 });                                // memory fallback
});

test('time: disputed/unknown dates are said out loud; gaps are not empty space', () => {
  assert.equal(spanText({ timePrecision: 'UNKNOWN' }), '年代不可考');
  assert.equal(spanText({ startYear: 757, endYear: 757, timePrecision: 'EXACT' }), '757年');
  assert.match(spanText({ startYear: 712, endYear: 770, timePrecision: 'APPROXIMATE' }), /^约 /);
  assert.equal(yearText(-221), '公元前221年');
  assert.deepEqual(gaps(0, 100, [{ start: 20, end: 40 }, { start: 30, end: 60 }]), [{ start: 0, end: 20 }, { start: 60, end: 100 }]);
  assert.deepEqual(gaps(0, 10, []), [{ start: 0, end: 10 }]);
  const { placed, count } = lanes([{ start: 0, end: 10 }, { start: 5, end: 12 }, { start: 20, end: 25 }], 1);
  assert.equal(count, 2);
  assert.equal(placed.find(p => p.start === 20).lane, 0);
});
