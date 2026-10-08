import {
  NAV_ITEMS,
  describeSystem,
  nextCopyTitle,
  isEmbeddedSurface,
  parseImportedSkill,
  sectionFromHash,
  SESSION_NAV_ITEM,
  trimActivities,
} from './model'
import { redactSessionText } from '../../lib/session-model'
import type { TraceRecord } from '@naviforge/session'
import { BUILTIN_TOOL_CATALOG } from '../../lib/builtin-tools'
import { buildThreadContext, createThread } from '../../lib/thread-model'
import {
  EMPTY_THREAD_MEMORY,
  formatThreadMemory,
  mergeThreadMemory,
  parseThreadMemoryJson,
  shouldCompactThread,
  threadMemoryPressure,
} from '@naviforge/session'
import {
  addModelProfile,
  getActiveModelProfile,
  migrateLegacyLlmSettings,
  normalizeModelProfilesStore,
  profileToLlmConfig,
  removeModelProfile,
  setActiveModelProfile,
  setOcrModelProfile,
  getOcrModelProfile,
  isBlockedOcrModel,
  formatProfilePickerLabel,
  normalizeThinkingMode,
} from '../../lib/llm-profiles'
import { isProbeExpressionAllowed, clampProbeResult } from '../../lib/main-probe'
const testRecord = (kind: string, title: string, content: any): TraceRecord => {
  if (kind === 'user') return { schema: 1, id: crypto.randomUUID(), at: 1, runId: 'test', channel: 'conversation', type: 'user.task', payload: { text: String(content) } }
  if (kind === 'result') return { schema: 1, id: crypto.randomUUID(), at: 1, runId: 'test', channel: 'conversation', type: 'run.result', payload: { text: String(content) } }
  return { schema: 1, id: crypto.randomUUID(), at: 1, runId: 'test', channel: 'trace', type: 'tool.result', payload: { tool: title, arguments: content.arguments ?? {}, ok: content.result?.ok ?? content.ok ?? true, data: content.result?.data } }
}
import {
  normalizeMaxAgentSteps,
  normalizeRunTimeoutMs,
  normalizeSameFailureLimit,
  normalizeTokenBudget,
  normalizePrivacySettings,
  DEFAULT_PRIVACY,
  DEFAULT_MAX_AGENT_STEPS,
  DEFAULT_TOKEN_BUDGET,
} from '../../lib/settings'
import { buildSessionAuditExport } from '../../lib/session-export'
import { parseGitHubSkill, parseGitHubSkillUrl, githubSkillDir, skillResourcePath } from '../../lib/github-skill'
import { mcpToolRequiresConfirmation } from '../../lib/mcp-policy'

function assert(condition: unknown, message: string): asserts condition {
  if (!condition) throw new Error(message)
}

assert(
  NAV_ITEMS.map((item) => item.id).join(',') ===
    'account,toolkit,plugins,automation,workspace,geniusFall,settings',
  'management information architecture'
)
assert(sectionFromHash('settings') === 'settings', 'hash routing default')
assert(sectionFromHash('#toolkit') === 'toolkit', 'hash routing toolkit')
assert(nextCopyTitle('Daily report · Copy 2', ['Daily report', 'Daily report · Copy', 'Daily report · Copy 2']) === 'Daily report · Copy 3', 'copy title numbering')
assert(
  nextCopyTitle('Task · Copy · Copy 3', ['Task · Copy · Copy 3', 'Task · Copy · Copy 2']) ===
    'Task · Copy 4',
  'stacked copy titles cleaned'
)

const status = describeSystem({
  modelConfigured: true,
  hostEnabled: true,
  enabledSkills: 3,
  totalSkills: 4,
  enabledConnections: 2,
})
assert(status.ready === 4 && status.total === 4, 'overview readiness')

const skill = parseImportedSkill(
  '{"manifest":{"id":"docs","version":"1.0.0","description":"Search docs"},"instructions":"Use MCP docs."}'
)
assert(skill.manifest.id === 'docs', 'skill import validation')

const mdSkill = parseImportedSkill(`---
name: local-md
description: from disk
version: 1.2.0
---

Do the thing.
`)
assert(mdSkill.manifest.id === 'local-md', 'SKILL.md import')
assert(mdSkill.instructions === 'Do the thing.', 'SKILL.md body')

let rejected = false
try {
  parseImportedSkill('{"manifest":{"id":"broken"}}')
} catch {
  rejected = true
}
assert(rejected, 'invalid skill import rejected')

