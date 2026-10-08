import {
  forgePlaybook,
  networkExpectationFor,
  parameterizePlaybook,
  resolvePlaybookText,
  resolveStepTarget,
} from '@naviforge/playbook'
import { buildDigest, matchInterceptRule, matchNetworkEvent } from '@naviforge/network-plane'
import { formatSkillCatalog, formatSkillGuidance, loadSkillBody, routeSkills } from '@naviforge/skill-runtime'
import type { DomPlane, DomSnapshot } from '@naviforge/dom-plane'
import { createTraceRecord } from '@naviforge/session'

import { execTurn, parseSnapshotMode } from './exec-turn.js'
import { chatCompletion } from './llm.js'
import {
  Agent,
  createHitlGate,
  createMessageQueue,
  createPauseController,
  formatActingDetail,
  isToolAllowed,
  requestedList,
  requestedTopN,
  isPageReadTask,
  resolveTaskMode,
  shouldHintListThenDetail,
  runAgent,
  normalizeScrollArgs,
  formatReadPageTrace,
  formatExtractDomTrace,
  formatExtractContentTrace,
  formatWebSearchTrace,
  formatFetchTextTrace,
  normalizeFetchTextUrl,
  clampFetchMaxChars,
  observationDedupeKey,
  actionLoopKey,
  urlsMatchForReuse,
  isCspEvalError,
} from './agent.js'
import { classifyFailure, isAbortError, retry } from './recovery.js'
import {
  DEFAULT_RUN_LIMITS,
  HARD_DENY_ERROR_CODES,
  formatListOpenConstraint,
  hardDenyQuestion,
  listHintsFromToolData,
  sameFailureQuestion,
} from './run-limits.js'
import { KERNEL_PROMPT, composeSystemPrompt, compileUserPrompt, formatListResult } from './prompt.js'
import { isPageReadTask } from './loop-gates.js'
import { runReadonlySubAgents } from './readonly-agent.js'
import { projectTraceRecords } from './working-set.js'
import {
  askAboutPage,
  ocrImage,
  PAGE_ASK_SYSTEM,
  PAGE_TEXT_SYSTEM,
  PAGE_SUMMARIZE_QUESTION,
  OCR_SYSTEM,
  explainPickedQuestion,
  pickedElementExcerpt,
  resolveOneShotQuestion,
} from './ask-about-page.js'
import { formatMcpToolCatalog, resolveMcpCall } from './mcp-tools.js'
import { resolveTaskScope, evaluateAskUser } from '@naviforge/policy'
import { isLikelyNavigationClick } from '@naviforge/policy'
import { compactSnapshotForPrompt } from '@naviforge/observe'
import { detectUrlDrift, urlsEquivalentForScope } from '@naviforge/policy'
import {
  AGENT_TOOL_CATALOG,
  AGENT_TOOL_IDS,
  buildChatTools,
  isCoveredByToolAllowlist,
  mcpQualifiedName,
  parseMcpQualifiedName,
} from '@naviforge/shared'
import type { AgentIo } from './agent-ctx.js'

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg)
}

type MockToolCall = { tool: string; arguments: Record<string, unknown> }

function mockLlmChoice(call: MockToolCall): { message: Record<string, unknown> } {
  return {
    message: {
      tool_calls: [
        {
          id: 'call_1',
          function: {
            name: call.tool,
            arguments: JSON.stringify(call.arguments),
          },
        },
      ],
    },
  }
}

const snap: DomSnapshot = {
  revision: 1,
  url: 'http://localhost/test',
  title: 'Test',
  header: 'header',
  content: '[1] button "Go"',
  footer: 'footer',
}

assert(mcpQualifiedName('docs', 'search') === 'mcp__docs__search', 'mcp__ name')
assert(parseMcpQualifiedName('mcp__docs__search')?.tool === 'search', 'parse mcp__ name')
{
  const listing = [
    {
      serverId: 'docs',
      serverName: 'Docs',
      name: 'search',
      description: 'Search docs',
      inputSchema: { type: 'object', properties: { q: { type: 'string' } } },
    },
  ]
  const catalog = formatMcpToolCatalog(listing)!
  assert(catalog.includes('mcp__docs__search'), 'MCP catalog uses qualified names')
  assert(catalog.includes('arguments:'), 'MCP catalog includes per-tool schema')
  const viaName = resolveMcpCall('mcp__docs__search', { q: 'x' }, listing)
  assert(viaName.ok && viaName.call.tool === 'search' && viaName.call.arguments.q === 'x', 'resolve mcp__')
  const rejected = resolveMcpCall(
    'mcp.call',
    { serverId: 'docs', tool: 'search', arguments: { q: 'y' } },
    listing
  )
  assert(!rejected.ok, 'mcp.call meta-tool is removed')
}

const user = compileUserPrompt('click Go', snap, [], 'NETWORK: (empty)')
assert(user.includes('NETWORK:'), 'network in prompt')
assert(
  compileUserPrompt(
    'click Go',
    snap,
    [],
    'NETWORK: (empty)',
    undefined,
    { memory: 'remember scope', conversation: '', reuse: { skillIds: [] } }
  ).includes(
    'remember scope'
  ),
  'thread context in prompt'
)

{
  const { formatPageState } = await import('./page-state.js')
  const { resolveSnapshotPromptPolicy } = await import('./prompt.js')
  const loginState = {
    url: 'https://example.com/login',
    title: 'Sign in',
    role: 'login' as const,
    blocked: true,
    items: [],
  }
  assert(resolveSnapshotPromptPolicy({ pageState: loginState, hasStickyPageEvidence: false }).omitA11yBody)
  const loginPrompt = compileUserPrompt(
    '分析站点结构',
    snap,
    [],
    'NETWORK: (empty)',
    undefined,
    undefined,
    undefined,
    'in_page',
    undefined,
    undefined,
    formatPageState(loginState),
    loginState
  )
  assert(loginPrompt.includes('PAGE STATE'), 'login prompt keeps page_state')
  assert(!loginPrompt.includes('[1]'), 'login prompt omits a11y index lines')
  assert(loginPrompt.includes('browser_observe'), 'login prompt hints observe for snapshot')
}
{
  const records = [
    createTraceRecord({ type: 'user.steer', runId: 'working-set', payload: { texts: ['留在当前页'], phase: 'pre_model' } }),
    ...Array.from({ length: 10 }, (_, index) =>
      createTraceRecord({
        type: 'tool.result',
        runId: 'working-set',
        payload: { tool: 'dom_read', arguments: { mode: 'list', n: index }, ok: true, data: { text: 'item '.repeat(800) } },
      })
    ),
  ]
  const compiled = compileUserPrompt('介绍一下', snap, projectTraceRecords(records, { maxInputTokens: 8_000 }).items.map((item) => item.content), 'NETWORK: (empty)')
  assert(compiled.includes('留在当前页'), 'steer survives record-based compaction')
  assert(compiled.length < 28_000, 'compiled prompt does not ingest 10 extract dumps')
  assert(!compiled.includes('item item item'), 'raw tool payloads stay out of the prompt')
}

assert(AGENT_TOOL_IDS.includes('browser_act'), 'browser_act tool in catalog')
assert(
  formatListResult(
    [
      { label: 'TOP1', index: 7, title: '正确标题', url: 'https://example.com/video/1' },
      { label: 'TOP2', index: 8, title: '第二条', url: 'https://example.com/video/2' },
    ],
    true
  ) ===
    '已在当前页面标记 2 个条目：\n1. 正确标题\n   https://example.com/video/1\n2. 第二条\n   https://example.com/video/2',
  'deterministic list result is useful and concise'
)
const directEvents: { type: string; taskId?: string; turn?: number }[] = []
const direct = await runAgent({   task: '标记top3',
  taskId: 'task-1',
  dom: {
    snapshot: async () => ({ ok: true, data: snap }),
    markTopn: async () => ({
      ok: true,
      data: {
        marked: 3,
        candidates: 10,
        items: [
          { label: 'TOP1', index: 1, title: '正确标题', url: 'https://example.com/1' },
          { label: 'TOP2', index: 2, title: '第二条', url: 'https://example.com/2' },
          { label: 'TOP3', index: 3, title: '第三条', url: 'https://example.com/3' },
        ],
      },
    }),
  } as DomPlane,
  llm: { baseURL: 'http://must-not-be-called', apiKey: 'x', model: 'x' },
  onRecord: (record) => directEvents.push(record),
})
assert(direct.status === 'done', 'deterministic top-N finishes without model loop')
assert(direct.result?.includes('正确标题'), 'deterministic top-N returns extracted titles')
assert(
  !directEvents.some((event) => event.type === 'model.turn'),
  'deterministic top-N never asks the model to repeat extraction'
)
assert(
  directEvents.every((event) => event.taskId === 'task-1'),
  'every event is attributed to the task that produced it'
)
assert(
  directEvents.every((event) => event.turn === undefined),
  'work outside the model loop carries no turn'
)

