import { resolveBuiltinToolCall } from '../builtin-tool-resolver.js'
import { INJECT_SCRIPT_DENIED } from '@naviforge/shared'
import type { ToolResult } from '@naviforge/shared'
import type { RecordedDomAction } from '@naviforge/playbook'
import { evaluateAskUser, isLikelyNavigationClick } from '@naviforge/policy'

import { isCspEvalError } from '../../run-limits.js'
import { workspaceFail } from './workspace.js'
import {
  handlerPrelude,
  networkAfter,
  normalizeScrollArgs,
  parseSnapshotMode,
  withStaleRevisionRetry,
} from './prelude.js'
import type { BuiltinHandler } from './types.js'
import { num, str } from './types.js'
import { throttlePageNavigation } from '../../page-friction/throttle.js'

const dom_snapshot: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  const mode = parseSnapshotMode(action.arguments.mode)
  result = await dom.snapshot(mode ? { mode } : undefined)
  return { result, snap, recorded }
}

const dom_click: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  const index = num(action.arguments.index)
  const selector = str(action.arguments.selector)
  const framePath = str(action.arguments.framePath) ?? undefined
  if (index === null && !selector) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'index or selector required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  if (
    index !== null &&
    taskScope.navigation === 'forbidden' &&
    isLikelyNavigationClick(snap, index)
  ) {
    result = {
      ok: false,
      error: {
        code: 'scope_locked',
        message: `Click on [${index}] looks like site navigation — use dom_mark_topn or dom_highlight on content items instead`,
        recoverable: true,
      },
    }
    return { result, snap, recorded }
  }
  {
    const startedAt = Date.now()
    if (index !== null) {
      const retried = await withStaleRevisionRetry(dom, snap, (revision) =>
        dom.click(index, revision, framePath)
      )
      result = retried.result
      snap = retried.snap
    } else {
      result = {
        ok: false,
        error: { code: 'bad_args', message: 'index required', recoverable: true },
      }
    }
    if (!result.ok && selector && dom.clickSelector && !framePath) {
      const bySelector = await dom.clickSelector(selector)
      if (bySelector.ok) result = bySelector
    }
    if (result.ok) {
      const locator =
        index !== null ? await dom.selector(index, snap.revision) : { ok: false as const }
      recorded = {
        tool: 'dom_click',
        index: index ?? 0,
        selector: locator.ok ? locator.data.selector : selector ?? undefined,
        network: await networkAfter(network, startedAt),
      }
    }
  }
  return { result, snap, recorded }
}

const dom_type: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  const index = num(action.arguments.index)
  const text = str(action.arguments.text)
  const selector = str(action.arguments.selector)
  if ((index === null && !selector) || text === null) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'index+text or selector+text required', recoverable: true },
    }
  } else {
    if (index !== null) {
      const retried = await withStaleRevisionRetry(dom, snap, (revision) =>
        dom.type(index, text, revision)
      )
      result = retried.result
      snap = retried.snap
    } else {
      result = {
        ok: false,
        error: { code: 'bad_args', message: 'index required', recoverable: true },
      }
    }
    if (!result.ok && selector && dom.typeSelector) {
      const bySelector = await dom.typeSelector(selector, text)
      if (bySelector.ok) result = bySelector
    }
    if (result.ok) {
      const locator =
        index !== null ? await dom.selector(index, snap.revision) : { ok: false as const }
      recorded = {
        tool: 'dom_type',
        index: index ?? 0,
        text,
        selector: locator.ok ? locator.data.selector : selector ?? undefined,
      }
    }
  }
  return { result, snap, recorded }
}

