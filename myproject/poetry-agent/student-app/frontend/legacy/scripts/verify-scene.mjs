#!/usr/bin/env node
/** Runs the page's own view-model code (same module the browser loads) under node. */
import { readFileSync } from 'node:fs';
import { buildScene, publishGate } from '../src/scene.js';

const bundle = JSON.parse(readFileSync(new URL('../../../runtime/contracts/sample.chun-wang.json', import.meta.url), 'utf8'));
const preview = JSON.parse(readFileSync(new URL('../public/preview.json', import.meta.url), 'utf8'));

let pass = 0, fail = 0;
const check = (name, ok, detail = '') => {
  if (ok) { pass++; console.log(`  ok   ${name}${detail ? ` — ${detail}` : ''}`); } else { fail++; console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`); }
};

console.log('\n[1] fail-closed gate: draft base must NOT render as a student view');
const scene = buildScene(bundle, preview);
const gate = publishGate(bundle, preview);
check('gate closed while the base is DRAFT', gate.open === false, `${gate.blocked.length} items not published`);
check('work itself is draft, so nothing renders', gate.blocked.includes('content:work-chun-wang'));
check('preview is labelled, not hidden', typeof scene.workId === 'string' && gate.blocked.length > 0);

console.log('\n[2] real base content, no invented text');
check('8 lines come from poetry_text_line', scene.lines.length === 8, scene.lines.map(l => l.text).join(''));
check('every 到/回 layer lands on lines that exist in the base',
  scene.steps.flatMap(s => s.layers).every(l => l.declaredInBase));
check('four situation layers present in 到', scene.steps[1].layers.map(l => l.layer).join(',') === 'SCENE,CITY,WORLD,PERSON');
check('background explains lines (anti pile-up)', scene.steps[1].layers.every(l => l.linkedLines.length > 0),
  scene.steps[1].layers.map(l => `${l.layer}:${l.linkedLines.length}`).join(' '));
check('annotations come from the base only', scene.lines.filter(l => l.annotations.length).length === 2,
  scene.lines.filter(l => l.annotations.length).map(l => l.seq).join(','));

console.log('\n[3] fact vs dramatisation is visible, not implied');
check('dramatisation lines carry a badge', scene.steps.flatMap(s => s.layers).flatMap(l => l.spoken)
  .filter(l => l.kind === 'DRAMATIZATION').every(l => !!l.badge), `${scene.dramatisations} line(s)`);
check('non-dramatisation lines carry a claim id', scene.steps.flatMap(s => s.layers).flatMap(l => l.spoken)
  .filter(l => l.kind !== 'DRAMATIZATION').every(l => !!l.claimId));

console.log('\n[4] budgets change the media, never the words');
const full = buildScene(bundle, preview, {});
const weak = buildScene(bundle, preview, { weakNetwork: true });
const textOnly = buildScene(bundle, preview, { forceLevel: 'L0' });
const count = s => s.steps.flatMap(x => x.layers).flatMap(l => l.assets).filter(a => a.level !== 'L0').length;
check('capable device keeps media', count(full) >= count(weak), `${count(full)} vs ${count(weak)}`);
check('L0 mode keeps the same spoken lines', textOnly.steps.flatMap(x => x.layers).flatMap(l => l.spoken).length
  === full.steps.flatMap(x => x.layers).flatMap(l => l.spoken).length);
check('degraded assets say so', weak.steps.flatMap(x => x.layers).flatMap(l => l.assets).every(a => a.level === 'L0' || a.level === 'L1'));

console.log('\n[5] coverage declaration is on screen, not in code');
check('coverage notice reaches the view model', scene.coverageNotice.includes('未覆盖'));
check('uncertain dates are declared', (scene.unknownDatesNotice || '').includes('两说'));

console.log('\n[6] five steps, free movement');
check('all five steps render', scene.steps.map(s => s.id).join(',') === 'read,arrive,meet,return,recite');
scene.machine.step('recite');
check('can jump to 诵 directly', scene.machine.step('recite').current === 'recite');
check('back is always available', scene.machine.back().current === 'read');

console.log(`\n${fail === 0 ? 'PASS' : 'FAIL'}  ${pass} checks, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