const readPreflightEvents: Array<{ type: string; tool?: string }> = []
let readPagePreflightCalled = false
const readFetchBackup = globalThis.fetch
globalThis.fetch = (async () => ({
  ok: true,
  json: async () => ({
    choices: [
      mockLlmChoice({ tool: 'system_done', arguments: { result: 'Snapzy 是 macOS 截图工具。' } }),
    ],
  }),
})) as unknown as typeof fetch
try {
  const readRun = await runAgent({     task: '详细介绍一下这个项目',
    taskId: 'read-task',
    maxSteps: 2,
    dom: {
      snapshot: async () => ({ ok: true, data: snap }),
      readPage: async () => {
        readPagePreflightCalled = true
        return {
          ok: true,
          data: {
            text: 'Snapzy is an open-source macOS screenshot and screen recording app.',
            source: 'github-readme',
            truncated: false,
            title: 'Snapzy',
            url: snap.url,
          },
        }
      },
    } as DomPlane,
    llm: { baseURL: 'http://local', apiKey: 'x', model: 'x' },
    onRecord: (record) => {
      if (record.type === 'tool.result') {
        readPreflightEvents.push({ type: record.type, tool: record.payload.tool })
      }
    },
  })
  assert(readPagePreflightCalled, 'read task preflight calls readPage')
  assert(
    readPreflightEvents.some((event) => event.tool === 'dom_read'),
    'read task emits dom_read before model'
  )
  assert(readRun.status === 'done', 'read task can finish after model summarizes preflight text')
} finally {
  globalThis.fetch = readFetchBackup
}

{
  const dupScript = [
    { tool: 'dom_read', arguments: { mode: 'body' } },
    { tool: 'dom_read', arguments: { mode: 'body' } },
    { tool: 'system_done', arguments: { result: 'TTS 2.0 见产品计费' } },
  ]
  let dupCursor = 0
  let readCalls = 0
  const dupFetch = globalThis.fetch
  const skipLogs: string[] = []
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({
      choices: [mockLlmChoice(dupScript[dupCursor++] ?? dupScript.at(-1)!)],
    }),
  })) as unknown as typeof fetch
  try {
    const dupRun = await runAgent({       task: '整理一下模型和价格，给出对比后的建议',
      taskId: 'dup-read',
      maxSteps: 6,
      dom: {
        snapshot: async () => ({ ok: true, data: snap }),
        readPage: async () => {
          readCalls += 1
          return {
            ok: true,
            data: {
              text: '模型列表\nTTS 2.0 和 ICL 2.0。价格见产品计费。',
              source: 'article',
              truncated: false,
              title: '模型列表',
              url: snap.url,
            },
          }
        },
      } as DomPlane,
      llm: { baseURL: 'http://dup', apiKey: 'x', model: 'x' },
      onRecord: (record) => {
        if (record.type === 'run.log') skipLogs.push(record.payload.message)
      },
    })
    assert(readCalls === 1, 'second dom_read body on same URL is not executed')
    assert(
      skipLogs.some((message) => message.includes('skip duplicate dom_read')),
      'duplicate dom_read is skipped with a hint'
    )
    assert(dupRun.status === 'done', 'run can finish after duplicate skip')
  } finally {
    globalThis.fetch = dupFetch
  }
}

{
  const jsScript = [
    { tool: 'dom_execute_js', arguments: { code: 'return {count:2}' } },
    { tool: 'system_done', arguments: { result: '2 items' } },
  ]
  let jsCursor = 0
  let jsCalls = 0
  const jsDenied: string[] = []
  const jsFetch = globalThis.fetch
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({
      choices: [mockLlmChoice(jsScript[jsCursor++] ?? jsScript.at(-1)!)],
    }),
  })) as unknown as typeof fetch
  try {
    const jsRun = await runAgent({       task: '取样这个接口',
      taskId: 'js-ungate',
      maxSteps: 4,
      allowDomInject: false,
      dom: {
        snapshot: async () => ({ ok: true, data: snap }),
        executeJs: async () => {
          jsCalls += 1
          return { ok: true, data: { result: { count: 2 } } }
        },
      } as DomPlane,
      llm: { baseURL: 'http://js', apiKey: 'x', model: 'x' },
      onRecord: (record) => {
        if (record.type === 'tool.result' && !record.payload.ok) {
          jsDenied.push(record.payload.error?.code ?? '')
        }
      },
    })
    assert(jsCalls >= 1, 'execute_js runs without allowDomInject')
    assert(!jsDenied.includes('execute_js_denied'), 'execute_js is not privacy-gated')
    assert(jsRun.status === 'done', 'execute_js run can finish')
  } finally {
    globalThis.fetch = jsFetch
  }
}

{
  let extractCalls = 0
  const extractScript = [
    { tool: 'dom_read', arguments: { mode: 'list', n: 8 } },
    { tool: 'dom_read', arguments: { mode: 'list', n: 8 } },
    { tool: 'dom_read', arguments: { mode: 'list', n: 8 } },
    { tool: 'dom_read', arguments: { mode: 'list', n: 8 } },
  ]
  let extractCursor = 0
  const extractFetch = globalThis.fetch
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({
      choices: [mockLlmChoice(extractScript[extractCursor++] ?? extractScript.at(-1)!)],
    }),
  })) as unknown as typeof fetch
  try {
    const extractRun = await runAgent({       task: 'github上是否还有类似的项目',
      taskId: 'dup-extract',
      maxSteps: 8,
      tokenBudget: 0,
      dom: {
        snapshot: async () => ({ ok: true, data: snap }),
        extractContent: async () => {
          extractCalls += 1
          return {
            ok: true,
            data: {
              items: [{ title: 'Sponsors', index: 1, url: 'https://github.com/sponsors' }],
              candidates: 4,
            },
          }
        },
      } as DomPlane,
      llm: { baseURL: 'http://extract', apiKey: 'x', model: 'x' },
    })
    assert(extractCalls >= 1, 'repeat dom_read list on same URL is not re-executed')
    assert(extractRun.status === 'done', 'duplicate extract loop stops instead of burning tokens')
  } finally {
    globalThis.fetch = extractFetch
  }
}

{
  let reusedReads = 0
  let realSkillLoads = 0
  const reuseScript = [
    { tool: 'skill_load', arguments: { id: 'page-read' } },
    { tool: 'dom_read', arguments: { mode: 'body' } },
    { tool: 'system_done', arguments: { result: 'macOS: brew install musetalk' } },
  ]
  let reuseCursor = 0
  const reuseFetch = globalThis.fetch
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({
      choices: [mockLlmChoice(reuseScript[reuseCursor++] ?? reuseScript.at(-1)!)],
    }),
  })) as unknown as typeof fetch
  try {
    const reuseRun = await runAgent({       task: 'mac上怎么安装',
      taskId: 'reuse-read',
      maxSteps: 6,
      threadContext: {
        memory: '',
        conversation: '',
        reuse: {
          skillIds: ['page-read'],
          page: { url: 'http://localhost/test', evidence: 'brew install musetalk' },
        },
      },
      skills: [
        { id: 'page-read', version: '0.2.0', description: 'read', instructions: 'template' },
      ],
      dom: {
        snapshot: async () => ({ ok: true, data: snap }),
        readPage: async () => {
          reusedReads += 1
          return {
            ok: true,
            data: { text: 'should not re-read', source: 'article', truncated: false, title: 'x', url: snap.url },
          }
        },
      } as DomPlane,
      llm: { baseURL: 'http://reuse', apiKey: 'x', model: 'x' },
      onRecord: (record) => {
        if (record.type === 'tool.result' && record.payload.tool === 'skill_load' && record.payload.ok) {
          const data = record.payload.data as { skipped?: boolean }
          if (!data.skipped) realSkillLoads += 1
        }
      },
    })
    assert(reusedReads === 0, 'follow-up does not re-read the same URL')
    assert(realSkillLoads === 0, 'follow-up does not reload page-read')
    assert(reuseRun.status === 'done', 'follow-up can answer from PAGE EVIDENCE')
  } finally {
    globalThis.fetch = reuseFetch
  }
}

{
  let jsCspCalls = 0
  const cspScript = [
    { tool: 'dom_execute_js', arguments: { code: 'return 1' } },
    { tool: 'dom_execute_js', arguments: { code: 'return 2' } },
    { tool: 'system_done', arguments: { result: 'csp blocked' } },
  ]
  let cspCursor = 0
  const cspFetch = globalThis.fetch
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({
      choices: [mockLlmChoice(cspScript[cspCursor++] ?? cspScript.at(-1)!)],
    }),
  })) as unknown as typeof fetch
  try {
    await runAgent({       task: '抓仓库列表',
      taskId: 'csp-js',
      maxSteps: 5,
      dom: {
        snapshot: async () => ({ ok: true, data: snap }),
        executeJs: async () => {
          jsCspCalls += 1
          return {
            ok: false,
            error: {
              code: 'execute_js_failed',
              message: "Evaluating a string as JavaScript violates CSP",
              recoverable: true,
            },
          }
        },
      } as DomPlane,
      llm: { baseURL: 'http://csp', apiKey: 'x', model: 'x' },
    })
    assert(jsCspCalls >= 1, 'execute_js is not retried after page CSP blocks eval')
  } finally {
    globalThis.fetch = cspFetch
  }
}

