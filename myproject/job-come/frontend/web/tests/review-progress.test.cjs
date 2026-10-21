const { test } = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const path = require('node:path');
function load(file) {
  const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/', file), 'utf8'),
    { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
  const mod = { exports: {} }; new Function('exports', code)(mod.exports); return mod.exports;
}
const { advanceReviewProgress, REVIEW_STAGES } = load('review-progress.ts');
const { readOperationResult } = load('operation-stream.ts');
test('review progress advances only on valid real stages and preserves terminal states', () => {
  let state = {};
  assert.equal(REVIEW_STAGES.length, 4);
  for (const id of ['read', 'rules']) {
    state = advanceReviewProgress(state, { stage: id, status: 'done' });
    assert.equal(state[id], 'done');
  }
  state = advanceReviewProgress(state, { stage: 'model', status: 'unavailable' });
  assert.equal(state.model, 'unavailable');
  assert.equal(advanceReviewProgress(state, { stage: 'model', status: 'done' }), state);
  assert.equal(advanceReviewProgress(state, { stage: 'read', status: 'running' }), state);
  assert.equal(advanceReviewProgress(state, { stage: 'fake', status: 'done' }), state);
  assert.equal(advanceReviewProgress(state, { stage: 'save', status: 'fake' }), state);
});
test('review SSE supports split CRLF, heartbeat, UTF8 and final unterminated result', async () => {
  const text = ': heartbeat\r\n\r\ndata: {"type":"progress","stage":"model","status":"unavailable"}\r\n\r\n' +
    'data: {"type":"result","data":{"status":"unavailable","notes":"未完成核对"}}';
  const bytes = new TextEncoder().encode(text);
  const response = new Response(new ReadableStream({ start(c) {
    for (const byte of bytes) c.enqueue(Uint8Array.of(byte)); c.close();
  }}));
  const seen = [];
  const result = await readOperationResult(response, (e) => seen.push(e));
  assert.equal(result.status, 'unavailable');
  assert.equal(result.notes, '未完成核对');
  assert.equal(seen.length, 1);
});

test('review screen defers auto-start so StrictMode probe mounts do not duplicate model calls', () => {
  const source = fs.readFileSync(path.join(__dirname, '../lib/hooks/useResumeQualityReview.ts'), 'utf8');
  assert.match(source, /React StrictMode/);
  assert.match(source, /window\.setTimeout\(\(\) => void runReview\(\), 0\)/);
  assert.match(source, /window\.clearTimeout\(scheduled\)/);
});
