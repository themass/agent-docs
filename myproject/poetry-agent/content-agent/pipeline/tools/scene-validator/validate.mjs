#!/usr/bin/env node
/**
 * CLI for the 12 compile rules. A bundle that passes is allowed to reach the CDN; one that fails
 * cannot ship at all. Facts come from the real base via facts-from-db.sh; without --facts the
 * reference rules report as SKIPPED, never as passed.
 *   node validate.mjs <bundle.json> [--facts facts.json]
 */
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { checkRules } from './rules.mjs';

const args = process.argv.slice(2);
const bundlePath = args.find(a => !a.startsWith('--'));
const factsIdx = args.indexOf('--facts');
if (!bundlePath) { console.error('usage: node validate.mjs <bundle.json> [--facts facts.json]'); process.exit(2); }
const bundle = JSON.parse(readFileSync(resolve(bundlePath), 'utf8'));
const facts = factsIdx >= 0 ? JSON.parse(readFileSync(resolve(args[factsIdx + 1]), 'utf8')) : null;
const r = checkRules(bundle, facts);
/* No facts means six rules never ran. That is not a pass, so it is not reported as one. */
const verdict = r.failures.length ? 'BLOCKED' : (facts ? 'COMPILES' : 'BLOCKED');
const report = {
  bundle: `${bundle.script_id}@${bundle.script_version}`,
  facts: facts ? 'from base' : 'ABSENT — reference rules not run',
  rules_executed: r.executed,
  rules_skipped: r.skipped,
  warnings: r.warnings, failures: r.failures,
  verdict,
  ...(verdict === 'BLOCKED' && !facts && !r.failures.length ? { reason: 'no --facts: cannot verify reference rules' } : {}),
};
console.log(JSON.stringify(report, null, 2));
process.exit(verdict === 'COMPILES' ? 0 : 1);
