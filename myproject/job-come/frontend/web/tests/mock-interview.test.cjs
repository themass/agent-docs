const { test } = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const path = require('node:path');

const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/mock-interview.ts'), 'utf8'),
 { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const mod = { exports: {} }; new Function('exports', code)(mod.exports);
const { STAGE_LABEL, formatElapsed, barText, SKIP_MESSAGE, SWAP_MESSAGE } = mod.exports;

const progress = (over = {}) => ({
  status: 'active', stage: 'core', suggested_stage: 'core', asked_main: 3, main_limit: 20,
  candidate_qa: false, ...over,
});

test('every stage the server can report has a label', () => {
  for (const stage of ['opening', 'experience', 'core', 'scenario', 'candidate_qa']) {
    assert.ok(STAGE_LABEL[stage], stage);
  }
  assert.equal(STAGE_LABEL.candidate_qa, '候选人提问');
});

test('elapsed time reads as minutes and seconds, then hours', () => {
  assert.equal(formatElapsed(0), '00:00');
  assert.equal(formatElapsed(65_000), '01:05');
  assert.equal(formatElapsed(59 * 60_000 + 59_000), '59:59');
  assert.equal(formatElapsed(3_600_000 + 61_000), '1:01:01');
});

test('a clock that is ahead of the server never shows a negative time', () => {
  assert.equal(formatElapsed(-5_000), '00:00');
  assert.equal(formatElapsed(Number.NaN), '00:00');
});

test('the bar names the question the interview is on, out of how many', () => {
  assert.equal(barText(progress({ asked_main: 3 })).position, '第 3 / 20 题');
});

test('before the first question the bar says the interview is opening', () => {
  const text = barText(progress({ asked_main: 0, stage: 'opening' }));
  assert.equal(text.position, '开场');
  assert.equal(text.stage, STAGE_LABEL.opening);
});

test('during the candidate turn the bar says so instead of counting questions', () => {
  const text = barText(progress({ asked_main: 20, stage: 'candidate_qa', candidate_qa: true }));
  assert.equal(text.position, '候选人提问');
  assert.equal(text.stage, '');
});

test('an unknown stage from a newer server is shown as nothing rather than as a code', () => {
  assert.equal(barText(progress({ stage: 'something_new' })).stage, '');
});

test('the lines the page says for the candidate are the ones the server reads as steering', () => {
  // tests/test_mock_answer_recorder.py pins the same two lines on the server side.
  assert.equal(SKIP_MESSAGE, '跳过这题，请出下一题。');
  assert.equal(SWAP_MESSAGE, '换一题，请出下一题。');
});
