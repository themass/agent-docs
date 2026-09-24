import { useEffect } from 'react'

import { STUDIO_COMPOSER_ATTACH_KEY } from '../messages.js'
import type { ComposerAttachment } from './composer-bridge.js'

export function useScreenshotStudioComposerBridge(
  onAttach: (attachment: ComposerAttachment) => void
): void {
  useEffect(() => {
    const apply = (value: unknown) => {
      if (!value || typeof value !== 'object') return
      const attachment = value as Partial<ComposerAttachment> & { at?: number }
      if (typeof attachment.dataUrl !== 'string') return
      onAttach({
        dataUrl: attachment.dataUrl,
        label: typeof attachment.label === 'string' ? attachment.label : '截图',
      })
      void chrome.storage.local.remove(STUDIO_COMPOSER_ATTACH_KEY)
    }

    void chrome.storage.local.get(STUDIO_COMPOSER_ATTACH_KEY).then((stored) => {
      apply(stored[STUDIO_COMPOSER_ATTACH_KEY])
    })

    const onChanged = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string
    ) => {
      if (area !== 'local' || !changes[STUDIO_COMPOSER_ATTACH_KEY]) return
      apply(changes[STUDIO_COMPOSER_ATTACH_KEY].newValue)
    }

    chrome.storage.onChanged.addListener(onChanged)
    return () => chrome.storage.onChanged.removeListener(onChanged)
  }, [onAttach])
}
