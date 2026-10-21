const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const path = require('node:path');
const ts = require('typescript');
const React = require('react');
const { renderToStaticMarkup } = require('react-dom/server');

// Use the project's existing TypeScript compiler: no additional test dependency.
const source = fs.readFileSync(path.join(__dirname, '../lib/agent-ui-kit/conversation/RichText.tsx'), 'utf8');
const code = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2017, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX },
}).outputText;
const mod = { exports: {} };
new Function('require', 'module', 'exports', code)(require, mod, mod.exports);
const render = (text) => renderToStaticMarkup(React.createElement(mod.exports.RichText, { text }));

test('formats headings, paragraphs, bold and inline code', () => {
  const html = render('## 修改建议\n\n**负责范围**：`订单服务`\n补充交付动作。\n\n确认后保存。');
  assert.match(html, /<h3[^>]*>修改建议<\/h3>/);
  assert.match(html, /<strong[^>]*>负责范围<\/strong>/);
  assert.match(html, /<code[^>]*>订单服务<\/code>/);
  assert.equal((html.match(/<p>/g) || []).length, 2);
  assert.match(html, /<br\/>/);
});

test('recovers flat numbered suggestions without rewriting decimal metrics', () => {
  const html = render('建议：1. FR 提升 1.5 个百分点。 2. 保留 2022.07 的时间。 3. 待补充事实。');
  assert.equal((html.match(/<li>/g) || []).length, 3);
  assert.match(html, /1\.5/);
  assert.match(html, /2022\.07/);
  assert.equal((render('FR 提升 1.5 个百分点。').match(/<ol/g) || []).length, 0);
});

test('blank paragraphs separate lists and preserve their starting number', () => {
  const html = render('1. 第一条\n2. 第二条\n\n补充说明。\n\n3. 第三条');
  assert.equal((html.match(/<ol /g) || []).length, 2);
  assert.match(html, /start="3"/);
});

test('code fences keep numbered text literal, including an unfinished stream', () => {
  const html = render('```text\n1. 不应成为列表\n2. 保持原样');
  assert.match(html, /<pre[^>]*><code>1\. 不应成为列表\n2\. 保持原样<\/code><\/pre>/);
  assert.doesNotMatch(html, /<ol/);
});

test('untrusted HTML is text, never executable markup', () => {
  const html = render('**注意** <script>alert(1)</script> <img src=x onerror=alert(1)>');
  assert.doesNotMatch(html, /<script|<img/);
  assert.match(html, /&lt;script&gt;/);
});