const now = 200_000_000
const activities = trimActivities(
  [
    { id: 'new', kind: 'agent', status: 'success', title: 'new', createdAt: now },
    { id: 'old', kind: 'agent', status: 'failed', title: 'old', createdAt: 1 },
  ],
  1,
  now
)
assert(activities.length === 1 && activities[0].id === 'new', 'activity retention')
assert(isEmbeddedSurface('?embedded=1'), 'side panel management mode')
assert(!isEmbeddedSurface(''), 'standalone management mode')
assert(SESSION_NAV_ITEM.id === 'automation', 'session navigation registered')
assert(
  redactSessionText('Authorization: Bearer secret-token').includes('[REDACTED]'),
  'session secret redaction'
)
assert(
  testRecord('tool', 'dom_click', { ok: true }).type === 'tool.result',
  'session tool message'
)
const githubSkill = parseGitHubSkillUrl(
  'https://github.com/acme/skills/blob/main/browser/SKILL.md'
)
assert(
  githubSkill.rawUrl === 'https://raw.githubusercontent.com/acme/skills/main/browser/SKILL.md',
  'GitHub skill raw URL'
)
assert(
  parseGitHubSkillUrl('https://github.com/acme/skills/tree/main/browser').path ===
    'browser/SKILL.md',
  'GitHub Skill directory URL'
)
assert(githubSkillDir(githubSkill) === 'browser', 'GitHub skill dir next to SKILL.md')
assert(
  skillResourcePath('browser-helper', 'scripts', 'run.py') === 'skills/browser-helper/scripts/run.py',
  'skill resource path'
)
assert(
  parseGitHubSkill(
    '---\nname: Browser helper\ndescription: Browse safely\nversion: 1.2.0\n---\nUse the browser.',
    githubSkill
  ).manifest.id === 'browser-helper',
  'GitHub SKILL.md conversion'
)
assert(BUILTIN_TOOL_CATALOG.some((tool) => tool.id === 'browser_nav'), 'navigate tool catalogued')
assert(BUILTIN_TOOL_CATALOG.some((tool) => tool.id === 'browser_observe'), 'observe tool catalogued')
assert(BUILTIN_TOOL_CATALOG.some((tool) => tool.id === 'web_search'), 'web_search tool catalogued')
const thread = createThread('Find current-page top4')
assert(thread.title === 'Find current-page top4' && thread.memory.goal === '', 'thread starts empty')
{
  const ctx = buildThreadContext(thread, [
    testRecord('user', 'Task', 'Find current-page top4'),
    testRecord('result', 'Completed', 'Top4 marked'),
  ])
assert(
  ctx.conversation.includes('Top4 marked'),
  'thread context includes recent verified result'
)
assert(ctx.conversation.includes('user:'), 'thread context uses continuous dialogue labels')
assert(ctx.conversation.includes('assistant:'), 'thread context labels prior results as assistant')
{
  const withPage = buildThreadContext(thread, [
    testRecord('user', 'Task', '介绍 MuseTalk'),
    testRecord('tool', 'dom_read', {
      arguments: { mode: 'body' },
      result: {
        ok: true,
        data: { url: 'https://github.com/Tencent/MuseTalk', text: 'pip install musetalk' },
      },
    }),
    testRecord('tool', 'skill_load', {
      arguments: { id: 'page-read' },
      result: { ok: true, data: { id: 'page-read', version: '0.2.0' } },
    }),
    testRecord('result', 'Completed', 'MuseTalk 是口型同步项目'),
  ])
  assert(withPage.reuse.skillIds.join() === 'page-read', 'thread reuses loaded skill ids')
  assert(withPage.reuse.page?.url === 'https://github.com/Tencent/MuseTalk', 'thread reuses read_page url')
  assert(withPage.reuse.page?.evidence.includes('pip install musetalk'), 'thread keeps dom_read body')
}
}
assert(shouldCompactThread({ ...EMPTY_THREAD_MEMORY, facts: Array.from({ length: 24 }, () => 'x') }), 'slot overflow compacts')
assert(!shouldCompactThread({ ...EMPTY_THREAD_MEMORY, facts: ['one fact'] }), 'small memory stays recent-only')
{
  const bloated = {
    ...EMPTY_THREAD_MEMORY,
    facts: Array.from({ length: 18 }, () => 'f'.repeat(400)),
  }
  assert(formatThreadMemory(bloated).length <= 6_000, 'display format stays capped')
  assert(threadMemoryPressure(bloated) > 6_000, 'pressure measures unsliced memory')
  assert(shouldCompactThread(bloated), 'over-budget memory compact even when display is sliced')
}
const parsed = parseThreadMemoryJson(
  '{"goal":"top4","facts":["marked TOP1-TOP4"],"constraints":["stay on page"],"open_questions":[],"last_outcome":"done"}'
)
assert(parsed?.goal === 'top4' && parsed.facts.length === 1, 'thread memory JSON parse')
const merged = mergeThreadMemory(
  { goal: 'top4', facts: ['a'], constraints: [], openQuestions: [], lastOutcome: '' },
  { facts: ['b'], lastOutcome: 'ok' }
)
assert(merged.facts.join(',') === 'a,b' && merged.lastOutcome === 'ok', 'thread memory merge')
assert(formatThreadMemory(merged).includes('GOAL: top4'), 'thread memory format')
assert(BUILTIN_TOOL_CATALOG.length <= 15 && BUILTIN_TOOL_CATALOG.length >= 10, 'builtin catalog from shared')
assert(buildSessionAuditExport([], []).schemaVersion === 1, 'session export schema')

