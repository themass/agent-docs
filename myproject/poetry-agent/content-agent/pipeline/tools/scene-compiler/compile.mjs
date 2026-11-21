#!/usr/bin/env node
/**
 * The scene compiler: script + base facts -> an immutable, content-addressed bundle.
 *
 * This is the only path from the base to a student's device. A page can never assemble a scene from
 * base records; a bundle exists only if the 12 rules passed, and its identity is the hash of its
 * contents, so offline caching, gray release and rollback all hang off one number.
 *
 *   node compile.mjs --script ../contracts/sample.chun-wang.json --facts ../contracts/facts.chun-wang.json
 *   (--check-only prints the verdict without writing anything)
 */
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { createHash } from 'node:crypto';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { checkRules } from '../scene-validator/rules.mjs';
// Single physical copy of the kernel lives in student-app/runtime/scene-runtime (architecture rule A6).
// The former content-agent/pipeline/scene-runtime was a byte-identical duplicate that could only drift.
import { resolve as pickAsset, ORDER } from '../../../../student-app/runtime/scene-runtime/src/degrade.ts';

const argv = process.argv.slice(2);
const opt = (name, dflt) => { const i = argv.indexOf('--' + name); return i >= 0 ? argv[i + 1] : dflt; };
const here = dirname(fileURLToPath(import.meta.url));
const scriptPath = resolve(opt('script', join(here, '../../contracts/sample.chun-wang.json')));
const factsPath = opt('facts') ? resolve(opt('facts')) : null;
const outDir = resolve(opt('out', join(here, '../../dist/bundles')));
const compiledBy = opt('compiled-by', 'local');
const checkOnly = argv.includes('--check-only');

const script = JSON.parse(readFileSync(scriptPath, 'utf8'));
const facts = factsPath ? JSON.parse(readFileSync(factsPath, 'utf8')) : null;
const verdict = checkRules(script, facts);

/* Without base facts six rules cannot run (R1 R2 R6 R7 R8 R11). A bundle built on that gap must not exist,
 * so there is no override flag: the caller has to supply --facts from the real base. */
if (!facts) {
  console.log(JSON.stringify({ verdict: 'BLOCKED', reason: 'no --facts: reference rules (R1 R2 R6 R7 R8 R11) cannot run — nothing was written',
    rules_skipped: verdict.skipped, warnings: verdict.warnings }, null, 2));
  process.exit(1);
}

if (verdict.failures.length) {
  console.log(JSON.stringify({ verdict: 'BLOCKED', reason: 'rules failed — nothing was written',
    failures: verdict.failures, warnings: verdict.warnings }, null, 2));
  process.exit(1);
}

/* Assets are pre-resolved for every device ceiling, so the client never invents its own degradation. */
const assets = script.assets || {};
const ceilings = ['L0', 'L1', 'L2', 'L3', 'L4'];
const levelPlans = {};
for (const c of ceilings) {
  const budget = { forceLevel: c };
  const chosen = Object.keys(assets).map(id => {
    const r = pickAsset(id, assets, budget);
    return { assetId: id, serves: r.assetId, level: r.level, degraded: r.degraded, chain: r.chain };
  });
  levelPlans[c] = { chosen, distinct: [...new Set(chosen.map(x => x.serves))].sort(),
                    degraded: chosen.filter(x => x.degraded).length };
}

/* Deterministic serialization: stable key order means the same inputs always give the same hash. */
const canonical = value => {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
  return JSON.stringify(value);
};
const bundle = { ...script, build: { level_plans: levelPlans } };
const bundleText = canonical(bundle);
const bundleHash = createHash('sha256').update(bundleText).digest('hex');

const compiledAt = opt('as-of', new Date().toISOString());
const manifest = {
  bundle_hash: bundleHash,
  schema_version: script.schema_version,
  script_id: script.script_id,
  script_version: script.script_version,
  work_id: script.work_id,
  text_version_id: script.text_version_id,
  asset_hashes: Object.fromEntries(Object.entries(assets).sort().map(([id, a]) => [id, a.hash])),
  coverage_notice: script.coverage_notice,
  unknown_dates_notice: script.unknown_dates_notice || null,
  facts_source: facts.generated_by || 'database',
  levels: ceilings,
  compiled_at: compiledAt,
  compiled_by: compiledBy,
  rules_passed: verdict.executed.filter(id => id !== 'R0').length, // R1–R12 are the 12 numbered rules; R0 is the shape preflight
  rules_executed: verdict.executed,
  rules_skipped: verdict.skipped,
};

if (checkOnly) {
  console.log(JSON.stringify({ verdict: 'COMPILES', bundle_hash: bundleHash, facts_source: manifest.facts_source,
    levels: ceilings.map(c => `${c}:${levelPlans[c].distinct.length} assets/${levelPlans[c].degraded} degraded`), warnings: verdict.warnings }, null, 2));
  process.exit(0);
}

const target = join(outDir, bundleHash.slice(0, 32));
mkdirSync(target, { recursive: true });
writeFileSync(join(target, 'bundle.json'), JSON.stringify(bundle, null, 2) + '\n');
writeFileSync(join(target, 'manifest.json'), JSON.stringify(manifest, null, 2) + '\n');
const indexFile = join(outDir, 'index.json');
const index = (() => { try { return JSON.parse(readFileSync(indexFile, 'utf8')); } catch { return { builds: [] }; } })();
index.builds = [{ hash: bundleHash, script: `${manifest.script_id}@${manifest.script_version}`,
                  facts_source: manifest.facts_source, compiled_at: compiledAt, compiled_by: compiledBy },
                ...index.builds.filter(b => b.hash !== bundleHash)];
writeFileSync(indexFile, JSON.stringify(index, null, 2) + '\n');
console.log(JSON.stringify({ verdict: 'EMITTED', bundle_hash: bundleHash, dir: target,
  facts_source: manifest.facts_source, levels: ceilings.map(c => `${c}:${levelPlans[c].distinct.length}`), warnings: verdict.warnings }, null, 2));
