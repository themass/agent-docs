import { useEffect, useState } from 'react'

import { useI18n } from '../../i18n'
import {
  normalizeModifyHeaders,
  persistModifyHeadersSettings,
} from '../../lib/modify-headers'
import { STORAGE } from '../../lib/settings'

/** Master switch on Settings → Privacy (off by default for store compliance). */
export function ModifyHeadersPrivacyToggle() {
  const { t } = useI18n()
  const [enabled, setEnabled] = useState(false)

  useEffect(() => {
    void chrome.storage.local.get(STORAGE.modifyHeaders).then((saved) => {
      setEnabled(normalizeModifyHeaders(saved[STORAGE.modifyHeaders]).enabled)
    })
    const onChanged = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string
    ) => {
      if (area !== 'local' || !changes[STORAGE.modifyHeaders]) return
      setEnabled(normalizeModifyHeaders(changes[STORAGE.modifyHeaders].newValue).enabled)
    }
    chrome.storage.onChanged.addListener(onChanged)
    return () => chrome.storage.onChanged.removeListener(onChanged)
  }, [])

  return (
    <label className="toggle-row">
      <span>
        <strong>{t('options.privacy.modifyHeadersLabel')}</strong>
        <small>{t('options.privacy.modifyHeadersDesc')}</small>
      </span>
      <input
        type="checkbox"
        checked={enabled}
        onChange={(event) => {
          const nextEnabled = event.target.checked
          setEnabled(nextEnabled)
          void chrome.storage.local.get(STORAGE.modifyHeaders).then(async (saved) => {
            const current = normalizeModifyHeaders(saved[STORAGE.modifyHeaders])
            await persistModifyHeadersSettings({ ...current, enabled: nextEnabled })
          })
        }}
      />
    </label>
  )
}