// A scripted model loop: the only place where turn stamping, per-task reset and skill
// allowlist enforcement can be observed together instead of reasoned about.
const scripted = [
  { tool: 'dom_type', arguments: { index: 1, text: 'x', revision: 1 } },
  { tool: 'dom_click', arguments: { index: 1, revision: 1 } },
  { tool: 'system_done', arguments: { result: '第一个任务完成' } },
  { tool: 'system_done', arguments: { result: '第二个任务完成' } },
]
const realFetch = globalThis.fetch
let scriptCursor = 0
globalThis.fetch = (async () => ({
  ok: true,
  json: async () => ({
    choices: [mockLlmChoice(scripted[scriptCursor++] ?? scripted.at(-1)!)],
  }),
})) as unknown as typeof fetch

const loopQueue = createMessageQueue()
const followUp = loopQueue.followUp('然后总结页面')
const loopEvents: Array<{ type: string; taskId?: string; turn?: number; payload?: { code?: string } }> = []
try {
  await runAgent({     task: '点击 Go 按钮',
    taskId: 'task-1',
    dom: {
      snapshot: async () => ({ ok: true, data: snap }),
      click: async () => ({ ok: true, data: { clicked: true } }),
      selector: async () => ({ ok: true, data: { selector: 'button.go' } }),
    } as DomPlane,
    llm: { baseURL: 'http://scripted', apiKey: 'x', model: 'x' },
    allowedTools: ['dom_click'],
    queue: loopQueue,
    onRecord: (record) => loopEvents.push(record),
  })
} finally {
  globalThis.fetch = realFetch
}

const denied = loopEvents.find((event) => event.type === 'run.error')
assert(denied?.payload?.code === 'skill_allowlist', 'a tool the skill forbids is reported, not silently dropped')
assert(denied?.turn === 0, 'the denial is attributed to the turn that attempted it')
const clicked = loopEvents.find((event) => event.type === 'tool.result')
assert(clicked?.turn === 1, 'the retry after a denial is a new turn')
const results = loopEvents.filter((event) => event.type === 'run.result')
assert(results.length === 2, 'each queued task produces its own result')
assert(results[0]!.taskId === 'task-1' && results[1]!.taskId === followUp!.id, 'results stay attributable')
assert(results[1]!.turn === 0, 'a follow-up task restarts turn numbering')

