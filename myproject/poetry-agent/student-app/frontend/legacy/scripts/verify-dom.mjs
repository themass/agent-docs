#!/usr/bin/env node
/**
 * Loads the real browser entry (src/app.js) under a minimal DOM shim. No jsdom dependency: the
 * point is not to render pixels, it is to prove the ids, module graph and event wiring do not throw
 * and that student mode refuses to render a draft bundle.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { join } from 'node:path';

const root = decodeURIComponent(new URL('..', import.meta.url).pathname);
const src = readFileSync(join(root, 'src/app.js'), 'utf8').replace("'/src/scene.js'", "'./scene.js'");
writeFileSync(join(root, 'src', '.app-under-test.mjs'), src);

const nodes = new Map();
const mkNode = (tag = 'div') => ({ tag, children: [], text: '', className: '', hidden: false, disabled: false,
  tabIndex: 0, attrs: {}, style: {}, set textContent(v) { this.text = v; }, get textContent() { return this.text; },
  appendChild(c) { this.children.push(c); return c; }, replaceChildren(...c) { this.children = c; },
  setAttribute(k, v) { this.attrs[k] = v; }, addEventListener(t, cb) { (this.handlers ??= {})[t] = cb; } });
for (const id of ['work', 'coverage', 'unknown', 'src', 'stage', 'step-body', 'lines', 'gate', 'gate-detail',
                  'degraded', 'level-tag', 'media-off', 'back']) nodes.set(id, mkNode());
const stepButtons = ['read', 'arrive', 'meet', 'return', 'recite'].map(s => { const n = mkNode('button'); n.dataset = { step: s }; return n; });
globalThis.document = {
  getElementById: id => nodes.get(id) ?? null,
  createElement: tag => mkNode(tag),
  querySelectorAll: sel => (sel === '.rail .step' ? stepButtons : sel === '.rail button' ? stepButtons : []),
};
globalThis.location = { search: process.argv.includes('--preview') ? '?preview' : '' };
globalThis.fetch = async (path) => {
  const file = join(root, path.replace(/^\//, ''));
  return { ok: true, json: async () => JSON.parse(readFileSync(file, 'utf8')) };
};

let pass = 0, fail = 0;
const check = (name, ok, detail = '') => { if (ok) { pass++; console.log(`  ok   ${name}${detail ? ` — ${detail}` : ''}`); } else { fail++; console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`); } };

await import(join(root, 'src/.app-under-test.mjs'));

console.log('\n[1] the page assembled without throwing');
const wantLines = process.argv.includes('--preview') ? 8 : 0;
check(`line list matches the mode (${wantLines})`, nodes.get('lines').children.length === wantLines,
      `${nodes.get('lines').children.length} lines`);
check('coverage notice on screen', nodes.get('coverage').text.startsWith('覆盖声明：'));
check('uncertain dates on screen', nodes.get('unknown').text.includes('两说'));
check('data source line names the version', nodes.get('src').text.includes('text-chun-wang-draft'), nodes.get('src').text);

console.log('\n[2]', process.argv.includes('--preview') ? 'preview mode renders draft content' : 'student mode refuses a draft bundle');
if (process.argv.includes('--preview')) {
  check('draft banner shown', nodes.get('gate').hidden === false);
  check('banner says what is unpublished', nodes.get('gate-detail').text.startsWith('未发布：'), nodes.get('gate-detail').text);
  check('读 step renders the poem plus a hint and no invented layer cards',
        nodes.get('step-body').children.length === 1, `${nodes.get('step-body').children.length} blocks`);
  check('level tag filled', nodes.get('level-tag').text.startsWith('当前'));
  const arrive = stepButtons.find(b => b.dataset.step === 'arrive');
  arrive.handlers.click();
  check('clicking 到 renders the four situation layers', nodes.get('step-body').children.length === 4,
    `${nodes.get('step-body').children.length} layers`);
  const recite = stepButtons.find(b => b.dataset.step === 'recite');
  recite.handlers.click();
  check('jumping to 诵 works', nodes.get('step-body').children.length >= 1);
  nodes.get('back').handlers.click();
  check('back works from the page', nodes.get('level-tag').text.length > 0);
  const toggle = nodes.get('media-off');
  toggle.checked = true; toggle.handlers.change({ target: { checked: true } });
  check('turning media off re-renders with the same words', nodes.get('lines').children.length === 8);
} else {
  check('student mode shows the refusal instead of content',
    nodes.get('stage').children.some(c => (c.text || '').includes('还没有发布')), JSON.stringify(nodes.get('stage').children.map(c => c.text)));
  check('navigation disabled in student mode', stepButtons.every(b => b.disabled === true));
}

console.log(`\n${fail === 0 ? 'PASS' : 'FAIL'}  ${pass} checks, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
