import type { TaskScope } from './task-scope.js'

/** Compare URLs for current-page scope (ignore hash fragments). */
export function urlsEquivalentForScope(before: string, after: string): boolean {
  try {
    const a = new URL(before)
    const b = new URL(after)
    return a.origin === b.origin && a.pathname === b.pathname && a.search === b.search
  } catch {
    return before === after
  }
}

const URL_MUTATING_TOOLS = new Set([
  'dom_click',
  'dom_navigate',
  'dom_press',
  'dom_type',
  'browser_act',
  'browser_nav',
])

export function isUrlMutatingTool(tool: string): boolean {
  return URL_MUTATING_TOOLS.has(tool)
}

export function detectUrlDrift(
  before: string,
  after: string,
  scope: TaskScope
): { drifted: boolean; message: string } {
  if (scope.navigation !== 'forbidden') {
    return { drifted: false, message: '' }
  }
  if (urlsEquivalentForScope(before, after)) {
    return { drifted: false, message: '' }
  }
  return {
    drifted: true,
    message: `unexpected navigation ${before} → ${after} (current-page task)`,
  }
}
