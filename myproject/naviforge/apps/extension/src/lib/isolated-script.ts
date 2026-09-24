const MAX_CODE = 100_000
const MAX_RESULT_JSON = 50_000
export const DEFAULT_SCRIPT_TIMEOUT_MS = 15_000

/** JSON-safe script return value; truncates oversized payloads. */
export function serializeScriptResult(value: unknown): unknown {
  try {
    const json = JSON.stringify(value ?? null)
    if (json.length > MAX_RESULT_JSON) {
      return { __truncated: true, preview: json.slice(0, MAX_RESULT_JSON) }
    }
    return JSON.parse(json) as unknown
  } catch {
    return { __string: String(value).slice(0, 2000) }
  }
}

function runInNode(code: string, timeoutMs: number): Promise<{ ok: true; result: unknown } | { ok: false; error: string }> {
  const body = code.slice(0, MAX_CODE).trim()
  if (!body) return Promise.resolve({ ok: false, error: 'empty script' })

  try {
    const run = new Function(`return (async () => { return (${body}); })()`) as () => Promise<unknown>
    const timeout = new Promise<never>((_, reject) => {
      setTimeout(() => reject(new Error(`timeout after ${timeoutMs}ms`)), timeoutMs)
    })
    return Promise.race([run(), timeout])
      .then((result) => ({ ok: true as const, result: serializeScriptResult(result) }))
      .catch((error: Error) => ({ ok: false as const, error: error.message }))
  } catch (error) {
    return Promise.resolve({ ok: false, error: (error as Error).message })
  }
}

function runViaMainBridge(
  code: string,
  timeoutMs: number
): Promise<{ ok: true; result: unknown } | { ok: false; error: string }> {
  const body = code.slice(0, MAX_CODE).trim()
  if (!body) return Promise.resolve({ ok: false, error: 'empty script' })

  return new Promise((resolve) => {
    const id = crypto.randomUUID()
    const timer = window.setTimeout(() => {
      window.removeEventListener('message', onMsg)
      resolve({ ok: false, error: `timeout after ${timeoutMs}ms` })
    }, timeoutMs)

    const onMsg = (event: MessageEvent) => {
      if (event.source !== window) return
      const data = event.data as {
        type?: string
        id?: string
        ok?: boolean
        result?: unknown
        error?: string
      }
      if (data?.type !== 'naviforge:execute_js_result' || data.id !== id) return
      window.removeEventListener('message', onMsg)
      window.clearTimeout(timer)
      resolve(
        data.ok
          ? { ok: true, result: serializeScriptResult(data.result) }
          : { ok: false, error: data.error ?? 'bridge error' }
      )
    }

    window.addEventListener('message', onMsg)
    window.postMessage({ type: 'naviforge:execute_js', id, code: body }, '*')
  })
}

export function isPageCspEvalError(message: string): boolean {
  return /unsafe-eval|Evaluating a string as JavaScript|Code generation from strings disallowed/i.test(
    message
  )
}

export async function runIsolatedScript(
  code: string,
  timeoutMs = DEFAULT_SCRIPT_TIMEOUT_MS
): Promise<{ ok: true; result: unknown } | { ok: false; error: string }> {
  if (typeof window !== 'undefined' && typeof window.postMessage === 'function') {
    const main = await runViaMainBridge(code, timeoutMs)
    // ponytail: MAIN `new Function` hits page CSP (GitHub); isolated world eval is the fallback.
    if (main.ok || !isPageCspEvalError(main.error)) return main
    return runInNode(code, timeoutMs)
  }
  return runInNode(code, timeoutMs)
}
