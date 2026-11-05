const { test } = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const path = require('node:path');

const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/report-poll.ts'), 'utf8'),
 { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const mod = { exports: {} }; new Function('exports', code)(mod.exports);
const { nextPoll, POLL_BASE_MS, POLL_MAX_MS, POLL_GIVE_UP_MS, START } = mod.exports;

const ok = { ok: true };
const failed = (status) => ({ ok: false, status });

test('a good answer keeps the base pace and clears earlier failures', () => {
  const first = nextPoll(START, failed(503));
  const next = nextPoll(first.state, ok);
  assert.equal(next.delayMs, POLL_BASE_MS);
  assert.equal(next.state.failures, 0);
  assert.equal(next.stopped, null);
});

test('a failure that may pass backs off, doubling up to a ceiling', () => {
  let state = START;
  const delays = [];
  for (let i = 0; i < 8; i++) {
    const step = nextPoll(state, failed(503));
    delays.push(step.delayMs);
    state = step.state;
  }
  assert.deepEqual(delays.slice(0, 3), [POLL_BASE_MS * 2, POLL_BASE_MS * 4, POLL_BASE_MS * 8]);
  assert.ok(delays.every((d) => d <= POLL_MAX_MS));
  assert.equal(delays[delays.length - 1], POLL_MAX_MS);
});

test('a network error with no status is retried like a server error', () => {
  const step = nextPoll(START, { ok: false, status: null });
  assert.equal(step.stopped, null);
  assert.equal(step.delayMs, POLL_BASE_MS * 2);
});

test('a refusal that will not change stops the polling', () => {
  for (const status of [400, 401, 403, 404]) {
    const step = nextPoll(START, failed(status));
    assert.equal(step.stopped, 'rejected', `status ${status}`);
    assert.equal(step.delayMs, null);
  }
});

test('a request timeout or rate limit is worth retrying, not a refusal', () => {
  for (const status of [408, 429]) {
    assert.equal(nextPoll(START, failed(status)).stopped, null, `status ${status}`);
  }
});

test('polling gives up after waiting too long, and says so', () => {
  let state = START;
  let step;
  let polls = 0;
  do {
    step = nextPoll(state, ok);
    state = step.state;
    polls += 1;
  } while (step.stopped === null && polls < 10_000);
  assert.equal(step.stopped, 'gave_up');
  assert.equal(step.delayMs, null);
  assert.ok(polls * POLL_BASE_MS >= POLL_GIVE_UP_MS);
  assert.ok((polls - 1) * POLL_BASE_MS < POLL_GIVE_UP_MS);
});

test('the wait counts the delays that were waited, backed off or not', () => {
  const step = nextPoll(START, failed(500));
  assert.equal(step.state.elapsedMs, POLL_BASE_MS * 2);
});
