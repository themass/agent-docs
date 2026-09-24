import assert from 'node:assert/strict'
import { readFileSync, readdirSync } from 'node:fs'
import { join } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = join(fileURLToPath(new URL('..', import.meta.url)))

function walk(dir, out = []) {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) {
      if (entry.name === 'node_modules' || entry.name === 'dist') continue
      walk(path, out)
    } else if (entry.name.endsWith('.ts') || entry.name.endsWith('.tsx')) {
      out.push(path)
    }
  }
  return out
}

const extensionFiles = walk(join(root, 'apps/extension/src'))
const runAgentHits = extensionFiles.filter((file) => {
  if (file.endsWith('run-supervisor.ts')) return false
  const text = readFileSync(file, 'utf8')
  return /\brunAgent\s*\(/.test(text) || /import\s*\{[^}]*\brunAgent\b/.test(text)
})

assert.equal(
  runAgentHits.length,
  0,
  `extension must not call runAgent directly (use RunSupervisor):\n${runAgentHits.join('\n')}`
)

const agentPath = join(root, 'packages/runtime/src/agent.ts')
const agentSource = readFileSync(agentPath, 'utf8')
assert.match(agentSource, /pipeline\.runTaskPreflight\(/, 'agent loop must delegate preflight to hook pipeline')
assert.match(agentSource, /runModelTurns\(/, 'agent loop must delegate model turns to model-turns')
assert.doesNotMatch(
  agentSource,
  /if \(isPageReadTask\(ctx\.task\)/,
  'page-read preflight must live in PreflightHook, not agent.ts'
)

console.log('architecture boundary check ok')
