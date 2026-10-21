const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');
const source = fs.readFileSync(path.join(__dirname, '../components/job/RequirementEvidenceList.tsx'), 'utf8');
const code = ts.transpileModule(source, { compilerOptions: {
  target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX,
}}).outputText;
const mod = { exports: {} };
new Function('exports', 'require', code)(mod.exports, require);
const render = (items, profileVersion) => renderToStaticMarkup(React.createElement(
  mod.exports.RequirementEvidenceList, { items, profileVersion },
));
test('old reports without evidence do not show invented rows', () => {
  assert.equal(render([]), '');
});
test('unknown is not inability and details are collapsed by default', () => {
  const html = render([{ requirement: '团队管理', importance: 'unspecified',
    importance_basis: 'estimated', status: 'unverified', evidence: [],
    next_question: '请补充管理经历。' }], 7);
  assert.match(html, /第 7 版/);
  assert.match(html, /待补充依据/);
  assert.match(html, /不代表你没有这项能力/);
  assert.match(html, /<details/);
  assert.doesNotMatch(html, /<details[^>]*open/);
});
test('quotes are escaped, not rendered as HTML instructions', () => {
  const html = render([{ requirement: '研发', importance: 'required', importance_basis: 'jd_explicit',
    status: 'supported', evidence: [{ quote: '<script>bad()</script>', field_path: 'experiences[0]' }],
  }], 1);
  assert.match(html, /&lt;script&gt;/);
  assert.doesNotMatch(html, /<script>/);
  assert.match(html, /有相关依据/);
});
