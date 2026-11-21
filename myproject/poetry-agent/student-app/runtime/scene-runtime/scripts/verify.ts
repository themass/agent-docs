/**
 * Runnable proof that the kernel obeys the product rules — no test framework, one command:
 *   node scripts/verify.ts
 * Each check maps to a rule in docs/specs/2026-11-06-qijing-script-dsl.md §7 or a mobile-readiness
 * discipline in 2026-11-06-frontend-and-mobile-strategy.md §4.
 */
import { readFileSync } from 'node:fs';
import { SceneMachine } from '../src/machine.ts';
import { resolve, ceiling, DEFAULT_BUDGET } from '../src/degrade.ts';
import { plan, QUOTA_BYTES } from '../src/offline.ts';
import type { SceneBundle } from '../src/bundle.ts';

const bundle = JSON.parse(readFileSync(new URL('../../contracts/sample.chun-wang.json', import.meta.url), 'utf8')) as SceneBundle;
let pass = 0, fail = 0;
const check = (name: string, ok: boolean, detail = '') => {
  if (ok) { pass++; console.log(`  ok   ${name}${detail ? ` — ${detail}` : ''}`); }
  else { fail++; console.log(`  FAIL ${name}${detail ? ` — ${detail}` : ''}`); }
};

console.log('\n[1] five-step machine is free movement, not a funnel');
const m = new SceneMachine(bundle);
check('starts at 读', m.snapshot.current === 'read');
m.enter('ready');
m.step('recite');                                   // straight to 诵 without touching the rest
check('jumps straight to 诵', m.snapshot.current === 'recite');
m.back();
check('back returns to the step actually visited before 诵 (读), not the index neighbour (诵→读)',
      m.snapshot.current === 'read', m.snapshot.visited.join('>'));
m.next();
check('next from 读 enters 到', m.snapshot.current === 'arrive');
m.step('meet'); m.step('arrive');
check('can revisit 到 after 见', m.snapshot.current === 'arrive');
check('nothing is scored', !('score' in m.snapshot) && !('grade' in m.snapshot));
check('coverage notice comes from the bundle', m.coverageNotice().includes('未覆盖'));

console.log('\n[2] degradation always lands on text');
const hi = resolve('a-dufu-bust', bundle.assets, { ...DEFAULT_BUDGET });
check('capable device keeps the L3 character', hi.level === 'L3', `got ${hi.level}`);
const weak = resolve('a-dufu-bust', bundle.assets, { weakNetwork: true });
check('weak network degrades the character to a still', weak.level === 'L1' && weak.degraded, `chain ${weak.chain.join(' > ')}`);
const forced = resolve('a-recite-demo', bundle.assets, { forceLevel: 'L0' });
check('media switched off → subtitle/text still there', forced.level === 'L0', `resolved ${forced.assetId}`);
check('ceiling(weakNetwork)=L1', ceiling({ weakNetwork: true }) === 'L1');
check('ceiling(reducedMotion)=L2', ceiling({ reducedMotion: true }) === 'L2');

console.log('\n[3] offline prefetch respects the scene byte budget, floor first');
const p = plan({ bundle_hash: 'x', script_id: 's', script_version: 'v', schema_version: '1.0',
  text_version_id: 't', asset_hashes: {}, coverage_notice: '', compiled_at: '', compiled_by: '',
  total_bytes: 0 },
  Object.fromEntries(Object.entries(bundle.assets).map(([k, a]) => [k, { ...a, bytes: 3 * 1024 * 1024 }])),
  { weakNetwork: true, maxBytesForScene: 8 * 1024 * 1024 });
check('downloads only what fits 8MB', p.totalBytes <= 8 * 1024 * 1024, `${(p.totalBytes / 1048576).toFixed(1)}MB, skipped ${p.skipped.length}`);
check('picks L0/L1 before L3', p.download.every(d => ['L0', 'L1'].includes(bundle.assets[d.assetId].level)));
check('device quota is 300MB', QUOTA_BYTES === 300 * 1024 * 1024);

console.log(`\n${fail === 0 ? 'PASS' : 'FAIL'}  ${pass} checks passed, ${fail} failed`);
process.exit(fail === 0 ? 0 : 1);