const dom_highlight: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.highlight) {
    result = {
      ok: false,
      error: { code: 'no_highlight', message: 'highlight unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const rawTargets = action.arguments.targets
  if (!Array.isArray(rawTargets) || !rawTargets.length) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'targets array required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  const targets = rawTargets
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      index: typeof item.index === 'number' ? item.index : undefined,
      selector: typeof item.selector === 'string' ? item.selector : undefined,
      label: String(item.label ?? ''),
      color: typeof item.color === 'string' ? item.color : undefined,
    }))
    .filter((item) => item.label && (item.index != null || item.selector))
  {
    const retried = await withStaleRevisionRetry(dom, snap, (revision) =>
      dom.highlight!(targets, revision)
    )
    result = retried.result
    snap = retried.snap
  }
  return { result, snap, recorded }
}

const dom_mark_topn: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.markTopn) {
    result = {
      ok: false,
      error: { code: 'no_mark_topn', message: 'mark_topn unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const n = Math.min(12, Math.max(1, Math.floor(num(action.arguments.n) ?? 4)))
  let marked = await dom.markTopn(n)
  if (marked.ok && marked.data.marked === 0 && dom.scroll && dom.wait) {
    ctx.emit?.(
      ctx.createRecord('run.recovery', {
        strategy: 'reobserve_and_replan',
        diagnostic: `mark_topn found 0 items from ${marked.data.candidates} candidates`,
      })
    )
    await dom.scroll({ y: 480 })
    await dom.wait({ kind: 'stable', timeoutMs: 2500 })
    marked = await dom.markTopn(n)
  }
  result = marked
  return { result, snap, recorded }
}

const dom_extract_content: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.extractContent) {
    result = {
      ok: false,
      error: {
        code: 'no_extract_content',
        message: 'extract_content unsupported',
        recoverable: false,
      },
    }
    return { result, snap, recorded }
  }
  const n = Math.min(48, Math.max(1, Math.floor(num(action.arguments.n) ?? 8)))
  let extracted = await dom.extractContent(n)
  if (extracted.ok && !extracted.data.items.length && dom.scroll && dom.wait) {
    ctx.emit?.(
      ctx.createRecord('run.recovery', {
        strategy: 'reobserve_and_replan',
        diagnostic: `extract_content found 0 records from ${extracted.data.candidates} candidates`,
      })
    )
    await dom.scroll({ y: 480 })
    await dom.wait({ kind: 'stable', timeoutMs: 2500 })
    extracted = await dom.extractContent(n)
  }
  result = extracted
  return { result, snap, recorded }
}