assert(requestedTopN('标记当前页面 top5 视频') === 5, 'explicit marking enables topN preflight')
assert(requestedTopN('找出 top5 视频名称和链接，不需要标记') === null, 'extract-only request skips marking')
assert(requestedList('找出 top5 视频名称和链接，不需要标记')?.mark === false, 'extract-only intent parsed')
assert(requestedList('找出 top5 视频名称和链接，不需要标记')?.n === 5, 'extract-only keeps the count')
assert(requestedList('标记当前页面 top5 视频')?.mark === true, 'marking intent parsed')
assert(requestedList('标记top3')?.n === 3, 'compact Chinese top3 count parsed')
assert(requestedList('标记top3')?.mark === true, 'compact Chinese top3 marking intent parsed')
assert(requestedList('总结一下这个页面') === null, 'no list request')
assert(requestedList('抓取本页10个视频链接和名称')?.n === 10, 'Chinese count list parsed')
assert(requestedList('抓取本页10个视频链接和名称')?.mark === false, 'Chinese extract-only list')
assert(requestedList('top1讲了一个什么故事？简述内容') === null, 'story question skips list shortcut')
assert(requestedList('你使用skill了么') === null, 'meta skill question skips list shortcut')
assert(requestedList('根据浏览次数，在页面标记出top4')?.mark === true, 'mark top4 still deterministic')
assert(isPageReadTask('总结一下页面内容'), 'summarize this page')
assert(isPageReadTask('总结一下这个页面'), 'summarize this page short')
assert(isPageReadTask('详细介绍一下这个项目'), 'intro project is read task')
assert(isPageReadTask('这个项目是做什么的'), 'what project does')
assert(!isPageReadTask('找出当前页 top4'), 'top4 extract is not read')
assert(!isPageReadTask('有没有同类型的项目'), 'similar-project ask is not a page-read')
assert(resolveTaskMode('LongHorizon loopx 2个github项目什么区别') === 'research', 'github compare is research mode')
assert(
  routeSkills('2个github项目什么区别', [
    {
      manifest: {
        id: 'ecommerce-compare',
        version: '1',
        description: '用途：电商商品。非：开源项目、GitHub 仓库对比。',
        triggers: ['商品'],
      },
      instructions: '',
    },
  ]).length === 0,
  'ecommerce-compare excluded for github compare task'
)
assert(!shouldHintListThenDetail('详细介绍一下这个项目'), 'read skips list→detail')
assert(!isPageReadTask('top1讲了一个什么故事？简述内容'), 'story ask is not page summarize')
assert(!shouldHintListThenDetail('总结一下页面内容'), 'page summarize skips list→detail hint')
assert(shouldHintListThenDetail('第3个讲了什么故事'), 'nth item story uses list→detail')
assert(KERNEL_PROMPT.includes('browser_observe'), 'kernel documents browser_observe')
assert(KERNEL_PROMPT.includes('TASK_MODE'), 'kernel documents task modes')
assert(AGENT_TOOL_IDS.includes('browser_observe'), 'browser_observe in catalog')
assert(!AGENT_TOOL_IDS.includes('page_to_pdf'), 'page_to_pdf is resolver alias not catalog')
assert(
  actionLoopKey('dom_read', 'https://a.example/x', { mode: 'body' }) === null,
  'dom_read body uses observation dedupe not action loop'
)
{
  const observe = AGENT_TOOL_CATALOG.find((tool) => tool.id === 'browser_observe')
  assert(observe?.description.includes('js'), 'observe catalog includes readonly js')
  const tabs = AGENT_TOOL_CATALOG.find((tool) => tool.id === 'tabs')
  assert(tabs?.description.includes('open'), 'tabs catalog includes open')
  const done = AGENT_TOOL_CATALOG.find((tool) => tool.id === 'system_done')
  assert(done?.description.includes('结论'), 'system_done catalog is user-facing conclusion')
}
assert(KERNEL_PROMPT.includes('network'), 'network tool in kernel')
assert(!KERNEL_PROMPT.includes('tabs_open'), 'kernel does not name atomic tabs_open')
assert(KERNEL_PROMPT.includes('web_search'), 'kernel documents web_search')
assert(KERNEL_PROMPT.includes('fetch_text'), 'kernel documents fetch_text')
assert(KERNEL_PROMPT.includes('observe'), 'kernel documents observe')
assert(KERNEL_PROMPT.includes('等待新任务'), 'kernel bans idle-done phrasing')
assert(KERNEL_PROMPT.includes('禁止用滚动收割'), 'kernel forbids scroll harvest')
assert(KERNEL_PROMPT.includes('GUIDANCE:'), 'kernel tells the model to obey runtime guidance')
assert(KERNEL_PROMPT.includes('CONSTRAINT:'), 'kernel tells the model to obey runtime constraints')
assert(KERNEL_PROMPT.includes('CSP'), 'kernel stops js after CSP')
assert(KERNEL_PROMPT.includes('回复语言'), 'kernel documents reply language')
// Regression for tests/message.txt: a safety refusal with no tool call must
// not be silently invisible to the user. The kernel must explicitly tell the
// model to call system_done(status: blocked) when declining on safety/policy
// grounds, instead of outputting bare refusal text with no tool call.
assert(KERNEL_PROMPT.includes('"blocked"'), 'kernel documents the blocked status')
assert(
  KERNEL_PROMPT.includes('禁止') && KERNEL_PROMPT.includes('不协助'),
  'kernel forbids bare-text safety refusals with no tool call'
)
assert(
  !compileUserPrompt('2个github项目什么区别', snap, ['CONTEXT\n(none)'], 'NETWORK: (empty)', undefined, undefined, undefined, 'research').includes(
    'snapshot_body'
  ),
  'research mode omits full shell-page snapshot'
)
assert(normalizeScrollArgs({}).direction === 'down', 'empty scroll defaults down')
assert(normalizeScrollArgs({ to: 'bottom' }).to === 'bottom', 'explicit scroll to kept')
assert(observationDedupeKey('dom_read', 'https://a.example/x', { mode: 'body' }) === 'dom_read|https://a.example/x|body')
assert(observationDedupeKey('dom_read', 'https://a.example/x', { mode: 'list' }) === 'dom_read|https://a.example/x|list')
assert(
  observationDedupeKey('web_search', 'https://a.example/x', { query: 'LongHorizon-Harness github' }) ===
    'web_search|longhorizon-harness github',
  'repeat web_search query is deduped'
)
assert(
  observationDedupeKey('fetch_text', 'https://a.example/x', {
    url: 'https://raw.githubusercontent.com/o/r/main/a.md',
  }) === 'fetch_text|https://raw.githubusercontent.com/o/r/main/a.md',
  'repeat fetch_text url is deduped'
)
assert(normalizeFetchTextUrl('http://example.com').ok === false, 'fetch_text rejects http')
assert(normalizeFetchTextUrl('https://raw.githubusercontent.com/x/y.md').ok === true, 'fetch_text accepts https raw')
assert(clampFetchMaxChars(undefined) === 32_000, 'fetch_text default max chars')
{
  const fetchTrace = formatFetchTextTrace({
    url: 'https://raw.githubusercontent.com/o/r/a.md',
    status: 200,
    content_type: 'text/plain',
    text: '# hello',
    truncated: false,
  })
  assert(fetchTrace.includes('hello'), 'fetch_text trace keeps body excerpt')
  assert(fetchTrace.includes('status=200'), 'fetch_text trace keeps status')
}
assert(observationDedupeKey('dom_click', 'https://a.example/x') === null, 'clicks are not observation-deduped')
assert(
  actionLoopKey('dom_screenshot', 'https://a.example/x') === 'dom_screenshot|https://a.example/x',
  'screenshot loop key'
)
assert(
  actionLoopKey('dom_scroll', 'https://a.example/x', {}) === 'dom_scroll|https://a.example/x|down:',
  'scroll loop key defaults down'
)
assert(isCspEvalError("Evaluating a string as JavaScript violates CSP"), 'github CSP eval is detected')
assert(!isCspEvalError('timeout after 15000ms'), 'timeout is not CSP')
assert(urlsMatchForReuse('https://github.com/acme/app/', 'https://github.com/acme/app'), 'reuse url ignores trailing slash')
{
  const reuse = {
    skillIds: ['page-read'],
    page: { url: 'https://github.com/acme/app', evidence: 'brew install musetalk' },
  }
  assert(reuse.skillIds.join() === 'page-read', 'parse reuse skill ids')
  assert(reuse.page.url === 'https://github.com/acme/app', 'reuse page url remains structured')
  assert(reuse.page.evidence.includes('brew install musetalk'), 'reuse page evidence remains structured')
}
{
  const extractTrace = formatExtractContentTrace({
    items: [
      { title: 'Sponsors', url: 'https://github.com/sponsors' },
      { title: 'stargazers' },
    ],
    shortfall: 'not a repo list',
  })
  assert(extractTrace.includes('Sponsors'), 'extract_content trace keeps titles')
  assert(extractTrace.includes('shortfall=not a repo list'), 'extract_content trace keeps shortfall')
}
{
  const searchTrace = formatWebSearchTrace({
    results: [
      { title: 'NaviForge', url: 'https://example.com/a', snippet: 'browser agent' },
      { title: 'Alt', url: 'https://example.com/b', snippet: '' },
    ],
  })
  assert(searchTrace.includes('https://example.com/a'), 'web_search trace keeps urls')
  assert(searchTrace.includes('browser agent'), 'web_search trace keeps snippets')
}
{
  const body = '账号ID\n余额\n模型列表\nTTS 2.0 按量计费见产品计费页'
  const trace = formatReadPageTrace({
    text: body,
    source: 'article',
    truncated: false,
    title: '模型列表',
    url: 'https://docs.example/models',
  })
  assert(trace.includes('TTS 2.0'), 'read_page trace keeps article body')
  assert(trace.includes('docs.example/models'), 'read_page trace keeps url')
}
{
  const trace = formatExtractDomTrace({
    url: 'https://docs.example/news',
    title: '产品动态',
    items: [
      { index: 42, kind: 'link', title: '产品计费', tag: 'a' },
      {
        index: 53,
        kind: 'link',
        title: '模型列表',
        href: 'https://docs.example/models',
        tag: 'a',
      },
    ],
  })
  assert(trace.includes('模型列表'), 'extract_dom trace lists link titles')
  assert(trace.includes('https://docs.example/models'), 'extract_dom trace keeps href')
  assert(trace.includes('(no href)'), 'extract_dom trace marks missing href')
}
assert(
  compileUserPrompt('找出当前页面的top4', snap, [], 'NETWORK: (empty)').includes(
    '"navigation":"forbidden"'
  ),
  'current-page topN stays locked'
)
assert(
  !compileUserPrompt('打开热门排行榜', snap, [], 'NETWORK: (empty)').includes(
    '"navigation":"forbidden"'
  ),
  'explicit navigate tasks are not locked'
)
assert(
  resolveTaskScope('找出当前页面的top4视频').navigation === 'forbidden',
  'current-page topN forbids navigation'
)
assert(
  resolveTaskScope('打开热门排行榜').navigation === 'allowed',
  'explicit navigation stays allowed'
)
assert(
  resolveTaskScope('有没有同类型的项目').navigation === 'allowed',
  'similar-project ask allows navigation'
)
assert(
  compactSnapshotForPrompt({
    ...snap,
    content: Array.from({ length: 120 }, (_, index) => `[${index}] button "Item ${index}"`).join('\n'),
  }).content.includes('more lines'),
  'compact snapshot truncates long pages'
)
assert(
  isLikelyNavigationClick(
    { ...snap, content: '[2] link "热门"\n[3] button "Play"' },
    2
  ),
  'navigation guard blocks hot tab'
)
assert(
  !isLikelyNavigationClick(
    { ...snap, content: '[2] link "Video title"\n[3] button "Play"' },
    2
  ),
  'navigation guard allows content links'
)
assert(AGENT_TOOL_IDS.includes('browser_nav'), 'shared tool catalog wired')
assert(
  evaluateAskUser('请完成验证码', resolveTaskScope('找出当前页面的top4')).allow,
  'captcha ask allowed on scoped task'
)
assert(
  detectUrlDrift('https://a.com/x', 'https://a.com/y', resolveTaskScope('找出当前页面的top4')).drifted,
  'url drift on current-page task'
)
assert(urlsEquivalentForScope('https://a.com/x#one', 'https://a.com/x#two'), 'hash ignored in url compare')
assert(
  !evaluateAskUser('should I navigate to 热门?', resolveTaskScope('找出当前页面的top4')).allow,
  'hitl blocks navigation questions on scoped task'
)
assert(AGENT_TOOL_IDS.includes('system_spawn_readonly_tasks'), 'spawn readonly tool catalogued')
assert(!KERNEL_PROMPT.includes('渐进披露'), 'kernel defers Skill section to composeSystemPrompt')
assert(KERNEL_PROMPT.includes('function tool call'), 'prompt documents native function tools')
assert(
  KERNEL_PROMPT.includes('只调 **一个** 工具') || KERNEL_PROMPT.includes('恰好一个 function tool call'),
  'prompt requires exactly one tool call per turn'
)
assert(!KERNEL_PROMPT.includes('每轮至多调用一个工具'), 'prompt no longer permits zero tool calls')
assert(composeSystemPrompt(undefined, { hasMcpTools: true }).includes('mcp__'), 'mcp section when tools present')
assert(!composeSystemPrompt(undefined, { hasMcpTools: false }).includes('## MCP'), 'no mcp section without tools')
assert(
  composeSystemPrompt(undefined, { runProfile: 'readonly-child' }).includes('只读子 Agent'),
  'readonly child kernel append'
)
assert(!KERNEL_PROMPT.includes('非原生'), 'kernel no longer uses text-only tool contract')
assert(!KERNEL_PROMPT.includes('mcp.call'), 'kernel must not mention removed mcp.call')
assert(!KERNEL_PROMPT.includes('Hermes'), 'kernel prompt must not name other agents')
assert(!KERNEL_PROMPT.includes('MAF'), 'kernel prompt must not name other agents')
assert(!KERNEL_PROMPT.includes('Claude Code'), 'kernel prompt must not name other agents')
assert(!KERNEL_PROMPT.includes('agentskills'), 'kernel prompt must not name other agents')
assert(!KERNEL_PROMPT.includes('skill_load'), 'skill_load lives in Skill section, not kernel meta list')
assert(!KERNEL_PROMPT.includes('## 工具参数'), 'kernel no longer dumps tool arg catalog')
assert(AGENT_TOOL_IDS.includes('network'), 'network tool catalogued')
assert(
  matchInterceptRule(
    { url: 'https://api.bilibili.com/x/v2/feed', method: 'GET' },
    { id: '1', urlIncludes: 'api.bilibili.com', action: 'mock', status: 200, body: '{}' }
  ),
  'intercept rule match'
)

