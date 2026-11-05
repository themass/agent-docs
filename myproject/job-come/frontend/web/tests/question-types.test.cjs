const { test } = require('node:test');
const assert = require('node:assert/strict');
const ts = require('typescript');
const fs = require('node:fs');
const path = require('node:path');

const code = ts.transpileModule(fs.readFileSync(path.join(__dirname, '../lib/question-types.ts'), 'utf8'),
 { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText;
const mod = { exports: {} }; new Function('exports', code)(mod.exports);
const { QUESTION_TYPES, questionTypeLabel } = mod.exports;

test('the types that already exist keep their ids and their labels', () => {
  const byId = Object.fromEntries(QUESTION_TYPES.map((t) => [t.id, t.label]));
  assert.equal(byId.behavioral, '行为/STAR');
  assert.equal(byId.project_deep, '项目深挖');
  assert.equal(byId.technical, '技术');
  assert.equal(byId.system_design, '系统设计');
  assert.equal(byId.other, '其他');
});

test('there are types for work that is not engineering', () => {
  const byId = Object.fromEntries(QUESTION_TYPES.map((t) => [t.id, t.label]));
  assert.equal(byId.case, '案例/情景');
  assert.equal(byId.domain, '专业技能');
});

test('"other" stays last, so the list reads from specific to general', () => {
  assert.equal(QUESTION_TYPES[QUESTION_TYPES.length - 1].id, 'other');
});

test('ids are unique', () => {
  const ids = QUESTION_TYPES.map((t) => t.id);
  assert.equal(new Set(ids).size, ids.length);
});

test('a type a newer server sends is shown as itself, not as nothing', () => {
  assert.equal(questionTypeLabel('behavioral'), '行为/STAR');
  assert.equal(questionTypeLabel('case'), '案例/情景');
  assert.equal(questionTypeLabel('something_new'), 'something_new');
});
