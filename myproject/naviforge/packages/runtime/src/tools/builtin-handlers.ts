import { AGENT_TOOL_IDS } from '@naviforge/shared'
import { extractPageList } from '@naviforge/extract'
import { mediaHintsFromUrls, type MediaHint } from '@naviforge/media-plane'
import type { RecordedDomAction } from '@naviforge/playbook'
import { findSkill, loadSkillBody, type Skill } from '@naviforge/skill-runtime'

import { scopeTabsToRun } from '../loop-gate-state.js'
import { runReadonlySubAgents } from '../readonly-agent.js'
import { normalizeSpawnBriefs } from '../subtask-guidance.js'
import type { ScriptLanguage } from '../script-plane.js'
import { ToolRegistry } from './registry.js'
import { resolveBuiltinToolCall } from './builtin-tool-resolver.js'
import { domCatalogHandler, domHandlers } from './handlers/dom.js'
import { networkCatalogHandler, networkHandlers } from './handlers/network.js'
import { handlerPrelude } from './handlers/prelude.js'
import type { BuiltinContext, BuiltinHandler, BuiltinResult } from './handlers/types.js'
import { num, str } from './handlers/types.js'
import { workspaceCatalogHandler, workspaceHandlers } from './handlers/workspace.js'

const tabsList: BuiltinHandler = async (input) => {
  const { tabs, ctx } = handlerPrelude(input)
  const snap = input.snap
  if (!tabs) {
    return {
      result: { ok: false, error: { code: 'no_tabs', message: 'tabs plane unavailable', recoverable: false } },
      snap,
    }
  }
  const listed = await tabs.list()
  if (!listed.ok) return { result: listed, snap }
  const scoped = scopeTabsToRun(listed.data.tabs, ctx.gates, ctx.anchorTabId)
  return {
    result: {
      ok: true,
      data: {
        tabs: scoped.tabs,
        scoped: scoped.scoped,
        totalBrowserTabs: scoped.totalBrowserTabs,
        hint: scoped.hint,
      },
    },
    snap,
  }
}

const tabsSwitch: BuiltinHandler = async (input) => {
  const { tabs, action } = handlerPrelude(input)
  let snap = input.snap
  if (!tabs) {
    return {
      result: { ok: false, error: { code: 'no_tabs', message: 'tabs plane unavailable', recoverable: false } },
      snap,
    }
  }
  const tabId = num(action.arguments.tab_id)
  if (tabId === null) {
    return {
      result: { ok: false, error: { code: 'bad_args', message: 'tab_id required', recoverable: true } },
      snap,
    }
  }
  return { result: await tabs.switch(tabId), snap }
}

const tabsClose: BuiltinHandler = async (input) => {
  const { tabs, action } = handlerPrelude(input)
  let snap = input.snap
  if (!tabs) {
    return {
      result: { ok: false, error: { code: 'no_tabs', message: 'tabs plane unavailable', recoverable: false } },
      snap,
    }
  }
  const tabId = num(action.arguments.tab_id)
  if (tabId === null) {
    return {
      result: { ok: false, error: { code: 'bad_args', message: 'tab_id required', recoverable: true } },
      snap,
    }
  }
  return { result: await tabs.close(tabId), snap }
}

const tabsOpen: BuiltinHandler = async (input) => {
  const { tabs, action } = handlerPrelude(input)
  let snap = input.snap
  if (!tabs?.open) {
    return {
      result: { ok: false, error: { code: 'no_tabs', message: 'tabs_open unavailable', recoverable: false } },
      snap,
    }
  }
  const url = str(action.arguments.url)
  if (!url) {
    return {
      result: { ok: false, error: { code: 'bad_args', message: 'url required', recoverable: true } },
      snap,
    }
  }
  return { result: await tabs.open(url), snap }
}

const webSearch: BuiltinHandler = async (input) => {
  const { search, action } = handlerPrelude(input)
  let snap = input.snap
  if (!search) {
    return {
      result: { ok: false, error: { code: 'no_search', message: 'web_search unavailable', recoverable: false } },
      snap,
    }
  }
  const query = str(action.arguments.query)?.trim()
  if (!query) {
    return {
      result: { ok: false, error: { code: 'bad_args', message: 'query required', recoverable: true } },
      snap,
    }
  }
  const n = num(action.arguments.n)
  return { result: await search.search(query, n ?? undefined), snap }
}

