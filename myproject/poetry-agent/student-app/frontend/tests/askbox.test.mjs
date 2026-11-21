/**
 * 「我想问」的纯逻辑 + 与词表、本地兜底的约束。不碰 DOM（组件本身的渲染由截图脚本覆盖）。
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { cleanQuestion, QUESTION_MAX } from '../src/ui/ask-box.js';
import { ASK_ACTIONS } from '../src/core/vocab.js';
import { localTurn } from '../src/data/local-help.js';
import { indexBundle } from '../src/data/facts.js';
import { bundle, pack } from './helpers.mjs';

test('cleanQuestion: trims, collapses whitespace, caps the length', () => {
  assert.equal(cleanQuestion('  他   为什么\n哭  '), '他 为什么 哭');
  assert.equal(cleanQuestion('字'.repeat(QUESTION_MAX + 50)).length, QUESTION_MAX);
});

test('cleanQuestion: nothing answerable means nothing is sent', () => {
  for (const empty of ['', '   ', null, undefined, '？？？', '……', '!!']) assert.equal(cleanQuestion(empty), null, String(empty));
});

test('cleanQuestion: a question with a number or a name still goes through', () => {
  assert.equal(cleanQuestion('757年是哪一年？'), '757年是哪一年？');
});

test('a reader\'s own question is not an event: free_text is not in the recorded vocabulary', () => {
  assert.equal(ASK_ACTIONS.includes('free_text'), false);
});

test('offline free_text: says it cannot answer, and never echoes what the reader typed', () => {
  const index = indexBundle(bundle());
  const typed = '杜甫的手机号是13800138000';
  const reply = localTurn({ action: 'free_text', step: 'arrive', args: { text: typed }, index, pack: pack() });
  assert.equal(reply.role, 'guide');
  assert.equal(reply.unavailable, true);
  assert.match(reply.say, /没连上/);
  assert.equal(JSON.stringify(reply).includes('13800138000'), false, 'must not echo the typed text');
  assert.equal(JSON.stringify(reply).includes(typed), false);
  assert.deepEqual(reply.basis, [], 'an offline non-answer cites nothing');
});
