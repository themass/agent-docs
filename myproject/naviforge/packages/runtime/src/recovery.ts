import type { ToolResult } from '@naviforge/shared'

/** What the loop/UI should do after a failure. Not a second taxonomy beside LoopCommand. */
export type RecoveryStrategy =
  | 'reobserve_and_replan'
  | 'retry_request'
  | 'ask_user'
  | 'stop'
  | 'protocol_retry'
  | 'protocol_error'
  | 'fold_context'

export type RecoveryPlan = {
  strategy: RecoveryStrategy
  retryable: boolean
  diagnostic: string
}

export function classifyFailure(
  error: Extract<ToolResult, { ok: false }>['error']
): RecoveryPlan {
  if (error.code === 'stale_revision') {
    return {
      strategy: 'reobserve_and_replan',
      retryable: true,
      diagnostic: 'The DOM changed after observation. A fresh snapshot is required.',
    }
  }
  if (error.code.startsWith('mcp_')) {
    const retryable = /\b(408|429|500|502|503|504)\b|timeout|network/i.test(error.message)
    return {
      strategy: retryable ? 'retry_request' : 'ask_user',
      retryable,
      diagnostic: error.message,
    }
  }
  if (error.code.startsWith('network') || error.code === 'no_network') {
    return {
      strategy: error.recoverable ? 'reobserve_and_replan' : 'ask_user',
      retryable: error.recoverable,
      diagnostic: error.message,
    }
  }
  if (error.code.includes('click') || error.code.includes('type') || error.code.includes('selector')) {
    return {
      strategy: error.recoverable ? 'reobserve_and_replan' : 'ask_user',
      retryable: error.recoverable,
      diagnostic: error.message,
    }
  }
  return {
    strategy: error.recoverable ? 'reobserve_and_replan' : 'stop',
    retryable: error.recoverable,
    diagnostic: error.message,
  }
}

export function isTransientRequestError(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return /\b(408|429|500|502|503|504)\b|timeout|network|fetch failed/i.test(message)
}

function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  if (ms <= 0) return Promise.resolve()
  if (signal?.aborted) {
    return Promise.reject(new DOMException('Aborted', 'AbortError'))
  }
  return new Promise((resolve, reject) => {
    const id = setTimeout(() => finish(resolve), ms)
    const onAbort = () => finish(() => reject(new DOMException('Aborted', 'AbortError')))
    const finish = (fn: () => void) => {
      clearTimeout(id)
      signal?.removeEventListener('abort', onAbort)
      fn()
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException
    ? error.name === 'AbortError'
    : error instanceof Error && error.name === 'AbortError'
}

export async function retry<T>(
  operation: () => Promise<T>,
  options: {
    attempts: number
    delayMs: number
    signal?: AbortSignal
    onRetry?: (attempt: number, error: unknown) => void
  }
): Promise<T> {
  let lastError: unknown
  for (let attempt = 0; attempt < options.attempts; attempt += 1) {
    options.signal?.throwIfAborted()
    try {
      return await operation()
    } catch (error) {
      lastError = error
      if (isAbortError(error)) throw error
      if (attempt === options.attempts - 1 || !isTransientRequestError(error)) throw error
      options.onRetry?.(attempt + 1, error)
      await sleep(options.delayMs * (attempt + 1), options.signal)
    }
  }
  throw lastError
}