const fetchText: BuiltinHandler = async (input) => {
  const { fetch, action } = handlerPrelude(input)
  let snap = input.snap
  if (!fetch) {
    return {
      result: { ok: false, error: { code: 'no_fetch', message: 'fetch_text unavailable', recoverable: false } },
      snap,
    }
  }
  const maxChars = num(action.arguments.max_chars)
  const rawUrls = action.arguments.urls
  if (Array.isArray(rawUrls)) {
    const urls = rawUrls.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
    if (!urls.length || urls.length > 10) {
      return {
        result: {
          ok: false,
          error: {
            code: 'bad_args',
            message: 'urls must contain 1–10 non-empty HTTPS URLs',
            recoverable: true,
          },
        },
        snap,
      }
    }
    const items = await Promise.all(
      urls.map(async (url) => {
        const result = await fetch.fetchText(url, maxChars ?? undefined)
        return result.ok
          ? { url, ok: true as const, ...result.data }
          : { url, ok: false as const, error: result.error }
      })
    )
    const okCount = items.filter((item) => item.ok).length
    return {
      result: {
        ok: okCount > 0,
        data: { items, okCount, n: items.length },
        ...(okCount === 0
          ? {
              error: {
                code: 'fetch_failed',
                message: items.find((item) => item.ok === false && 'error' in item && item.error)?.error?.message ?? 'all fetches failed',
                recoverable: true,
              },
            }
          : {}),
      },
      snap,
    }
  }
  const url = str(action.arguments.url)
  if (!url) {
    return {
      result: { ok: false, error: { code: 'bad_args', message: 'url or urls required', recoverable: true } },
      snap,
    }
  }
  return { result: await fetch.fetchText(url, maxChars ?? undefined), snap }
}

const scriptSave: BuiltinHandler = async (input) => {
  const { scripts, action } = handlerPrelude(input)
  const snap = input.snap
  if (!scripts) {
    return {
      result: { ok: false, error: { code: 'no_script_plane', message: 'script storage unavailable', recoverable: false } },
      snap,
    }
  }
  const title = str(action.arguments.title)
  const filename = str(action.arguments.filename)
  const content = str(action.arguments.content)
  const language = str(action.arguments.language)
  if (!title || !filename || !content || !['python', 'shell', 'javascript'].includes(language ?? '')) {
    return {
      result: { ok: false, error: { code: 'bad_args', message: 'title, filename, language, content required', recoverable: true } },
      snap,
    }
  }
  if (content.length > 100_000) {
    return {
      result: { ok: false, error: { code: 'script_too_large', message: 'script exceeds 100KB', recoverable: true } },
      snap,
    }
  }
  return {
    result: await scripts.save({
      title,
      filename,
      content,
      language: language as ScriptLanguage,
      sourceUrl: snap.url,
    }),
    snap,
  }
}

const scriptDownload: BuiltinHandler = async (input) => {
  const { scripts, action } = handlerPrelude(input)
  let snap = input.snap
  const id = str(action.arguments.id)
  if (!scripts?.download || !id) {
    return {
      result: { ok: false, error: { code: 'bad_args', message: 'saved script id required', recoverable: true } },
      snap,
    }
  }
  return { result: await scripts.download(id), snap }
}

const skillLoad: BuiltinHandler = async (input) => {
  const { skills, action } = handlerPrelude(input)
  let snap = input.snap
  const id = str(action.arguments.id)
  if (!id) {
    return {
      result: { ok: false, error: { code: 'bad_args', message: 'id required', recoverable: true } },
      snap,
    }
  }
  const catalog: Skill[] = (skills ?? []).map((item) => ({
    manifest: {
      id: item.id,
      version: item.version,
      description: item.description,
      permissions: item.tools?.length ? { tools: item.tools } : undefined,
    },
    instructions: item.instructions,
    files: item.files,
  }))
  const body = loadSkillBody(catalog, id)
  const skill = findSkill(catalog, id)
  if (!body || !skill) {
    return {
      result: {
        ok: false,
        error: {
          code: 'skill_not_found',
          message: `skill "${id}" is not installed or not enabled for this run`,
          recoverable: true,
        },
      },
      snap,
    }
  }
  return {
    result: {
      ok: true,
      data: { id: skill.manifest.id, version: skill.manifest.version, body, files: skill.files ?? [] },
    },
    snap,
  }
}

