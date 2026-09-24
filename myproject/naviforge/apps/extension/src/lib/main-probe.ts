import type { ToolResult } from '@naviforge/shared'

const MAX_EXPRESSION_LEN = 400
const MAX_RESULT_JSON_LEN = 8_192

/** Blocked substrings in MAIN-world probe expressions. */
const BLOCKED_PROBE =
  /\b(eval|Function|constructor|__proto__|prototype|import|require|document|window\.open|fetch|XMLHttpRequest|cookie|localStorage|sessionStorage|indexedDB|postMessage|chrome|debugger)\b/i

/** Allowed probe expression charset (property paths, literals, typeof). */
const ALLOWED_PROBE = /^(?:typeof\s+)?[\w$.\[\]()'"+?:,\s-]+$/

export function isProbeExpressionAllowed(expression: string): boolean {
  const trimmed = expression.trim()
  if (!trimmed || trimmed.length > MAX_EXPRESSION_LEN) return false
  if (BLOCKED_PROBE.test(trimmed)) return false
  return ALLOWED_PROBE.test(trimmed)
}

export function clampProbeResult(value: unknown): { ok: true; value: unknown } | { ok: false; error: string } {
  let json: string
  try {
    json = JSON.stringify(value)
  } catch {
    return { ok: false, error: 'result is not JSON-serializable' }
  }
  if (json.length > MAX_RESULT_JSON_LEN) {
    return { ok: false, error: `result too large (${json.length} chars, max ${MAX_RESULT_JSON_LEN})` }
  }
  try {
    return { ok: true, value: JSON.parse(json) as unknown }
  } catch {
    return { ok: false, error: 'result JSON round-trip failed' }
  }
}

/** MAIN-world read-only expression (returns JSON-serializable value). */
export async function mainWorldProbe(
  tabId: number,
  expression: string
): Promise<ToolResult<{ value: unknown }>> {
  if (!isProbeExpressionAllowed(expression)) {
    return {
      ok: false,
      error: {
        code: 'bad_expression',
        message:
          'expression blocked (max 400 chars; no eval/Function/document/fetch/storage/cookie)',
        recoverable: true,
      },
    }
  }
  try {
    const [result] = await chrome.scripting.executeScript({
      target: { tabId },
      world: 'MAIN',
      func: (code: string) => {
        const blocked =
          /\b(eval|Function|constructor|__proto__|prototype|import|require|document|window\.open|fetch|XMLHttpRequest|cookie|localStorage|sessionStorage|indexedDB|postMessage|chrome|debugger)\b/i
        if (blocked.test(code)) return { ok: false as const, error: 'blocked expression' }
        try {
          // ponytail: indirect eval in page context; upgrade to CDP Runtime.evaluate later.
          const fn = new Function(`"use strict"; return (${code})`)
          const value = fn()
          const json = JSON.stringify(value)
          if (json.length > 8192) return { ok: false as const, error: 'result too large' }
          return { ok: true as const, value: JSON.parse(json) }
        } catch (error) {
          return { ok: false as const, error: (error as Error).message }
        }
      },
      args: [expression],
    })
    const payload = result?.result as { ok: boolean; value?: unknown; error?: string } | undefined
    if (!payload?.ok) {
      return {
        ok: false,
        error: {
          code: 'probe_failed',
          message: payload?.error ?? 'probe failed',
          recoverable: true,
        },
      }
    }
    const clamped = clampProbeResult(payload.value)
    if (!clamped.ok) {
      return {
        ok: false,
        error: { code: 'probe_result', message: clamped.error, recoverable: true },
      }
    }
    return { ok: true, data: { value: clamped.value } }
  } catch (error) {
    return {
      ok: false,
      error: { code: 'probe_error', message: (error as Error).message, recoverable: true },
    }
  }
}
