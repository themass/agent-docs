import { DEFAULT_RUN_LIMITS } from './run-limits.js'
import { normalizeScrollArgs } from './exec-turn.js'

export {
  bareSkillId,
  isGeneralTask,
  isPageReadTask,
  isResearchTask,
  requestedList,
  requestedTopN,
  resolveTaskMode,
  shouldHintListThenDetail,
  urlsMatchForReuse,
  type TaskMode,
} from './task-classifier.js'
export type { ThreadContext, ThreadReuse } from '@naviforge/session'

const DOM_READ_DEDUPE_MODES = new Set(['body', 'list', 'dom'])

export function observationDedupeKey(
  tool: string,
  url: string,
  args?: Record<string, unknown>
): string | null {
  if (tool === 'dom_read') {
    const mode = typeof args?.mode === 'string' ? args.mode : 'body'
    if (!DOM_READ_DEDUPE_MODES.has(mode)) return null
    return `dom_read|${url}|${mode}`
  }
  if (tool === 'web_search') {
    const query = typeof args?.query === 'string' ? args.query.trim().toLowerCase() : ''
    return query ? `web_search|${query}` : null
  }
  if (tool === 'fetch_text') {
    const raw = typeof args?.url === 'string' ? args.url.trim() : ''
    if (!raw) return null
    try {
      const parsed = new URL(raw)
      return `fetch_text|${parsed.origin}${parsed.pathname}`.replace(/\/$/, '')
    } catch {
      return `fetch_text|${raw.toLowerCase()}`
    }
  }
  if (tool === 'dom_execute_js') {
    const code = typeof args?.code === 'string' ? args.code.trim().slice(0, 120) : ''
    return code ? `dom_execute_js|${url}|${code}` : `dom_execute_js|${url}`
  }
  if (tool === 'page_signals') return url ? `page_signals|${url}` : 'page_signals'
  if (tool === 'tabs_open') {
    const raw = typeof args?.url === 'string' ? args.url.trim() : ''
    if (!raw) return null
    try {
      const parsed = new URL(raw)
      return `tabs_open|${parsed.origin}${parsed.pathname}`.replace(/\/$/, '')
    } catch {
      return `tabs_open|${raw.toLowerCase()}`
    }
  }
  return null
}

const ACTION_LOOP_TOOLS = new Set(['dom_screenshot', 'dom_scroll', 'dom_snapshot', 'page_to_pdf'])

/** Stable key for repeated successful actions on the same URL (screenshot/scroll loops). */
export function actionLoopKey(
  tool: string,
  url: string,
  args?: Record<string, unknown>
): string | null {
  if (!url) return null
  if (tool === 'dom_read') {
    const mode = typeof args?.mode === 'string' ? args.mode : 'body'
    if (mode === 'markdown') return `dom_read|${url}|markdown`
    return null
  }
  if (!ACTION_LOOP_TOOLS.has(tool)) return null
  if (tool === 'dom_scroll') {
    const scroll = normalizeScrollArgs(args ?? {})
    const part =
      scroll.to ??
      (scroll.y != null ? `y:${scroll.y}` : `${scroll.direction ?? 'down'}:${scroll.amount ?? ''}`)
    return `dom_scroll|${url}|${part}`
  }
  if (tool === 'dom_snapshot') {
    const mode = typeof args?.mode === 'string' ? args.mode : 'visible'
    return `dom_snapshot|${url}|${mode}`
  }
  return `${tool}|${url}`
}

export type ActionLoopGate = {
  exec: Map<string, number>
  skip: Map<string, number>
  limit: number
}

export function createActionLoopGate(limit: number): ActionLoopGate {
  return { exec: new Map(), skip: new Map(), limit }
}

/** Before executing: allow, skip (hint only), or stop the run. */
export function decideActionLoop(gate: ActionLoopGate, key: string | null): 'allow' | 'skip' | 'stop' {
  if (!key || gate.limit <= 0) return 'allow'
  const exec = gate.exec.get(key) ?? 0
  if (exec < gate.limit) return 'allow'
  const n = (gate.skip.get(key) ?? 0) + 1
  gate.skip.set(key, n)
  return n >= 2 ? 'stop' : 'skip'
}

export function recordActionLoopSuccess(gate: ActionLoopGate, key: string | null): void {
  if (!key) return
  gate.exec.set(key, (gate.exec.get(key) ?? 0) + 1)
}

export type ActionLoopCall = { tool: string; arguments?: Record<string, unknown> }

/** Replay successful calls on one URL. `stopAt` is the call index that would halt the run, or -1. */
export function replayActionLoop(
  calls: ActionLoopCall[],
  url: string,
  limit = DEFAULT_RUN_LIMITS.sameActionLimit
): { stopAt: number; allowed: number } {
  const gate = createActionLoopGate(limit)
  let allowed = 0
  for (let i = 0; i < calls.length; i++) {
    const call = calls[i]!
    const key = actionLoopKey(call.tool, url, call.arguments)
    const decision = decideActionLoop(gate, key)
    if (decision === 'stop') return { stopAt: i, allowed }
    if (decision === 'skip') continue
    allowed += 1
    recordActionLoopSuccess(gate, key)
  }
  return { stopAt: -1, allowed }
}
