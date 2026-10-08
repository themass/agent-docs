/**
 * Phase A/B acceptance for tests/message.txt golden task (static simulation + hook probes).
 */
import assert from 'node:assert/strict'
import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane'

import { Agent, AgentCtx } from './agent-ctx.js'
import {
  ScriptDeliverableStepHook,
  ScriptLoginNavigateHook,
  TaskHintHook,
} from './builtin-hooks.js'
import {
  deliverableGuidanceNotes,
  resolveDeliverable,
  shouldEmitSiteCatalogGuidance,
  shouldRunCatalogPreflight,
  shouldRunMediaRecipe,
} from './deliverable.js'
import { createAgentGates } from './loop-gate-state.js'
import { classifyPageState } from './page-state.js'
import { intentGuidanceNotes, resolveTaskIntent } from './task-intent.js'
import { parallelSubtaskGuidanceNotes, taskGuidanceNotes } from './task-classifier.js'

const SAMPLE =
  '分析这个网站的 视频列表，给我生成一个python 脚本，抓取每个分类下的第一页。\n页码可以定义多少页，默认值为1'

const OLD_TRACE_BAD = [
  'GUIDANCE: intent=media —',
  'PREFLIGHT: site recipe media-extract-default',
  'PREFLIGHT: intent=media_extract skill media-extract',
  'PREFLIGHT: skill catalog-crawl-sop',
  'PREFLIGHT: catalog strategy=full-catalog',
] as const

function simulatePreflightNotes(task: string): string[] {
  const deliverable = resolveDeliverable(task)
  const intent = resolveTaskIntent(task)
  const notes: string[] = []
  notes.push(...deliverableGuidanceNotes(deliverable))
  if (deliverable === 'general') {
    notes.push(...intentGuidanceNotes(intent))
  }
  if (shouldRunMediaRecipe(deliverable, intent)) {
    notes.push('PREFLIGHT: site recipe media-extract-default — (would run)')
  }
  notes.push(`PREFLIGHT: deliverable=${deliverable} skill persist`)
  if (shouldEmitSiteCatalogGuidance(task, deliverable)) {
    notes.push('PREFLIGHT: skill catalog-crawl-sop (site catalog SOP)')
  }
  if (shouldRunCatalogPreflight(task, deliverable)) {
    notes.push('PREFLIGHT: catalog strategy=full-catalog')
  }
  notes.push(...taskGuidanceNotes(task, 'fresh'))
  notes.push(...parallelSubtaskGuidanceNotes(task))
  return notes
}

const simulated = simulatePreflightNotes(SAMPLE)

console.log('=== Phase A/B analysis (message.txt golden task) ===\n')
console.log(`deliverable=${resolveDeliverable(SAMPLE)} intent=${resolveTaskIntent(SAMPLE)}\n`)

console.log('| Old trace (must NOT repeat) | New preflight simulation |')
console.log('|-------------------------------|---------------------------|')
for (const bad of OLD_TRACE_BAD) {
  const still = simulated.some((n) => n.includes(bad))
  const newHas = still ? '⚠ still present' : '✓ absent'
  console.log(`| ${bad.slice(0, 42)}… | ${newHas} |`)
}

console.log('\nExpected NEW signals:')
const mustHave = [
  'deliverable=script',
  'PLAN:',
  'persist',
  '禁止 media_extract recipe',
]
for (const token of mustHave) {
  const hit = simulated.some((n) => n.includes(token))
  console.log(`  ${hit ? '✓' : '✗'} ${token}`)
  assert.ok(hit, `missing expected note token: ${token}`)
}

assert.ok(!simulated.some((n) => n.includes('intent=media —')))
assert.ok(!simulated.some((n) => n.includes('PREFLIGHT: intent=media_extract skill')))
assert.ok(!simulated.some((n) => n.includes('media-extract-default')))
assert.ok(!simulated.some((n) => n.includes('PREFLIGHT: skill catalog-crawl-sop')))
assert.ok(!simulated.some((n) => n.includes('PREFLIGHT: catalog strategy=full-catalog')))

assert.equal(shouldRunCatalogPreflight(SAMPLE, 'script'), false)
assert.equal(shouldRunMediaRecipe('script', 'script_authoring'), false)
assert.equal(parallelSubtaskGuidanceNotes(SAMPLE).length, 0)
assert.equal(taskGuidanceNotes(SAMPLE, 'fresh').length, 0)

{
  const loginSnap: DomSnapshot = {
    revision: 1,
    url: 'https://example.test/login',
    title: 'Login',
    header: '登录',
    content: '请输入密码 Sign in',
    footer: '',
  }
  const role = classifyPageState({
    url: loginSnap.url,
    title: loginSnap.title,
    login: true,
    blocking: true,
    items: [],
  })
  assert.equal(role.role, 'login')

  const agent = new Agent({
    task: SAMPLE,
    llm: { baseURL: 'http://x', apiKey: 'x', model: 'x' },
    dom: { snapshot: async () => ({ ok: true, data: loginSnap }) } as DomPlane,
  })
  const ctx = new AgentCtx(agent, loginSnap)
  ctx.gates = createAgentGates(3)
  ctx.gates.deliverable = 'script'
  ctx.gates.taskIntent = 'script_authoring'
  ctx.pageState = role

  const stepHook = new ScriptDeliverableStepHook()
  const ask = stepHook.beforeStep(ctx)
  assert.equal(ask.kind, 'ask_user')
  assert.ok(ctx.gates.scriptLoginAskIssued)

  const navHook = new ScriptLoginNavigateHook()
  ctx.toolCall = { tool: 'dom_navigate', arguments: { url: 'https://example.test/home' } }
  const skip = navHook.beforeTool(ctx)
  assert.equal(skip.kind, 'skip_tool')

  const hint = new TaskHintHook()
  ctx.gates.taskHintIssued = false
  const hintOut = hint.beforeStep(ctx)
  assert.equal(hintOut.kind, 'continue')
}

console.log('\npreflight-phase-ab self-check ok')