const legacy = migrateLegacyLlmSettings({
  baseURL: 'https://api.example/v1',
  model: 'gpt-4o',
  apiKey: 'sk-test',
})
assert(legacy.profiles.length === 1 && legacy.profiles[0]!.model === 'gpt-4o', 'legacy llm migration')
const multi = addModelProfile(legacy, { name: 'Claude', model: 'claude-sonnet-4-6' })
assert(multi.profiles.length === 2 && multi.activeProfileId === multi.profiles[1]!.id, 'add profile')
const switched = setActiveModelProfile(multi, legacy.profiles[0]!.id)
assert(getActiveModelProfile(switched).model === 'gpt-4o', 'switch active profile')
const withOcr = setOcrModelProfile(switched, switched.profiles[1]!.id)
assert(getOcrModelProfile(withOcr)?.model === 'claude-sonnet-4-6', 'ocr profile pointer')
const trimmed = removeModelProfile(withOcr, withOcr.profiles[1]!.id)
assert(trimmed.profiles.length === 1, 'remove profile keeps minimum one')
assert(getOcrModelProfile(trimmed) === undefined, 'removing ocr profile clears pointer')
assert(isBlockedOcrModel('deepseek-v4-flash'), 'deepseek v4 blocked for ocr')
assert(!isBlockedOcrModel('qwen3.5-ocr'), 'qwen ocr allowed')
assert(
  profileToLlmConfig(getActiveModelProfile(trimmed)).baseURL.includes('api.example'),
  'profile to runtime config'
)
assert(normalizeModelProfilesStore(undefined).profiles.length === 1, 'empty store normalized')
assert(normalizeThinkingMode('nope') === 'off', 'unknown thinking → off')
assert(formatProfilePickerLabel({ name: 'Grok', thinking: 'off' }) === 'Grok', 'picker hides off')
assert(formatProfilePickerLabel({ name: 'Grok', thinking: 'xhigh' }) === 'Grok 极高', 'picker shows intensity')
const withThink = addModelProfile(legacy, { name: 'Think', model: 'x', thinking: 'high' })
assert(getActiveModelProfile(withThink).thinking === 'high', 'add profile keeps thinking')
assert(profileToLlmConfig(getActiveModelProfile(withThink)).reasoningEffort === 'high', 'thinking → reasoningEffort')
assert(
  profileToLlmConfig(getActiveModelProfile(legacy)).reasoningEffort === undefined,
  'off thinking omits reasoningEffort'
)
assert(isProbeExpressionAllowed('window.__PLAYER__.src'), 'probe allows property read')
assert(!isProbeExpressionAllowed('eval("1")'), 'probe blocks eval')
assert(clampProbeResult({ a: 1 }).ok, 'probe result clamp')
assert(mcpToolRequiresConfirmation('create_issue'), 'mcp write heuristic')
assert(!mcpToolRequiresConfirmation('search_docs'), 'mcp read heuristic')
assert(normalizeMaxAgentSteps(99) === 99, 'max steps accepts 99')
assert(normalizeMaxAgentSteps(9999) === 500, 'max steps cap')
assert(normalizeMaxAgentSteps('bad') === DEFAULT_MAX_AGENT_STEPS, 'max steps invalid → default 30')
assert(normalizeSameFailureLimit(2) === 2, 'same failure default shape')
assert(normalizeSameFailureLimit(-1) === 0, 'same failure floor')
assert(normalizeRunTimeoutMs(8 * 60_000) === 8 * 60_000, 'run timeout 8m')
assert(normalizeRunTimeoutMs(0) === 0, 'run timeout off')
assert(normalizeTokenBudget(80_000) === 80_000, 'token budget')
assert(normalizeTokenBudget(0) === 0, 'token budget off')
assert(
  normalizePrivacySettings({ ...DEFAULT_PRIVACY, tokenBudget: 80_000 }).privacy.tokenBudget === 80_000,
  'token budget within bounds stays'
)
assert(
  normalizePrivacySettings({ ...DEFAULT_PRIVACY, tokenBudget: 0 }).privacy.tokenBudget === 0,
  'token budget off stays off'
)

console.log('options model self-check ok')
