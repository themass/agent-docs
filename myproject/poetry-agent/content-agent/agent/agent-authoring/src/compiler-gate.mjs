import { existsSync } from 'node:fs';
import { execFileSync } from 'node:child_process';

export function compileGate({ bundlePath, factsPath }) {
  if (!bundlePath || !factsPath) return { verdict: 'NOT_RUN', failures: ['bundle_or_facts_not_provided'] };
  if (!existsSync(bundlePath) || !existsSync(factsPath)) return { verdict: 'BLOCKED', failures: ['bundle_or_facts_missing'] };
  try {
    const output = execFileSync('node', ['/Users/gqli/work/xuexi/poetry-agent-platform/content-agent/pipeline/tools/scene-validator/validate.mjs', bundlePath, '--facts', factsPath], { encoding: 'utf8' });
    return { verdict: output.includes('BLOCKED') ? 'BLOCKED' : 'COMPILES', failures: output.includes('BLOCKED') ? [output.trim()] : [] };
  } catch (error) {
    return { verdict: 'BLOCKED', failures: [String(error.stdout || error.message).trim()] };
  }
}
