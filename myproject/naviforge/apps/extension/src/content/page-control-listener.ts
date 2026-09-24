import {
  extensionRuntimeAlive,
  isExtensionContextInvalidated,
} from '../lib/extension-runtime'

/** PAGE_CONTROL message router — keeps content.ts entry thinner. */
export function installPageControlListener(
  onAction: (
    action: string,
    payload: Record<string, any>,
    sendResponse: (response: unknown) => void
  ) => Promise<void>
): void {
  chrome.runtime.onMessage.addListener((message, _sender, sendResponse): true | undefined => {
    if (message?.type !== 'PAGE_CONTROL') return
    if (!extensionRuntimeAlive()) return
    void onAction(String(message.action ?? ''), (message.payload ?? {}) as Record<string, any>, (response) => {
      if (!extensionRuntimeAlive()) return
      try {
        sendResponse(response)
      } catch (error) {
        if (!isExtensionContextInvalidated(error)) throw error
      }
    })
    return true
  })
}