assert(
  matchNetworkEvent(
    { id: '1', method: 'GET', url: 'https://x.com/api/a', status: 200, ts: 1 },
    { urlIncludes: '/api/', status: 200 }
  ),
  'match'
)
assert(
  routeSkills('fill a form', [
    { manifest: { id: 'form-fill', version: '1', description: 'fill form', triggers: ['form'] }, instructions: '' },
  ]).length === 1,
  'skill routing'
)
assert(
  routeSkills('详细介绍一下这个项目', [
    {
      manifest: {
        id: 'page-read',
        version: '1',
        description: 'intro summarize readme',
        triggers: ['介绍', '项目'],
      },
      instructions: '',
    },
  ])[0]?.manifest.id === 'page-read',
  'Chinese intro routes page-read'
)
assert(
  routeSkills('top1讲了一个什么故事？简述内容', [
    {
      manifest: {
        id: 'list-then-detail',
        version: '1',
        description: 'open detail and summarize',
        triggers: ['故事', '简述'],
      },
      instructions: '',
    },
    {
      manifest: {
        id: 'video-site-extract',
        version: '1',
        description: 'list extract only',
        triggers: ['视频', '列表'],
      },
      instructions: '',
    },
  ])[0]?.manifest.id === 'list-then-detail',
  'Chinese triggers route list-then-detail'
)
assert(!KERNEL_PROMPT.includes('list-then-detail'), 'kernel does not name skills')
assert(
  compileUserPrompt(
    'click Go',
    snap,
    [],
    'NETWORK: (empty)',
    '# skill:list-then-detail@0.1.0\nopen then summarize'
  ).includes('本会话有效'),
  'sticky skill_load body in user prompt'
)
{
  const hints = listHintsFromToolData({
    items: [
      { index: 7, title: '扩散模型', url: 'https://example.com/video/1' },
      { index: 8, title: '浏览器 Agent' },
    ],
  })
  assert(hints.length === 2 && hints[0]?.url?.includes('/video/1'), 'list hints from tool data')
  assert(formatListOpenConstraint(hints).includes('index=7'), 'open constraint lists indexes')
}
{
  const skills = [
    {
      manifest: { id: 'form-fill', version: '1', description: 'fill form', triggers: ['form'] },
      instructions: 'Use type then click.',
    },
  ]
  const guided = formatSkillGuidance(skills)
  assert(guided.includes('available_skills'), 'progressive skill L1 uses available_skills')
  assert(guided.includes('<name>form-fill</name>'), 'progressive skill catalogs id in XML')
  assert(guided.includes('<description>'), 'L1 includes description element')
  assert(guided.includes('skill_load'), 'L1 instructs skill_load')
  assert(guided.includes('L1='), 'short skill protocol header')
  assert(!guided.includes('(v1)'), 'L1 catalog is id + description only')
  assert(!guided.includes('· tools:'), 'L1 catalog does not dump tool allowlists')
  assert(!guided.includes('form-fill@1'), 'catalog no longer uses id@version copy bait')
  assert(!guided.includes('Use type then click.'), 'progressive skill never dumps body into prompt')
  assert(formatSkillCatalog(skills).includes('fill form'), 'catalog is L1 only')
  assert(loadSkillBody(skills, 'form-fill')?.includes('Use type then click.'), 'skill_load path returns body')
  assert(loadSkillBody(skills, 'form-fill@1')?.includes('Use type then click.'), 'skill_load accepts id@version')
  assert(loadSkillBody(skills, 'missing') === null, 'skill_load missing id')
  assert(
    loadSkillBody(
      [
        {
          manifest: { id: 'pdf', version: '1', description: 'pdf' },
          instructions: 'Extract.',
          files: ['skills/pdf/scripts/extract.py', 'skills/pdf/references/schema.md'],
        },
      ],
      'pdf'
    )?.includes('skills/pdf/scripts/extract.py'),
    'skill_load lists bundled scripts/references'
  )
  const readBody = loadSkillBody(
    [
      {
        manifest: {
          id: 'page-read',
          version: '0.2.0',
          description: 'READ done template',
          triggers: ['介绍'],
        },
        instructions: '### 一句话\n≤40 字\n### 适合谁\n版式硬规则',
      },
    ],
    'page-read'
  )
  assert(readBody?.includes('### 一句话'), 'page-read skill body exposes done template')
  const system = composeSystemPrompt(guided)
  assert(system.includes('## Skill（渐进披露）'), 'skill protocol + catalog is one system section')
  assert(system.includes('skill_load'), 'unified Skill section documents skill_load')
  assert(system.includes('available_skills'), 'unified Skill section includes L1 catalog')
  assert(system.startsWith(KERNEL_PROMPT), 'system prompt keeps kernel first')
  assert(!system.includes('## Available Skills'), 'no second Skills heading')
  assert(
    !compileUserPrompt('click Go', snap, [], 'NETWORK: (empty)').includes('available_skills'),
    'skill L1 must not live in user message'
  )
}
{
  const tools = buildChatTools([
    {
      serverId: 'docs',
      name: 'search',
      description: 'Search docs',
      inputSchema: { type: 'object', properties: { q: { type: 'string' } } },
    },
  ])
  assert(tools.some((t) => t.function.name === 'browser_act'), 'API tools use OpenAI-safe names')
  assert(tools.some((t) => t.function.name === 'mcp__docs__search'), 'API tools include mcp__')
  assert(tools.some((t) => t.function.name === 'skill_load'), 'API tools include skill_load as skill_load')
  assert(tools.some((t) => t.function.name === 'web_search'), 'API tools include web_search as web_search')
  assert(tools.some((t) => t.function.name === 'fetch_text'), 'API tools include fetch_text')
  assert(tools.some((t) => t.function.name === 'browser_observe'), 'API tools expose browser_observe')
  assert(!tools.some((t) => t.function.name === 'dom_extract_content'), 'legacy extract alias hidden from model tools[]')
  assert(
    tools.every((t) => /^[a-zA-Z0-9_-]+$/.test(t.function.name)),
    'API function names match OpenAI/DeepSeek pattern'
  )
}
{
  const apiNames = [...AGENT_TOOL_IDS]
  assert(new Set(apiNames).size === apiNames.length, 'API tool names are unique')
}
assert(buildDigest([]).count === 0, 'digest')
assert(isCoveredByToolAllowlist('dom_click', ['browser_act']), 'browser_act allowlist covers dom_click')
assert(isToolAllowed('dom_click', new Set(['dom_click'])), 'skill tool permission allows listed tool')
assert(!isToolAllowed('network_read', new Set(['dom_click'])), 'network_read must not bypass skill allowlist')
assert(!isToolAllowed('network_list', new Set(['dom_click'])), 'internal network_list must not bypass skill allowlist')
assert(isToolAllowed('system_done', new Set()), 'terminal tools remain available')
assert(isToolAllowed('skill_load', new Set(['dom_click'])), 'skill_load is always available meta tool')
assert(!isToolAllowed('workspace', new Set(['dom_click'])), 'workspace fs tool must not bypass skill allowlist')
assert(!isToolAllowed('workspace_read', new Set(['dom_click'])), 'workspace_read internal must not bypass skill allowlist')
assert(!isToolAllowed('mcp__docs__search', new Set(['dom_click'])), 'mcp tools must not bypass skill allowlist')
assert(parseSnapshotMode('viewport') === 'viewport', 'snapshot mode viewport')
assert(parseSnapshotMode('full') === 'full', 'snapshot mode full')
assert(parseSnapshotMode('nope') === undefined, 'snapshot mode rejects junk')
assert(!AGENT_TOOL_IDS.includes('mcp.call' as never), 'mcp.call removed from builtin catalog')
assert(DEFAULT_RUN_LIMITS.maxSteps === 30, 'default max steps 30')
assert(DEFAULT_RUN_LIMITS.runTokenBudget === 200_000, 'default run token budget 200k')
assert(DEFAULT_RUN_LIMITS.maxInputTokens === 32_000, 'default single prompt input limit')
assert(HARD_DENY_ERROR_CODES.has('execute_js_denied'), 'execute_js is hard deny')
assert(HARD_DENY_ERROR_CODES.has('no_search_key'), 'missing search key is hard deny')
assert(hardDenyQuestion('dom_execute_js', 'execute_js_denied').includes('Settings'), 'hard deny asks settings')
assert(
  hardDenyQuestion('web_search', 'no_search_key').includes('search API key'),
  'missing search key points at web search settings'
)
assert(
  sameFailureQuestion('dom_navigate', 'bad_args', 2).includes('action/url'),
  'navigate bad_args asks for action/url'
)
assert(sameFailureQuestion('dom_read', 'timeout', 2).includes('failed 2 times'), 'same failure asks')

const queue = createMessageQueue()
queue.steer('stay on page')
queue.steer('mark top4')
const first = queue.followUp('then summarize')
const second = queue.followUp('then close')
assert(first?.text === 'then summarize' && second?.text === 'then close', 'follow-ups enqueue with ids')
assert(queue.drainSteering().join('|') === 'stay on page|mark top4', 'steer drains all')
assert(queue.drainNextFollowUp()?.text === 'then summarize', 'follow-up drains one at a time')
assert(queue.drainNextFollowUp()?.text === 'then close', 'follow-up drains sequentially')
assert(queue.drainNextFollowUp() === null, 'follow-up queue empty')
assert(queue.pending().steering === 0 && queue.pending().followUp === 0, 'queues empty')
const third = queue.followUp('third')
assert(third && queue.listFollowUps().length === 1, 'list follow-ups')
queue.setFollowUps([
  { id: 'b', text: 'b' },
  { id: 'a', text: 'a' },
  { id: 'c', text: 'c' },
])
assert(queue.listFollowUps().map((task) => task.id).join('|') === 'b|a|c', 'replace follow-ups')
queue.moveFollowUp(2, 0)
assert(queue.listFollowUps().map((task) => task.id).join('|') === 'c|b|a', 'reorder follow-ups')
queue.updateFollowUp('b', 'beta')
assert(queue.listFollowUps().find((task) => task.id === 'b')?.text === 'beta', 'edit follow-up')
queue.removeFollowUp('c')
assert(queue.listFollowUps().map((task) => task.text).join('|') === 'beta|a', 'remove follow-up')

