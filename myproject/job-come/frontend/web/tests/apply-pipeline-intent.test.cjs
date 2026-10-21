const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const source = fs.readFileSync(path.join(__dirname, '../lib/api/jobs.ts'), 'utf8');
const code = ts.transpileModule(source, {compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS,
}}).outputText;
const mod = { exports: {} };
const calls = [];
new Function('exports', 'require', code)(mod.exports, () => ({
  apiJson: (url, options) => { calls.push({url, ...options}); return Promise.resolve({}); },
}));
test('preparing materials does not implicitly claim submission', async () => {
  await mod.exports.runApplyPipeline('p', { job_id: 'j' });
  assert.equal(JSON.parse(calls.at(-1).body).create_application, false);
});
test('explicit confirmed submission remains supported for compatibility', async () => {
  await mod.exports.runApplyPipeline('p', { job_id: 'j', create_application: true });
  assert.equal(JSON.parse(calls.at(-1).body).create_application, true);
});