const dom_mark_items: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.markItems) {
    result = {
      ok: false,
      error: { code: 'no_mark_items', message: 'mark_items unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const items = Array.isArray(action.arguments.items)
    ? (action.arguments.items as Array<Record<string, unknown>>)
        .map((item) => ({
          index: num(item.index) ?? -1,
          label: str(item.label) ?? undefined,
          detail: str(item.detail) ?? undefined,
        }))
        .filter((item) => item.index > 0)
    : []
  result = items.length
    ? await dom.markItems(items)
    : {
        ok: false,
        error: {
          code: 'bad_args',
          message: 'items required — call dom_extract_content first',
          recoverable: true,
        },
      }
  return { result, snap, recorded }
}

const dom_clear_highlights: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  result = dom.clearHighlights
    ? await dom.clearHighlights()
    : {
        ok: false,
        error: { code: 'no_highlight', message: 'clearHighlights unsupported', recoverable: false },
      }
  return { result, snap, recorded }
}

const dom_inject: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.inject) {
    result = {
      ok: false,
      error: { code: 'no_inject', message: 'inject unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const kind = str(action.arguments.kind)
  const code = str(action.arguments.code)
  if (!kind || !code || !['css', 'html', 'script'].includes(kind)) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'kind(css|html|script)+code required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  if (kind === 'script' && !allowDomInject) {
    result = {
      ok: false,
      error: {
        code: 'inject_denied',
        message: INJECT_SCRIPT_DENIED,
        recoverable: false,
      },
    }
    return { result, snap, recorded }
  }
  result = await dom.inject({
    kind: kind as 'css' | 'html' | 'script',
    code,
    allowScript: allowDomInject,
  })
  return { result, snap, recorded }
}

const dom_execute_js: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.executeJs) {
    result = {
      ok: false,
      error: { code: 'no_execute_js', message: 'execute_js unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const code = str(action.arguments.code) || str(action.arguments.expression)
  if (!code) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'code required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  const timeoutMs = num(action.arguments.timeout_ms)
  result = await dom.executeJs({
    code,
    timeoutMs: timeoutMs != null ? Math.min(30_000, Math.max(1000, timeoutMs)) : undefined,
    allowScript: true,
  })
  if (!result.ok && isCspEvalError(result.error.message)) {
    result = {
      ok: false,
      error: {
        code: 'csp_eval_blocked',
        message: result.error.message,
        recoverable: false,
      },
    }
  }
  return { result, snap, recorded }
}

const dom_extract_dom: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.extractDom) {
    result = {
      ok: false,
      error: { code: 'no_extract_dom', message: 'extract_dom unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const kindRaw = str(action.arguments.kind)
  const kind =
    kindRaw === 'links' || kindRaw === 'buttons' || kindRaw === 'feeds' ? kindRaw : 'all'
  const limit = num(action.arguments.limit)
  result = await dom.extractDom({
    kind,
    limit: limit != null ? Math.min(96, Math.max(1, Math.floor(limit))) : undefined,
  })
  return { result, snap, recorded }
}

const dom_navigate: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (taskScope.navigation === 'forbidden') {
    result = {
      ok: false,
      error: {
        code: 'scope_locked',
        message: 'Current-page task forbids navigation',
        recoverable: true,
      },
    }
    return { result, snap, recorded }
  }
  if (!dom.navigate) {
    result = {
      ok: false,
      error: { code: 'no_navigate', message: 'navigate unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const navAction = str(action.arguments.action)
  if (!navAction || !['back', 'forward', 'reload', 'url'].includes(navAction)) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'action(back|forward|reload|url) required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  if (navAction === 'url' && !str(action.arguments.url)) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'url required for action=url', recoverable: true },
    }
    return { result, snap, recorded }
  }
  await throttlePageNavigation()
  result = await dom.navigate(
    navAction as 'back' | 'forward' | 'reload' | 'url',
    str(action.arguments.url) ?? undefined
  )
  return { result, snap, recorded }
}

const dom_scroll: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.scroll) {
    result = {
      ok: false,
      error: { code: 'no_scroll', message: 'scroll unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const scrollArgs = normalizeScrollArgs(action.arguments)
  result = await dom.scroll(scrollArgs)
  return { result, snap, recorded }
}

const dom_read_page: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.readPage) {
    result = {
      ok: false,
      error: { code: 'no_read_page', message: 'read_page unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const timeoutMs = num(action.arguments.timeout_ms)
  result = await dom.readPage(timeoutMs != null ? { timeoutMs } : undefined)
  return { result, snap, recorded }
}

const dom_wait: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.wait) {
    result = {
      ok: false,
      error: { code: 'no_wait', message: 'wait unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const kind = str(action.arguments.kind)
  if (!kind || !['stable', 'text', 'network_idle', 'download'].includes(kind)) {
    result = {
      ok: false,
      error: {
        code: 'bad_args',
        message: 'kind(stable|text|network_idle|download) required',
        recoverable: true,
      },
    }
    return { result, snap, recorded }
  }
  result = await dom.wait({
    kind: kind as 'stable' | 'text' | 'network_idle' | 'download',
    text: str(action.arguments.text) ?? undefined,
    timeoutMs: num(action.arguments.timeout_ms) ?? 10000,
  })
  return { result, snap, recorded }
}

const dom_press: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.press) {
    result = {
      ok: false,
      error: { code: 'no_press', message: 'press unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const key = str(action.arguments.key)
  if (!key) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'key required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  const modifiers = Array.isArray(action.arguments.modifiers)
    ? action.arguments.modifiers.filter((value): value is string => typeof value === 'string')
    : undefined
  result = await dom.press(key, modifiers)
  return { result, snap, recorded }
}

const dom_select: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.select) {
    result = {
      ok: false,
      error: { code: 'no_select', message: 'select unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const index = num(action.arguments.index)
  const value = str(action.arguments.value)
  const revision = num(action.arguments.revision) ?? snap.revision
  if (index === null || !value) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'index+value+revision required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  {
    const retried = await withStaleRevisionRetry(dom, snap, (revision) =>
      dom.select!(index, value, revision)
    )
    result = retried.result
    snap = retried.snap
  }
  return { result, snap, recorded }
}

const dom_check: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.check) {
    result = {
      ok: false,
      error: { code: 'no_check', message: 'check unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const index = num(action.arguments.index)
  const revision = num(action.arguments.revision) ?? snap.revision
  if (index === null || typeof action.arguments.checked !== 'boolean') {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'index+checked+revision required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  {
    const retried = await withStaleRevisionRetry(dom, snap, (revision) =>
      dom.check!(index, action.arguments.checked === true, revision)
    )
    result = retried.result
    snap = retried.snap
  }
  return { result, snap, recorded }
}

const dom_upload: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.upload) {
    result = {
      ok: false,
      error: { code: 'no_upload', message: 'upload unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const index = num(action.arguments.index)
  const filename = str(action.arguments.filename)
  const contentBase64 = str(action.arguments.content_base64)
  const revision = num(action.arguments.revision) ?? snap.revision
  if (index === null || !filename || !contentBase64) {
    result = {
      ok: false,
      error: {
        code: 'bad_args',
        message: 'index+filename+content_base64+revision required',
        recoverable: true,
      },
    }
    return { result, snap, recorded }
  }
  {
    const retried = await withStaleRevisionRetry(dom, snap, (revision) =>
      dom.upload!(index, filename, contentBase64, revision)
    )
    result = retried.result
    snap = retried.snap
  }
  return { result, snap, recorded }
}

const dom_hover: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.hover) {
    result = {
      ok: false,
      error: { code: 'no_hover', message: 'hover unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const index = num(action.arguments.index)
  const revision = num(action.arguments.revision) ?? snap.revision
  if (index === null) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'index+revision required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  {
    const retried = await withStaleRevisionRetry(dom, snap, (revision) => dom.hover!(index, revision))
    result = retried.result
    snap = retried.snap
  }
  return { result, snap, recorded }
}

const dom_drag: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.drag) {
    result = {
      ok: false,
      error: { code: 'no_drag', message: 'drag unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const fromIndex = num(action.arguments.from_index)
  const toIndex = num(action.arguments.to_index)
  const revision = num(action.arguments.revision) ?? snap.revision
  if (fromIndex === null || toIndex === null) {
    result = {
      ok: false,
      error: { code: 'bad_args', message: 'from_index+to_index+revision required', recoverable: true },
    }
    return { result, snap, recorded }
  }
  {
    const retried = await withStaleRevisionRetry(dom, snap, (revision) =>
      dom.drag!(fromIndex, toIndex, revision)
    )
    result = retried.result
    snap = retried.snap
  }
  return { result, snap, recorded }
}
const dom_screenshot: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.screenshot) {
    result = {
      ok: false,
      error: { code: 'no_screenshot', message: 'screenshot unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  const shot = await dom.screenshot()
  if (!shot.ok) {
    result = shot
    return { result, snap, recorded }
  }
  if (ctx.visionShot) ctx.visionShot.dataUrl = shot.data.dataUrl
  if (workspace) {
    try {
      const saved = await workspace.saveShot({
        kind: 'visible',
        dataUrl: shot.data.dataUrl,
        threadId: ctx.workspaceThread?.threadId,
        slug: ctx.workspaceThread?.slug,
        title: ctx.workspaceThread?.title,
        runId: ctx.workspaceThread?.runId,
        tool: 'dom_screenshot',
      })
      result = { ok: true, data: { path: saved.relativePath } }
    } catch (error) {
      result = {
        ok: false,
        error: {
          code: 'shot_not_saved',
          message: (error as Error).message,
          recoverable: true,
        },
      }
    }
  } else {
    result = shot
  }
  return { result, snap, recorded }
}

const page_to_markdown: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.toMarkdown) {
    result = {
      ok: false,
      error: { code: 'no_to_markdown', message: 'to_markdown unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  if (!workspace) {
    result = workspaceFail('no_workspace', '本机工作区未连接')
    return { result, snap, recorded }
  }
  const converted = await dom.toMarkdown()
  if (!converted.ok) {
    result = converted
    return { result, snap, recorded }
  }
  try {
    const saved = await workspace.savePage({
      kind: 'md',
      content: converted.data.markdown,
      slug: converted.data.title,
    })
    result = {
      ok: true,
      data: {
        path: saved.relativePath,
        title: converted.data.title,
        url: converted.data.url,
        source: converted.data.source,
        chars: converted.data.markdown.length,
        bytes: saved.bytes,
        excerpt:
          converted.data.markdown.length > 800
            ? `${converted.data.markdown.slice(0, 800)}\n… (truncated)`
            : converted.data.markdown,
      },
    }
  } catch (error) {
    result = workspaceFail('page_not_saved', (error as Error).message)
  }
  return { result, snap, recorded }
}

const page_to_pdf: BuiltinHandler = async (input) => {
  const { turn, action, ctx, blockAsk, dom, network, tabs, scripts, taskScope, callMcpTool, mcpTools, allowDomInject, allowNetworkIntercept, skills, search, workspace } = handlerPrelude(input)
  let snap = input.snap
  let result: ToolResult
  let recorded: RecordedDomAction | undefined
  
  if (!dom.toPdf) {
    result = {
      ok: false,
      error: { code: 'no_to_pdf', message: 'to_pdf unsupported', recoverable: false },
    }
    return { result, snap, recorded }
  }
  if (!workspace) {
    result = workspaceFail('no_workspace', '本机工作区未连接')
    return { result, snap, recorded }
  }
  const printed = await dom.toPdf()
  if (!printed.ok) {
    result = printed
    return { result, snap, recorded }
  }
  try {
    const saved = await workspace.savePage({
      kind: 'pdf',
      dataUrl: printed.data.dataUrl,
      slug: printed.data.title,
    })
    result = {
      ok: true,
      data: {
        path: saved.relativePath,
        title: printed.data.title,
        url: printed.data.url,
        bytes: saved.bytes,
      },
    }
  } catch (error) {
    result = workspaceFail('page_not_saved', (error as Error).message)
  }
  return { result, snap, recorded }
}


export const domHandlers = {
  dom_snapshot,
  dom_click,
  dom_type,
  dom_highlight,
  dom_mark_topn,
  dom_extract_content,
  dom_mark_items,
  dom_clear_highlights,
  dom_inject,
  dom_execute_js,
  dom_extract_dom,
  dom_navigate,
  dom_scroll,
  dom_read_page,
  dom_wait,
  dom_press,
  dom_select,
  dom_check,
  dom_upload,
  dom_hover,
  dom_drag,
  dom_screenshot,
  page_to_markdown,
  page_to_pdf,
} as const satisfies Record<string, BuiltinHandler>

export const domCatalogHandler: BuiltinHandler = async (input) => {
  const mode = input.action.arguments.mode
  if (typeof mode !== 'string') {
    return {
      result: {
        ok: false,
        error: {
          code: 'bad_args',
          message: 'dom mode required (body|list|dom|markdown)',
          recoverable: true,
        },
      },
      snap: input.snap,
    }
  }
  const resolved = resolveBuiltinToolCall('dom_read', input.action.arguments)
  const handler = domHandlers[resolved.tool as keyof typeof domHandlers]
  if (!handler) {
    return {
      result: {
        ok: false,
        error: { code: 'bad_args', message: `unknown dom mode: ${mode}`, recoverable: true },
      },
      snap: input.snap,
    }
  }
  return handler({
    ...input,
    action: { ...input.action, tool: resolved.tool, arguments: resolved.arguments },
  })
}