{
  const duplicateQueue = createMessageQueue()
  const firstDuplicate = duplicateQueue.followUp('summarize it', 'same-follow-up')
  const duplicate = duplicateQueue.followUp('ignore this duplicate', 'same-follow-up')
  assert(firstDuplicate?.text === 'summarize it', 'first duplicate-id follow-up is queued')
  assert(duplicate === null, 'duplicate-id follow-up is rejected')
  assert(duplicateQueue.listFollowUps().length === 1, 'duplicate-id input leaves one queued follow-up')

  const duplicateTaskRecords: Array<{ type: string; taskId?: string }> = []
  const duplicateFetch = globalThis.fetch
  let duplicateCursor = 0
  globalThis.fetch = (async () => ({
    ok: true,
    json: async () => ({
      choices: [
        mockLlmChoice(
          [
            { tool: 'system_done', arguments: { result: 'initial task complete' } },
            { tool: 'system_done', arguments: { result: 'follow-up complete' } },
          ][duplicateCursor++] ?? { tool: 'system_done', arguments: { result: 'unexpected duplicate task' } }
        ),
      ],
    }),
  })) as unknown as typeof fetch
  try {
    await runAgent({       task: 'initial task',
      taskId: 'initial-task',
      maxSteps: 4,
      queue: duplicateQueue,
      dom: { snapshot: async () => ({ ok: true, data: snap }) } as DomPlane,
      llm: { baseURL: 'http://queue', apiKey: 'x', model: 'x' },
      onRecord: (record) => duplicateTaskRecords.push(record),
    })
  } finally {
    globalThis.fetch = duplicateFetch
  }
  assert(
    duplicateTaskRecords.filter((record) => record.type === 'user.task' && record.taskId === 'same-follow-up').length === 1,
    'duplicate-id input emits one eventual follow-up task record'
  )
}

assert(formatActingDetail('skill_load', { id: 'video-site-extract' }).includes('video-site-extract'), 'acting detail names skill')
assert(formatActingDetail('mcp__docs__search').includes('MCP'), 'acting detail names MCP')
assert(formatActingDetail('dom_click').includes('dom_click'), 'acting detail names tool')
assert(formatActingDetail('web_search', { query: 'naviforge alternatives' }).includes('naviforge'), 'acting detail names search query')
assert(formatActingDetail('fetch_text', { url: 'https://raw.githubusercontent.com/o/r/a.md' }).includes('fetch_text'), 'acting detail names fetch_text')

const hitl = createHitlGate()
const waiting = hitl.waitForReply('stay on page?')
assert(hitl.isWaiting() && hitl.question() === 'stay on page?', 'hitl waiting')
assert(hitl.reply('yes, stay') === true, 'hitl reply accepted')
assert((await waiting) === 'yes, stay', 'hitl answer delivered')
assert(!hitl.isWaiting(), 'hitl cleared')

const hitlEarly = createHitlGate()
assert(hitlEarly.reply('go ahead') === true, 'early hitl reply buffers')
assert(hitlEarly.isWaiting(), 'buffered reply counts as waiting')
assert((await hitlEarly.waitForReply('navigate?')) === 'go ahead', 'early reply delivered on wait')
assert(!hitlEarly.isWaiting(), 'early hitl cleared')

const pause = createPauseController()
const abortCtrl = new AbortController()
pause.pause()
const pauseWait = pause.waitIfPaused(abortCtrl.signal)
abortCtrl.abort()
try {
  await pauseWait
  assert(false, 'pause wait should abort')
} catch (error) {
  assert(isAbortError(error), 'pause abort is AbortError')
}

const hitlAbort = createHitlGate()
const abortCtrl2 = new AbortController()
const hitlWait = hitlAbort.waitForReply('cancel me?', abortCtrl2.signal)
hitlAbort.cancelWaiting()
try {
  await hitlWait
  assert(false, 'hitl cancel should abort')
} catch (error) {
  assert(isAbortError(error), 'hitl cancel is AbortError')
}

assert(
  classifyFailure({ code: 'stale_revision', message: 'revision 1 != 2', recoverable: true })
    .strategy === 'reobserve_and_replan',
  'stale DOM ref recovery'
)
assert(
  classifyFailure({ code: 'mcp_error', message: 'HTTP 503', recoverable: true }).retryable,
  'transient MCP recovery'
)
let retryCount = 0
const retryValue = await retry(async () => {
  retryCount += 1
  if (retryCount < 2) throw new Error('HTTP 503')
  return 'recovered'
}, { attempts: 2, delayMs: 0 })
assert(retryValue === 'recovered' && retryCount === 2, 'retry transient failure')

const pb = forgePlaybook({
  title: 'demo',
  task: 'fill',
  actions: [
    { tool: 'dom_type', index: 1, text: 'hello' },
    { tool: 'dom_click', index: 2 },
  ],
})
assert(!!pb && pb.steps.length === 2, 'forge steps')
assert(forgePlaybook({ title: 'x', actions: [] }) === null, 'forge empty')
assert(resolvePlaybookText('${inputs.message}', { message: 'changed' }) === 'changed', 'input variable')
assert(
  resolvePlaybookText('prefix-${inputs.message}', { message: 'changed' }) === 'prefix-changed',
  'interpolated variable'
)
const parameterized = parameterizePlaybook(pb!)
assert(parameterized.inputs?.value1?.default === 'hello', 'parameter default')
assert(parameterized.steps[0].use === 'dom_type' && parameterized.steps[0].text === '${inputs.value1}', 'parameter step')
assert(
  resolveStepTarget({ id: 's1', use: 'dom_click', index: 2, selector: '#go' }).selector === '#go',
  'selector preferred'
)
const withSelector = forgePlaybook({
  title: 'selector',
  actions: [{ tool: 'dom_click', index: 2, selector: '[data-test="go"]' }],
})
assert(withSelector?.steps[0].use === 'dom_click' && withSelector.steps[0].selector === '[data-test="go"]', 'record selector')
assert(
  networkExpectationFor({
    id: 'n1',
    method: 'POST',
    url: 'https://example.com/api/search?q=hello',
    status: 200,
    ts: 1,
  }).urlIncludes === '/api/search',
  'network path expectation'
)

assert(AGENT_TOOL_IDS.length <= 15, 'model-facing catalog ≤15')
for (const id of AGENT_TOOL_IDS) {
  assert(AGENT_TOOL_CATALOG.some((tool) => tool.id === id), `catalog missing ${id}`)
}