const systemDone: BuiltinHandler = async (input) => {
  const { ctx, action } = handlerPrelude(input)
  const snap = input.snap
  const r = str(action.arguments.result) ?? ''
  return { nextSnap: snap, trace: `done: ${r}`, terminal: ctx.createRecord('run.result', { text: r }) }
}

const domProbe: BuiltinHandler = async (input) => {
  const { ctx, action } = handlerPrelude(input)
  let snap = input.snap
  const expression = str(action.arguments.expression)
  if (!ctx.mainProbe) {
    return {
      result: {
        ok: false,
        error: {
          code: 'probe_denied',
          message: 'MAIN world 探测未开启 — 到控制台 → 隐私与数据，打开「允许 MAIN world 只读探测」并保存',
          recoverable: false,
        },
      },
      snap,
    }
  }
  if (!expression || expression.length > 500) {
    return {
      result: { ok: false, error: { code: 'bad_args', message: 'expression required (max 500 chars)', recoverable: true } },
      snap,
    }
  }
  return { result: await ctx.mainProbe(expression), snap }
}

const systemExtractPage: BuiltinHandler = async (input) => {
  const { dom, network } = handlerPrelude(input)
  let snap = input.snap
  let mediaHints: MediaHint[] = []
  const jsonPreviews: Array<{ url: string; preview: string }> = []
  if (network) {
    const listed = await network.list({ limit: 80 })
    if (listed.ok) {
      mediaHints = mediaHintsFromUrls(listed.data)
      for (const event of listed.data) {
        if (event.bodyPreview) jsonPreviews.push({ url: event.url, preview: event.bodyPreview })
      }
    }
  }
  const items = extractPageList({
    snapshotContent: snap.content,
    frames: snap.frames,
    mediaHints,
    jsonPreviews,
  })
  return { result: { ok: true, data: { items, count: items.length } }, snap }
}

const systemCaptchaWait: BuiltinHandler = async (input) => {
  const { ctx, action } = handlerPrelude(input)
  const snap = input.snap
  const hint = str(action.arguments.hint) ?? 'Complete the CAPTCHA in the page, then reply when done.'
  const terminal = ctx.createRecord('run.ask', { question: hint, wait: 'captcha' })
  ctx.emit?.(terminal)
  return { nextSnap: snap, trace: `captcha: ${hint}`, terminal }
}

const systemAskUser: BuiltinHandler = async (input) => {
  const { ctx, action, blockAsk } = handlerPrelude(input)
  const snap = input.snap
  const q = str(action.arguments.question) ?? ''
  const blocked = blockAsk(q)
  if (blocked) return blocked
  return {
    nextSnap: snap,
    trace: `ask: ${q}`,
    terminal: ctx.createRecord('run.ask', { question: q, wait: 'user' }),
  }
}

const systemSpawnReadonlyTasks: BuiltinHandler = async (input) => {
  const { ctx, action, dom, network, callMcpTool, mcpTools, search, fetch } = handlerPrelude(input)
  let snap = input.snap
  const normalized = normalizeSpawnBriefs(action.arguments as Record<string, unknown>)
  if ('error' in normalized) {
    return {
      result: {
        ok: false,
        error: { code: 'bad_args', message: normalized.error, recoverable: true },
      },
      snap,
    }
  }
  const { briefs } = normalized
  const subResult = await runReadonlySubAgents({
    briefs,
    parentRunId: ctx.runId,
    parentSessionId: ctx.parentSessionId,
    anchorTabId: ctx.anchorTabId,
    createLeafPlanes: ctx.createLeafPlanes,
    onLeafRecord: ctx.onLeafRecord,
    onLeafSessionStart: ctx.onLeafSessionStart,
    onLeafSessionComplete: ctx.onLeafSessionComplete,
    dom,
    llm: ctx.llm,
    network,
    mcpTools,
    callMcpTool,
    search,
    fetch,
    signal: ctx.signal,
    onTokenUsage: ctx.chargeTokens,
  })
  return {
    result: {
      ok: true,
      data: {
        children: subResult.children,
        ok: subResult.children.every((child) => child.status === 'done'),
      },
    },
    snap,
  }
}

