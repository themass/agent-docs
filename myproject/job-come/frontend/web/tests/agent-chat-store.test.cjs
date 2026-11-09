// A new interview must not reuse the chat the last one was in (its thread keeps the old turns).
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');

const file = path.join(__dirname, '..', 'lib', 'agent-chat-store.ts');
const code = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText;
const exportsOf = {};
new Function('exports', code)(exportsOf);
const { chatStorageKey, forgetStoredChat } = exportsOf;

function fakeStorage(entries) {
  const map = new Map(Object.entries(entries));
  return { removeItem: (k) => map.delete(k), getItem: (k) => map.get(k) ?? null, has: (k) => map.has(k) };
}

test('the storage key is the one the chat hook has always used', () => {
  assert.equal(chatStorageKey('coach-agent-job_1', 'p1'), 'jc_agent_session_coach-agent-job_1_p1');
  assert.equal(chatStorageKey('coach-agent-general', null), 'jc_agent_session_coach-agent-general_none');
});

test('starting an interview forgets the remembered chat for that page and profile', () => {
  const key = chatStorageKey('coach-agent-job_1', 'p1');
  const storage = fakeStorage({ [key]: 'agsn_old' });
  forgetStoredChat(storage, 'coach-agent-job_1', 'p1');
  assert.equal(storage.has(key), false);
});

test('forgetting touches only that page and profile', () => {
  const mine = chatStorageKey('coach-agent-job_1', 'p1');
  const otherJob = chatStorageKey('coach-agent-job_2', 'p1');
  const otherProfile = chatStorageKey('coach-agent-job_1', 'p2');
  const storage = fakeStorage({ [mine]: 'a', [otherJob]: 'b', [otherProfile]: 'c' });
  forgetStoredChat(storage, 'coach-agent-job_1', 'p1');
  assert.equal(storage.has(mine), false);
  assert.equal(storage.has(otherJob), true);
  assert.equal(storage.has(otherProfile), true);
});
