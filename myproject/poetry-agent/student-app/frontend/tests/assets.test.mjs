import test from 'node:test';
import assert from 'node:assert/strict';
import { createAssets, budgetFrom, modeOf } from '../src/data/assets.js';
import { validateManifest, isSafeSvg } from '../src/character/mount.js';
import { spoken } from '../src/ui/trust.js';
import { bundle, read } from './helpers.mjs';

const registry = new Map(read('../../production/published/registry.json').assets.map(a => [a.asset_id, { id: a.asset_id, kind: a.kind, level: a.level, uri: a.uri }]));
const make = o => createAssets({ assets: bundle().assets, registry, budget: () => budgetFrom(o), assetBase: '/published' });

test('assets: the registry uri is the address; kinds map to a drawing mode', () => {
  const r = make({}).resolve('a-changan-dusk');
  assert.equal(r.url, '/published/assets/a-changan-dusk/parallax.json');
  assert.equal(r.mode, 'parallax');
  assert.equal(modeOf({ kind: 'character', uri: 'characters/du-fu/manifest.json' }), 'character');
});

test('assets: media off, weak network and low memory all land on something showable or on text', () => {
  for (const o of [{ mediaOff: true }, { weak: true }, { lowMemory: true }, { reducedMotion: true }]) {
    for (const id of Object.keys(bundle().assets)) {
      const r = make(o).resolve(id);
      assert.ok(r.mode === 'text' || r.url, `${id} ${JSON.stringify(o)}`);
    }
  }
  const off = make({ mediaOff: true }).resolve('a-dufu-bust');
  assert.notEqual(off.mode, 'character');                                 // an animated character is never loaded with media off
});

test('assets: an id the bundle does not know is reported, never replaced by an unrelated floor asset', () => {
  const r = make({}).resolve('a-not-in-bundle');
  assert.equal(r.mode, 'text'); assert.equal(r.degraded, true); assert.equal(r.reason, 'missing');
});

test('character manifest: C\'s placeholder validates; non-dramatization depiction is refused; hostile svg is refused', () => {
  const m = read('../../production/published/characters/du-fu/manifest.json');
  assert.equal(validateManifest(m), null);
  assert.match(validateManifest({ ...m, depiction: { declared_as: 'FACT' } }), /DRAMATIZATION/);
  assert.equal(isSafeSvg('<svg><path d="M0 0"/></svg>'), true);
  for (const bad of ['<svg><script>x</script></svg>', '<svg onload="x()"></svg>', '<svg><a href="https://evil/x"/></svg>', '<svg><foreignObject/></svg>'])
    assert.equal(isSafeSvg(bad), false, bad);
});

test('trust: an unbadged dramatization is not rendered at all', () => {
  assert.equal(spoken({ text: '我的白发却短得几乎插不住簪子', kind: 'DRAMATIZATION' }), null);
});