assert(PAGE_ASK_SYSTEM.includes('不要编造'), 'page ask system mentions honesty')
assert(PAGE_TEXT_SYSTEM.includes('不要编造'), 'text ask system mentions honesty')
assert(PAGE_TEXT_SYSTEM.includes('正文'), 'text ask system is excerpt-first')
assert(OCR_SYSTEM.includes('不要总结'), 'ocr system forbids summary')
assert(resolveOneShotQuestion('summarize', '') === PAGE_SUMMARIZE_QUESTION, 'empty summarize uses default')
assert(resolveOneShotQuestion('summarize', '  重点是什么  ') === '重点是什么', 'typed summarize wins')
assert(
  resolveOneShotQuestion('explain', '', 'Submit') === explainPickedQuestion('Submit'),
  'empty explain uses picked label'
)
assert(resolveOneShotQuestion('page', '') === '', 'page ask has no default question')
assert(resolveOneShotQuestion('page', '标题？') === '标题？', 'page ask uses typed question')
assert(
  pickedElementExcerpt({ tag: 'button', title: 'Go', selector: '#go', text: 'Start' }).includes('#go'),
  'picked excerpt keeps selector'
)
{
  let sawImage = false
  let sawDoneTool = false
  const prevFetch = globalThis.fetch
  globalThis.fetch = (async (_url: RequestInfo | URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body ?? '{}')) as {
      messages?: Array<{ content?: unknown }>
      tools?: Array<{ function?: { name?: string } }>
    }
    const user = body.messages?.[1]?.content
    sawImage = Array.isArray(user) && user.some((part) => (part as { type?: string }).type === 'image_url')
    sawDoneTool = body.tools?.length === 1 && body.tools[0]?.function?.name === 'system_done'
    return new Response(
      JSON.stringify({
        choices: [
          {
            message: {
              tool_calls: [{ function: { name: 'system_done', arguments: '{"result":"页面标题是 Demo"}' } }],
            },
          },
        ],
        usage: { prompt_tokens: 10, completion_tokens: 5, total_tokens: 15 },
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    const result = await askAboutPage({
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'vision' },
      question: '标题是什么？',
      imageDataUrl: 'data:image/png;base64,aaa',
      url: 'https://example.com',
      title: 'Demo',
      textExcerpt: 'Demo page',
    })
    assert(result.answer === '页面标题是 Demo', 'askAboutPage returns system_done result')
    assert(sawImage, 'askAboutPage sends multimodal image_url')
    assert(sawDoneTool, 'page ask exposes only system_done')
    assert(result.usage?.totalTokens === 15, 'askAboutPage forwards usage')
  } finally {
    globalThis.fetch = prevFetch
  }
}
{
  let threw = false
  try {
    await askAboutPage({
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'text' },
      question: '总结',
    })
  } catch {
    threw = true
  }
  assert(threw, 'askAboutPage without image or excerpt fails')
}
{
  const prevFetch = globalThis.fetch
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ choices: [{ message: { content: 'raw text must not be used' } }] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })) as typeof fetch
  try {
    const out = await askAboutPage({
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'text' },
      question: '总结',
      textExcerpt: '正文',
    })
    assert(out.answer.includes('raw text'), 'page ask accepts plain text when gateway omits tool_calls')
  } finally {
    globalThis.fetch = prevFetch
  }
}
{
  let sawImage = false
  let system = ''
  const prevFetch = globalThis.fetch
  globalThis.fetch = (async (_url: RequestInfo | URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body ?? '{}')) as {
      messages?: Array<{ role?: string; content?: unknown }>
    }
    system = String(body.messages?.[0]?.content ?? '')
    const user = body.messages?.[1]?.content
    sawImage = Array.isArray(user) && user.some((part) => (part as { type?: string }).type === 'image_url')
    return new Response(
      JSON.stringify({
        choices: [
          {
            message: {
              tool_calls: [{ function: { name: 'system_done', arguments: '{"result":"这是一篇产品文档"}' } }],
            },
          },
        ],
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    const result = await askAboutPage({
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'text' },
      question: PAGE_SUMMARIZE_QUESTION,
      url: 'https://example.com/docs',
      title: 'Docs',
      textExcerpt: 'NaviForge 是浏览器 Agent。',
    })
    assert(result.answer === '这是一篇产品文档', 'text-only askAboutPage returns system_done result')
    assert(!sawImage, 'text-only askAboutPage does not send image_url')
    assert(system === PAGE_TEXT_SYSTEM, 'text-only askAboutPage uses text system prompt')
  } finally {
    globalThis.fetch = prevFetch
  }
}
{
  let sawImage = false
  const prevFetch = globalThis.fetch
  globalThis.fetch = (async (_url: RequestInfo | URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body ?? '{}')) as {
      messages?: Array<{ content?: unknown }>
    }
    const user = body.messages?.[1]?.content
    sawImage = Array.isArray(user) && user.some((part) => (part as { type?: string }).type === 'image_url')
    return new Response(
      JSON.stringify({
        choices: [
          {
            message: {
              tool_calls: [{ function: { name: 'system_done', arguments: '{"result":"顾问名单"}' } }],
            },
          },
        ],
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    const result = await ocrImage({
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'qwen3.5-ocr' },
      imageDataUrl: 'data:image/jpeg;base64,aaa',
    })
    assert(result.text === '顾问名单', 'ocrImage returns system_done transcription')
    assert(sawImage, 'ocrImage sends multimodal image_url')
  } finally {
    globalThis.fetch = prevFetch
  }
}
{
  let threw = false
  try {
    await ocrImage({
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'qwen3.5-ocr' },
      imageDataUrl: 'https://example.com/x.png',
    })
  } catch (error) {
    threw = (error as Error).message.includes('选区截图')
  }
  assert(threw, 'ocrImage rejects non-data image urls')
}
{
  const prevFetch = globalThis.fetch
  let sentBody = ''
  globalThis.fetch = (async (_url, init) => {
    sentBody = String(init?.body ?? '')
    return new Response(
      JSON.stringify({
        choices: [
          {
            message: {
              content: 'visible answer',
              reasoning_content: 'hidden chain',
              tool_calls: [
                { function: { name: 'system_done', arguments: '{"result":"ok"}' } },
                { function: { name: 'dom_click', arguments: '{"index":1}' } },
              ],
            },
          },
        ],
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    const result = await chatCompletion(
      { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm' },
      'sys',
      'user',
      {
        tools: [
          {
            type: 'function',
            function: {
              name: 'system_done',
              description: 'Finish the task',
              parameters: { type: 'object', properties: {} },
            },
          },
        ],
      }
    )
    assert(result.content === 'visible answer', 'assistant content stays separate from reasoning')
    assert(result.reasoning === 'hidden chain', 'reasoning_content is kept')
    assert(result.toolCalls?.[0]?.name === 'system_done', 'tool_calls survive')
    assert(result.toolCalls?.length === 2, 'multiple tool calls are preserved for protocol rejection')
    assert(JSON.parse(sentBody).tool_choice === 'required', 'tool-enabled requests require a function call')
    assert(!('reasoning_effort' in JSON.parse(String(sentBody))), 'off thinking omits reasoning_effort')
  } finally {
    globalThis.fetch = prevFetch
  }

  let sentHigh: string | undefined
  globalThis.fetch = (async (_url, init) => {
    sentHigh = String(init?.body ?? '')
    return new Response(
      JSON.stringify({ choices: [{ message: { content: 'ok' } }] }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    await chatCompletion(
      { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm', reasoningEffort: 'high' },
      'sys',
      'user'
    )
    assert(JSON.parse(sentHigh ?? '{}').reasoning_effort === 'high', 'thinking high sends reasoning_effort')
  } finally {
    globalThis.fetch = prevFetch
  }

  let sentThinkingTools: string | undefined
  globalThis.fetch = (async (_url, init) => {
    sentThinkingTools = String(init?.body ?? '')
    return new Response(
      JSON.stringify({ choices: [{ message: { content: 'ok' } }] }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    await chatCompletion(
      { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm', reasoningEffort: 'high' },
      'sys',
      'user',
      {
        tools: [
          {
            type: 'function',
            function: {
              name: 'system_done',
              description: 'Finish',
              parameters: { type: 'object', properties: {} },
            },
          },
        ],
      }
    )
    assert(JSON.parse(sentThinkingTools ?? '{}').tool_choice === 'auto', 'thinking + tools use auto tool_choice')
  } finally {
    globalThis.fetch = prevFetch
  }

  let sentDeepSeekTools: string | undefined
  globalThis.fetch = (async (_url, init) => {
    sentDeepSeekTools = String(init?.body ?? '')
    return new Response(
      JSON.stringify({ choices: [{ message: { content: 'ok' } }] }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    await chatCompletion(
      { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'deepseek-v4-flash' },
      'sys',
      'user',
      {
        tools: [
          {
            type: 'function',
            function: {
              name: 'system_done',
              description: 'Finish',
              parameters: { type: 'object', properties: {} },
            },
          },
        ],
      }
    )
    assert(JSON.parse(sentDeepSeekTools ?? '{}').tool_choice === 'auto', 'deepseek v4 uses auto tool_choice')
  } finally {
    globalThis.fetch = prevFetch
  }

  let sentKimi: string | undefined
  globalThis.fetch = (async (_url, init) => {
    sentKimi = String(init?.body ?? '')
    return new Response(
      JSON.stringify({ choices: [{ message: { content: 'ok' } }] }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    await chatCompletion(
      { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'bt-kimi-k3' },
      'sys',
      'user'
    )
    assert(JSON.parse(sentKimi ?? '{}').temperature === 1, 'kimi models use temperature 1')
  } finally {
    globalThis.fetch = prevFetch
  }

  let tempRetryBodies: string[] = []
  globalThis.fetch = (async (_url, init) => {
    const body = String(init?.body ?? '')
    tempRetryBodies.push(body)
    const temp = JSON.parse(body).temperature
    if (temp !== 1) {
      return new Response(
        JSON.stringify({
          error: { message: 'invalid temperature: only 1 is allowed for this model' },
        }),
        { status: 400, headers: { 'Content-Type': 'application/json' } }
      )
    }
    return new Response(
      JSON.stringify({ choices: [{ message: { content: 'ok' } }] }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    const result = await chatCompletion(
      { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'vendor-only-temp-1' },
      'sys',
      'user'
    )
    assert(result.content === 'ok', 'temperature retry succeeds')
    assert(tempRetryBodies.length === 2, 'retries once with temperature 1')
    assert(JSON.parse(tempRetryBodies[1] ?? '{}').temperature === 1, 'retry uses temperature 1')
  } finally {
    globalThis.fetch = prevFetch
  }
}

{
  const prevFetch = globalThis.fetch
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ choices: [{ message: {} }] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })) as typeof fetch
  try {
    const result = await chatCompletion(
      { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm' },
      'sys',
      'user'
    )
    assert(result.content === '' && result.toolCalls === undefined, 'empty completion reaches protocol handling')
  } finally {
    globalThis.fetch = prevFetch
  }
}

{
  const io = {
    planes: { dom: { snapshot: async () => ({ ok: true, data: snap }) } as DomPlane },
    snap,
    taskScope: resolveTaskScope('test'),
    llm: { baseURL: 'http://x', apiKey: 'x', model: 'x' },
    hitlPolicy: 'balanced',
    rollbackUrlDrift: true,
    allowDomInject: false,
    allowNetworkIntercept: false,
    createRecord: (type, payload) => createTraceRecord({ type, payload, runId: 'exec-turn-check' }),
  } satisfies AgentIo
  const done = await execTurn(
    { call: { tool: 'system_done', arguments: { result: '   ' } }, summary: 'system_done' },
    io
  )
  const ask = await execTurn(
    { call: { tool: 'system_ask_user', arguments: { question: '\n\t' } }, summary: 'system_ask_user' },
    io
  )
  assert(done.terminal?.type === 'run.error', 'system_done rejects whitespace-only result')
  assert(ask.terminal?.type === 'run.error', 'system_ask_user rejects whitespace-only question')
}

{
  const prevFetch = globalThis.fetch
  globalThis.fetch = (async () =>
    new Response(JSON.stringify({ choices: [{ message: {} }] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })) as typeof fetch
  try {
    const result = await runReadonlySubAgents({
      briefs: ['test'],
      parentRunId: 'parent-readonly-check',
      dom: { snapshot: async () => ({ ok: true, data: snap }) } as DomPlane,
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm' },
      maxSteps: 3,
    })
    assert(result.children[0]?.status === 'max_steps', 'readonly children use the shared protocol hook')
  } finally {
    globalThis.fetch = prevFetch
  }
}

{
  const records: import('@naviforge/session').TraceRecord[] = []
  const run = Agent.prototype.run
  Agent.prototype.run = async function () {
    if (this.opts.task === 'throws unexpectedly') throw new Error('unexpected child failure')
    return { status: 'done', result: 'sibling result', recordedActions: [], recoveries: [] }
  }
  try {
    const batch = await runReadonlySubAgents({
      briefs: ['throws unexpectedly', 'succeeds'],
      parentRunId: 'parent-child-throw',
      dom: { snapshot: async () => ({ ok: true, data: snap }) } as DomPlane,
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm' },
      onLeafRecord: (record) => records.push(record),
    })
    assert(batch.children.some((child) => child.status === 'done' && child.result === 'sibling result'), 'successful sibling remains in aggregate')
    assert(batch.children.some((child) => child.status === 'error' && child.result === 'unexpected child failure'), 'unexpected throw becomes failed child result')
    assert(
      records.some(
        (record) =>
          record.type === 'run.error' &&
          record.parentRunId === 'parent-child-throw' &&
          record.payload.message === 'unexpected child failure'
      ),
      'unexpected child throw emits a child trace error'
    )
  } finally {
    Agent.prototype.run = run
  }
}

{
  const records: import('@naviforge/session').TraceRecord[] = []
  let charged = 0
  const prevFetch = globalThis.fetch
  globalThis.fetch = (async (_url: RequestInfo | URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body ?? '{}')) as {
      messages?: Array<{ content?: string }>
      tools?: Array<{ function?: { name?: string } }>
    }
    const user = body.messages?.[1]?.content ?? ''
    const tools = body.tools?.map((tool) => tool.function?.name) ?? []
    assert(!tools.includes('dom_click'), 'readonly child never receives DOM write tools')
    const call =
      user.includes('deny click')
        ? { tool: 'dom_click', arguments: { index: 1, revision: 1 } }
        : user.includes('deny nested spawn')
          ? { tool: 'system_spawn_readonly_tasks', arguments: { briefs: ['nested'] } }
          : { tool: 'system_done', arguments: { result: 'child success' } }
    return new Response(
      JSON.stringify({
        choices: [mockLlmChoice(call)],
        usage: { prompt_tokens: 2, completion_tokens: 3, total_tokens: 5 },
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    const batch = await runReadonlySubAgents({
      briefs: ['child success', 'deny click', 'deny nested spawn'],
      parentRunId: 'parent-batch',
      dom: { snapshot: async () => ({ ok: true, data: snap }) } as DomPlane,
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm' },
      maxSteps: 1,
      onLeafRecord: (record) => records.push(record),
      onTokenUsage: (usage) => {
        charged += usage.totalTokens
      },
    })
    assert(batch.children.length === 3, 'three bounded child briefs produce three results')
    assert(new Set(batch.children.map((child) => child.runId)).size === 3, 'child run ids are unique')
    assert(
      records.every((record) => record.parentRunId === 'parent-batch'),
      'child records retain their parent run id'
    )
    assert(batch.children.some((child) => child.status === 'done'), 'successful child survives sibling failures')
    assert(
      batch.children.filter((child) => child.status !== 'done').length === 2,
      'denied DOM and nested spawn become independent child failures'
    )
    assert(
      records.some(
        (record) =>
          record.type === 'tool.result' &&
          record.payload.error?.code === 'capability_denied' &&
          (record.payload.tool === 'dom_click' || record.payload.tool === 'system_spawn_readonly_tasks')
      ),
      'readonly profile hard-denies DOM writes and nested spawn'
    )
    assert(charged === 15, 'child token usage is charged to the parent callback')
  } finally {
    globalThis.fetch = prevFetch
  }
}

{
  const records: import('@naviforge/session').TraceRecord[] = []
  const calls: string[] = []
  const prevFetch = globalThis.fetch
  globalThis.fetch = (async (_url: RequestInfo | URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body ?? '{}')) as { messages?: Array<{ content?: string }> }
    const user = body.messages?.[1]?.content ?? ''
    const tool = user.includes('unmarked MCP') ? 'mcp__docs__unsafe' : 'mcp__docs__safe'
    return new Response(JSON.stringify({ choices: [mockLlmChoice({ tool, arguments: {} })] }), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }) as typeof fetch
  try {
    await runReadonlySubAgents({
      briefs: ['unmarked MCP', 'marked MCP'],
      parentRunId: 'parent-readonly-mcp',
      dom: { snapshot: async () => ({ ok: true, data: snap }) } as DomPlane,
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm' },
      maxSteps: 1,
      mcpTools: [
        { serverId: 'docs', serverName: 'Docs', name: 'unsafe', inputSchema: { type: 'object' } },
        { serverId: 'docs', serverName: 'Docs', name: 'safe', inputSchema: { type: 'object' }, readonly: true },
      ],
      callMcpTool: async (_serverId, tool) => {
        calls.push(tool)
        return { ok: true, data: { result: 'safe' } }
      },
      onLeafRecord: (record) => records.push(record),
    })
    assert(calls.join(',') === 'safe', 'only readonly MCP tools reach the host callback')
    assert(
      records.some(
        (record) =>
          record.type === 'tool.result' &&
          record.payload.tool === 'mcp__docs__unsafe' &&
          record.payload.error?.code === 'capability_denied'
      ),
      'unmarked MCP tool is denied in readonly child'
    )
  } finally {
    globalThis.fetch = prevFetch
  }
}

{
  const controller = new AbortController()
  const prevFetch = globalThis.fetch
  globalThis.fetch = ((_url: RequestInfo | URL, init?: RequestInit) =>
    new Promise<Response>((_resolve, reject) => {
      init?.signal?.addEventListener(
        'abort',
        () => reject(new DOMException('Aborted', 'AbortError')),
        { once: true }
      )
      controller.abort()
    })) as typeof fetch
  try {
    let cancelled = false
    try {
      await runReadonlySubAgents({
        briefs: ['cancel child'],
        parentRunId: 'parent-cancel',
        dom: { snapshot: async () => ({ ok: true, data: snap }) } as DomPlane,
        llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm' },
        signal: controller.signal,
      })
    } catch (error) {
      cancelled = isAbortError(error)
    }
    assert(cancelled, 'parent cancellation propagates instead of returning an aggregate')
  } finally {
    globalThis.fetch = prevFetch
  }
}

{
  const records: import('@naviforge/session').TraceRecord[] = []
  let parentTurns = 0
  const prevFetch = globalThis.fetch
  globalThis.fetch = (async (_url: RequestInfo | URL, init?: RequestInit) => {
    const body = JSON.parse(String(init?.body ?? '{}')) as {
      messages?: Array<{ content?: string }>
    }
    const user = body.messages?.[1]?.content ?? ''
    const call = user.includes('parent aggregate')
      ? parentTurns++ === 0
        ? { tool: 'system_spawn_readonly_tasks', arguments: { briefs: ['good child', 'failed child'] } }
        : { tool: 'system_done', arguments: { result: 'parent complete' } }
      : user.includes('failed child')
        ? { tool: 'dom_click', arguments: { index: 1, revision: 1 } }
        : { tool: 'system_done', arguments: { result: 'child complete' } }
    return new Response(
      JSON.stringify({
        choices: [mockLlmChoice(call)],
        usage: { prompt_tokens: 1, completion_tokens: 1, total_tokens: 2 },
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } }
    )
  }) as typeof fetch
  try {
    await runAgent({       task: 'parent aggregate',
      runId: 'parent-aggregate',
      maxSteps: 2,
      dom: { snapshot: async () => ({ ok: true, data: snap }) } as DomPlane,
      llm: { baseURL: 'https://example.test/v1', apiKey: 'k', model: 'm' },
      onRecord: (record) => records.push(record),
    })
    const aggregate = records.find(
      (record) => record.type === 'tool.result' && record.payload.tool === 'system_spawn_readonly_tasks'
    )
    const data = aggregate?.type === 'tool.result' ? (aggregate.payload.data as { ok?: boolean; children?: unknown[] }) : undefined
    assert(data?.ok === false && data.children?.length === 2, 'parent receives one aggregate with success and failure')
    assert(
      records.some((record) => record.type === 'metrics.tokens' && record.runId === 'parent-aggregate'),
      'child tokens are included in parent token accounting'
    )
  } finally {
    globalThis.fetch = prevFetch
  }
}

console.log('runtime self-check ok')
