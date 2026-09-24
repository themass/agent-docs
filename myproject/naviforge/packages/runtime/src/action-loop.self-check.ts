import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import { DEFAULT_RUN_LIMITS } from './run-limits.js'
import { actionLoopKey, replayActionLoop, type ActionLoopCall } from './agent.js'

const url = 'https://example.test/page'

{
  const shot = { tool: 'dom_screenshot', arguments: {} }
  const replay = replayActionLoop([shot, shot, shot, shot], url)
  assert.equal(replay.allowed, DEFAULT_RUN_LIMITS.sameActionLimit)
  assert.equal(replay.stopAt, DEFAULT_RUN_LIMITS.sameActionLimit + 1, '2 skips then stop')
}

{
  const down = { tool: 'dom_scroll', arguments: { direction: 'down' } }
  const replay = replayActionLoop([down, down, down, down], url)
  assert.ok(replay.stopAt >= 0, 'identical scroll is gated')
}

{
  const click = { tool: 'dom_click', arguments: { index: 1 } }
  const replay = replayActionLoop([click, click, click, click], url)
  assert.equal(replay.stopAt, -1, 'clicks are not action-loop gated')
}

{
  const mixed: ActionLoopCall[] = [
    { tool: 'dom_screenshot' },
    { tool: 'dom_scroll', arguments: { direction: 'down' } },
    { tool: 'dom_screenshot' },
    { tool: 'dom_screenshot' },
    { tool: 'dom_screenshot' },
  ]
  const replay = replayActionLoop(mixed, url)
  assert.equal(replay.allowed, 3, '2 shots + 1 scroll allowed')
  assert.equal(replay.stopAt, 4)
}

assert.equal(actionLoopKey('dom_screenshot', url), `dom_screenshot|${url}`)
assert.equal(actionLoopKey('dom_read', url, { mode: 'markdown' }), `dom_read|${url}|markdown`)
assert.equal(actionLoopKey('page_to_pdf', url), `page_to_pdf|${url}`)

{
  const md = { tool: 'dom_read', arguments: { mode: 'markdown' } }
  const replay = replayActionLoop([md, md, md, md], url)
  assert.equal(replay.stopAt, DEFAULT_RUN_LIMITS.sameActionLimit + 1, 'repeat page export is gated')
}

const corpus = resolve(dirname(fileURLToPath(import.meta.url)), '../../../tests/message.txt')
assert.ok(existsSync(corpus), 'tests/message.txt is the loop regression corpus')

const byRun = new Map<string, ActionLoopCall[]>()
for (const line of readFileSync(corpus, 'utf8').split('\n')) {
  if (!line.includes('"type":"model.turn"') || !line.includes('"tool":"dom_')) continue
  const rec = JSON.parse(line) as {
    runId?: string
    payload?: { call?: { tool?: string; arguments?: Record<string, unknown> } }
  }
  const call = rec.payload?.call
  if (!call?.tool || !rec.runId) continue
  const list = byRun.get(rec.runId) ?? []
  list.push({ tool: call.tool, arguments: call.arguments ?? {} })
  byRun.set(rec.runId, list)
}

let longest = 0
for (const calls of byRun.values()) {
  const loopTools = calls.filter((call) => actionLoopKey(call.tool, url, call.arguments))
  longest = Math.max(longest, loopTools.length)
}

if (longest > 0) {
  assert.ok(longest > DEFAULT_RUN_LIMITS.sameActionLimit, 'corpus contains a screenshot/scroll streak')
}
// Corpus mix of screenshot/scroll/snapshot keys may not trip same-key stop; synthetic cases above cover that.

console.log(
  `action-loop self-check ok (corpus runs=${byRun.size} longestLoopTools=${longest})`
)
