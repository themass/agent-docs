import { compressVisionImage } from '../../../lib/vision-ocr.js'
import { openSidePanelForStudioAttach } from '../../../lib/surface-launch.js'
import { STUDIO_COMPOSER_ATTACH_KEY, SCREENSHOT_STUDIO_MESSAGE } from '../messages.js'

export type ComposerAttachment = { dataUrl: string; label: string }

export async function queueComposerAttachment(
  dataUrl: string,
  label = '截图',
  sourceTabId?: number,
  sourceWindowId?: number
): Promise<void> {
  const compact =
    dataUrl.startsWith('data:image/png') || dataUrl.startsWith('data:image/webp')
      ? await compressVisionImage(dataUrl)
      : dataUrl
  const payload = { dataUrl: compact, label, at: Date.now() }
  try {
    await chrome.runtime.sendMessage({
      type: SCREENSHOT_STUDIO_MESSAGE.attach,
      tabId: sourceTabId,
      windowId: sourceWindowId,
      ...payload,
    })
  } catch {
    /* side panel may not be listening yet */
  }
  await chrome.storage.local.set({ [STUDIO_COMPOSER_ATTACH_KEY]: payload })
}

/** Sync in click handler — opens Agent side panel before await. */
export function openSidePanelForAttach(
  tabId: number,
  windowId?: number
): { ok: true } | { ok: false; error: string } {
  try {
    chrome.runtime.sendMessage({
      type: SCREENSHOT_STUDIO_MESSAGE.openSidePanel,
      tabId,
      windowId,
    })
  } catch {
    /* background may be asleep; direct open below */
  }
  return openSidePanelForStudioAttach(tabId, windowId)
}