export const BUILTIN_TOOL_REGISTRY = new ToolRegistry<BuiltinContext, BuiltinResult>()
  .register('dom_snapshot', domHandlers.dom_snapshot)
  .register('dom_click', domHandlers.dom_click)
  .register('dom_type', domHandlers.dom_type)
  .register('dom_highlight', domHandlers.dom_highlight)
  .register('dom_mark_topn', domHandlers.dom_mark_topn)
  .register('dom_extract_content', domHandlers.dom_extract_content)
  .register('dom_mark_items', domHandlers.dom_mark_items)
  .register('dom_clear_highlights', domHandlers.dom_clear_highlights)
  .register('dom_inject', domHandlers.dom_inject)
  .register('dom_execute_js', domHandlers.dom_execute_js)
  .register('dom_extract_dom', domHandlers.dom_extract_dom)
  .register('dom_navigate', domHandlers.dom_navigate)
  .register('dom_scroll', domHandlers.dom_scroll)
  .register('dom_read_page', domHandlers.dom_read_page)
  .register('dom_wait', domHandlers.dom_wait)
  .register('dom_press', domHandlers.dom_press)
  .register('dom_select', domHandlers.dom_select)
  .register('dom_check', domHandlers.dom_check)
  .register('dom_upload', domHandlers.dom_upload)
  .register('dom_hover', domHandlers.dom_hover)
  .register('dom_drag', domHandlers.dom_drag)
  .register('tabs_list', tabsList)
  .register('tabs_switch', tabsSwitch)
  .register('tabs_close', tabsClose)
  .register('tabs_open', tabsOpen)
  .register('web_search', webSearch)
  .register('fetch_text', fetchText)
  .register('script_save', scriptSave)
  .register('script_download', scriptDownload)
  .register('workspace_ls', workspaceHandlers.workspace_ls)
  .register('workspace_read', workspaceHandlers.workspace_read)
  .register('workspace_write', workspaceHandlers.workspace_write)
  .register('workspace_mkdir', workspaceHandlers.workspace_mkdir)
  .register('workspace_touch', workspaceHandlers.workspace_touch)
  .register('workspace_stat', workspaceHandlers.workspace_stat)
  .register('workspace_glob', workspaceHandlers.workspace_glob)
  .register('workspace_grep', workspaceHandlers.workspace_grep)
  .register('workspace', workspaceCatalogHandler)
  .register('dom_screenshot', domHandlers.dom_screenshot)
  .register('page_to_markdown', domHandlers.page_to_markdown)
  .register('page_to_pdf', domHandlers.page_to_pdf)
  .register('network_digest', networkHandlers.network_digest)
  .register('network_list', networkHandlers.network_list)
  .register('network_get_body', networkHandlers.network_get_body)
  .register('network_media_hints', networkHandlers.network_media_hints)
  .register('network_resolve_hls', networkHandlers.network_resolve_hls)
  .register('network_wait', networkHandlers.network_wait)
  .register('network_intercept', networkHandlers.network_intercept)
  .register('network_clear_intercepts', networkHandlers.network_clear_intercepts)
  .register('network_read', networkCatalogHandler)
  .register('skill_load', skillLoad)
  .register('system_done', systemDone)
  .register('dom_probe', domProbe)
  .register('system_extract_page', systemExtractPage)
  .register('system_captcha_wait', systemCaptchaWait)
  .register('system_ask_user', systemAskUser)
  .register('system_spawn_readonly_tasks', systemSpawnReadonlyTasks)
  .register('dom_read', domCatalogHandler)

BUILTIN_TOOL_REGISTRY.assertCatalog(AGENT_TOOL_IDS)

export async function executeBuiltinTool(input: BuiltinContext): Promise<BuiltinResult> {
  const resolved = resolveBuiltinToolCall(input.action.tool, input.action.arguments)
  const handler = BUILTIN_TOOL_REGISTRY.get(resolved.tool)
  if (!handler) {
    return {
      result: { ok: false, error: { code: 'unknown_tool', message: resolved.tool, recoverable: false } },
      snap: input.snap,
    }
  }
  return handler({ ...input, action: { ...input.action, tool: resolved.tool, arguments: resolved.arguments } })
}
