/** MV3 extension context helpers — avoid uncaught rejections after reload/update. */

export function extensionRuntimeAlive(): boolean {
  try {
    return Boolean(globalThis.chrome?.runtime?.id)
  } catch {
    return false
  }
}

export function isExtensionContextInvalidated(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return message.includes('Extension context invalidated')
}

/** MV3 service worker may be asleep or reloading — callers should retry or skip. */
export function isServiceWorkerUnavailable(error: unknown): boolean {
  const message = error instanceof Error ? error.message : String(error)
  return (
    message.includes('No SW') ||
    message.includes('Receiving end does not exist') ||
    message.includes('Could not establish connection')
  )
}

export function runIfExtensionAlive(fn: () => void): void {
  if (!extensionRuntimeAlive()) return
  try {
    fn()
  } catch (error) {
    if (!isExtensionContextInvalidated(error)) throw error
  }
}

export async function safeStorageLocalGet(
  key: string
): Promise<Record<string, unknown> | undefined> {
  if (!extensionRuntimeAlive()) return undefined
  try {
    return (await chrome.storage.local.get([key])) as Record<string, unknown>
  } catch (error) {
    if (isExtensionContextInvalidated(error)) return undefined
    throw error
  }
}

export async function safeStorageLocalSet(values: Record<string, unknown>): Promise<boolean> {
  if (!extensionRuntimeAlive()) return false
  try {
    await chrome.storage.local.set(values)
    return true
  } catch (error) {
    if (isExtensionContextInvalidated(error)) return false
    throw error
  }
}

export async function safeRuntimeSendMessage<T = unknown>(message: unknown): Promise<T | undefined> {
  if (!extensionRuntimeAlive()) return undefined
  try {
    return (await chrome.runtime.sendMessage(message)) as T
  } catch (error) {
    if (isExtensionContextInvalidated(error) || isServiceWorkerUnavailable(error)) return undefined
    throw error
  }
}

/** Content scripts: swallow invalidated-context rejections after extension reload. */
export function installExtensionContextGuard(onInvalidated: () => void): () => void {
  if (typeof window === 'undefined') return () => {}
  const onRejection = (event: PromiseRejectionEvent) => {
    if (!isExtensionContextInvalidated(event.reason)) return
    event.preventDefault()
    onInvalidated()
  }
  window.addEventListener('unhandledrejection', onRejection)
  return () => window.removeEventListener('unhandledrejection', onRejection)
}
