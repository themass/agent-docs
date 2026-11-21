/**
 * The compiled test-fixture bundle (content-agent/pipeline/dist/bundles/a1a919c2…) against C's real registry and files.
 * Skipped when the bundle has not been compiled (python3 scripts/maintenance/build_fixture_bundle.py).
 * Covers the three paths the fixture exists for: normal L1/L2, asset missing -> text, reduced motion.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { createAssets, budgetFrom } from '../src/data/assets.js';
import { indexBundle } from '../src/data/facts.js';

const path = rel => fileURLToPath(new URL(rel, import.meta.url));
const BUNDLE = path('../../../content-agent/pipeline/dist/bundles/a1a919c215d656000910a72ef2d01f8a/bundle.json');
const PUB = path('../../production/published/');
const skip = !existsSync(BUNDLE);
const bundle = skip ? null : JSON.parse(readFileSync(BUNDLE, 'utf8'));
const rows = skip ? [] : JSON.parse(readFileSync(PUB + 'registry.json', 'utf8')).assets;
const registry = new Map(rows.map(a => [a.asset_id, { id: a.asset_id, kind: a.kind, level: a.level, uri: a.uri }]));
const make = o => createAssets({ assets: bundle.assets, registry, budget: () => budgetFrom(o), assetBase: '/published' });

test('fixture: every registered file exists and matches its SHA-256', { skip }, () => {
  for (const a of rows) for (const f of a.files) {
    assert.ok(existsSync(PUB + f.path), f.path);
    assert.equal(createHash('sha256').update(readFileSync(PUB + f.path)).digest('hex'), f.sha256, f.path);
  }
});

test('fixture: normal budget loads the animated character, the parallax scene and the audio as asked', { skip }, () => {
  const a = make({});
  assert.equal(a.resolve('a-dufu-bust').mode, 'character');
  assert.equal(a.resolve('a-changan-dusk').mode, 'parallax');
  assert.equal(a.resolve('a-recite-demo').mode, 'audio');
  assert.equal(a.resolve('a-dufu-bust').degraded, false);
});

test('fixture: reduced motion and weak network swap the character for its still picture', { skip }, () => {
  for (const o of [{ reducedMotion: true }, { weak: true }, { lowMemory: true }]) {
    const r = make(o).resolve('a-dufu-bust');
    assert.equal(r.assetId, 'a-dufu-still'); assert.equal(r.mode, 'image'); assert.equal(r.degraded, true);
  }
  assert.equal(make({ weak: true }).resolve('a-recite-demo').mode, 'text');      // audio above the L1 ceiling -> captions
});

test('fixture: a character that fails to load drops to the still picture, then to text', { skip }, () => {
  const a = make({});
  assert.equal(a.resolve('a-dufu-bust', { forceLevel: 'L1' }).assetId, 'a-dufu-still');
  const floor = a.resolve('a-dufu-bust', { forceLevel: 'L0' });
  assert.equal(floor.mode, 'text');
});

test('fixture: media off puts every asset on text; no budget leaves an asset with nothing to show', { skip }, () => {
  for (const id of Object.keys(bundle.assets)) assert.equal(make({ mediaOff: true }).resolve(id).mode, 'text', id);
  for (const o of [{}, { reducedMotion: true }, { weak: true }, { lowMemory: true }, { mediaOff: true }])
    for (const id of Object.keys(bundle.assets)) { const r = make(o).resolve(id); assert.ok(r.mode === 'text' || r.url, id); }
});

test('fixture: spoken lines are the same ones the agent numbers (arrive/WORLD/0, meet/PERSON/0 …)', { skip }, () => {
  const idx = indexBundle(bundle);
  for (const id of ['arrive/SCENE/0', 'arrive/CITY/0', 'arrive/WORLD/0', 'arrive/PERSON/0', 'meet/PERSON/0', 'return/WORLD/0', 'return/PERSON/0'])
    assert.ok(idx.facts.has(id), id);
  assert.equal(idx.facts.get('meet/PERSON/0').kind, 'DRAMATIZATION');
});
