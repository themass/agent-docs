import { fillCopy, uiCopy } from './ui-copy.js'

/** Codes that mean "settings gate" — retrying another path still wastes the run. */
export const HARD_DENY_ERROR_CODES = new Set([
  'execute_js_denied',
  'inject_denied',
  'intercept_denied',
  'probe_denied',
  'no_search_key',
])

export function privacyHintFor(code: string, locale?: string): string | undefined {
  return uiCopy(locale).privacy[code]
}

export function isCspEvalError(message: string): boolean {
  return /unsafe-eval|Evaluating a string as JavaScript|Code generation from strings disallowed/i.test(
    message
  )
}

export type RunLimitOptions = {
  /** Consecutive identical tool+error.code failures before ask_user (0 = off). */
  sameFailureLimit?: number
  /** Max successful identical screenshot/scroll/snapshot actions per URL before blocking (0 = off). */
  sameActionLimit?: number
  /** Wall-clock ms from run start (0 = off). */
  runTimeoutMs?: number
  /** Cumulative LLM tokens for this run (0 = off). */
  runTokenBudget?: number
  /** Estimated tokens in a single model input (system + user; 0 = off). */
  maxInputTokens?: number
}

export const DEFAULT_RUN_LIMITS = {
  maxSteps: 30,
  sameFailureLimit: 2,
  sameActionLimit: 2,
  runTimeoutMs: 8 * 60_000,
  runTokenBudget: 200_000,
  maxInputTokens: 32_000,
} as const

export function sameActionLoopResult(tool: string, count: number, locale?: string): string {
  return fillCopy(uiCopy(locale).actionLoop, { tool, count })
}

export function hardDenyQuestion(tool: string, code: string, hint?: string, locale?: string): string {
  const copy = uiCopy(locale)
  if (code === 'no_search_key') {
    const where = hint ?? copy.privacy.no_search_key ?? 'Settings → Models → Web search'
    return fillCopy(copy.hardDenySearch, { tool, code, where })
  }
  const where = hint ?? 'Settings → Privacy'
  return fillCopy(copy.hardDeny, { tool, code, where })
}

export function sameFailureQuestion(tool: string, code: string, count: number, locale?: string): string {
  const copy = uiCopy(locale)
  if (tool === 'dom_navigate' && code === 'bad_args') {
    return fillCopy(copy.sameFailureNav, { count })
  }
  return fillCopy(copy.sameFailure, { tool, code, count })
}

export type ListOpenHint = { index: number; title: string; url?: string }

/** Format concrete list rows so navigate/click recovery can avoid empty {} loops. */
export function formatListOpenConstraint(items: ListOpenHint[]): string {
  const lines = items.slice(0, 5).map((item, i) => {
    const url = item.url ? ` url=${item.url}` : ''
    return `${i + 1}. index=${item.index} ${item.title}${url}`
  })
  return (
    `CONSTRAINT: Open detail via dom_click({"index":N,"revision":R}) or ` +
    `dom_navigate({"action":"url","url":"..."}); pick from:\n${lines.join('\n')}\n` +
    `Forbidden: empty dom_navigate {}.`
  )
}

export function listHintsFromToolData(data: unknown): ListOpenHint[] {
  if (!data || typeof data !== 'object') return []
  const items = (data as { items?: unknown }).items
  if (!Array.isArray(items)) return []
  const out: ListOpenHint[] = []
  for (const raw of items.slice(0, 8)) {
    if (!raw || typeof raw !== 'object') continue
    const row = raw as Record<string, unknown>
    const index = typeof row.index === 'number' ? row.index : Number(row.index)
    const title = typeof row.title === 'string' ? row.title.trim() : ''
    const url = typeof row.url === 'string' ? row.url : undefined
    if (!Number.isFinite(index) || !title) continue
    out.push({ index, title, url })
  }
  return out
}
