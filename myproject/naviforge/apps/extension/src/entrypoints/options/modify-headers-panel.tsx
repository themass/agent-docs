import { useEffect, useState } from 'react'

import { useI18n } from '../../i18n'
import {
  DEFAULT_MODIFY_HEADERS,
  normalizeModifyHeaders,
  persistModifyHeadersSettings,
  type ModifyHeadersSettings,
} from '../../lib/modify-headers'
import { STORAGE } from '../../lib/settings'

/** Global request-header injection (all tabs / all http(s)). Lives in Toolkit. */
export function ModifyHeadersPanel() {
  const { t } = useI18n()
  const [settings, setSettings] = useState<ModifyHeadersSettings>(DEFAULT_MODIFY_HEADERS)
  const [notice, setNotice] = useState('')

  useEffect(() => {
    void chrome.storage.local.get(STORAGE.modifyHeaders).then((saved) => {
      setSettings(normalizeModifyHeaders(saved[STORAGE.modifyHeaders]))
    })
  }, [])

  function flash(message: string): void {
    setNotice(message)
    window.setTimeout(() => setNotice(''), 2200)
  }

  async function persist(next: ModifyHeadersSettings): Promise<void> {
    const normalized = await persistModifyHeadersSettings(next)
    setSettings(normalized)
    flash(
      normalized.enabled
        ? t('options.modifyHeaders.noticeEnabled')
        : t('options.modifyHeaders.noticeDisabled')
    )
  }

  async function save(): Promise<void> {
    await persist(settings)
  }

  return (
    <section className="toolkit-results modify-headers-panel">
      <div className="section-heading">
        <span>{t('options.modifyHeaders.eyebrow')}</span>
        <h2>{t('options.modifyHeaders.title')}</h2>
        <p className="session-hint">{t('options.modifyHeaders.description')}</p>
      </div>

      {notice ? (
        <div className="notice" role="status">
          {notice}
        </div>
      ) : null}

      <label className="mh-toggle">
        <input
          type="checkbox"
          checked={settings.enabled}
          onChange={(event) => {
            const enabled = event.target.checked
            void persist({ ...settings, enabled })
          }}
        />
        <span>
          <strong>{t('options.modifyHeaders.enableLabel')}</strong>
          <small>{t('options.modifyHeaders.enableDesc')}</small>
        </span>
      </label>

      <label className="mh-toggle">
        <input
          type="checkbox"
          checked={settings.cors}
          disabled={!settings.enabled}
          onChange={(event) => {
            const cors = event.target.checked
            void persist({ ...settings, cors })
          }}
        />
        <span>
          <strong>{t('options.modifyHeaders.corsLabel')}</strong>
          <small>{t('options.modifyHeaders.corsDesc')}</small>
        </span>
      </label>

      <div className="mh-kv-head">
        <span>{t('options.modifyHeaders.kvHeadName')}</span>
        <span>{t('options.modifyHeaders.kvHeadValue')}</span>
        <span />
      </div>
      {settings.headers.map((row, index) => (
        <div className="mh-row" key={index}>
          <input
            placeholder={t('options.modifyHeaders.namePlaceholder')}
            value={row.key}
            disabled={!settings.enabled}
            onChange={(event) => {
              const headers = settings.headers.slice()
              headers[index] = { ...row, key: event.target.value }
              setSettings({ ...settings, headers })
            }}
          />
          <input
            placeholder={t('options.modifyHeaders.valuePlaceholder')}
            value={row.value}
            disabled={!settings.enabled}
            onChange={(event) => {
              const headers = settings.headers.slice()
              headers[index] = { ...row, value: event.target.value }
              setSettings({ ...settings, headers })
            }}
          />
          <button
            type="button"
            className="text-button"
            disabled={!settings.enabled}
            onClick={() =>
              setSettings({
                ...settings,
                headers: settings.headers.filter((_, i) => i !== index),
              })
            }
          >
            {t('options.common.buttons.delete')}
          </button>
        </div>
      ))}

      <div className="button-row compact">
        <button
          type="button"
          className="button secondary"
          disabled={!settings.enabled}
          onClick={() =>
            setSettings({
              ...settings,
              headers: [...settings.headers, { key: '', value: '' }],
            })
          }
        >
          {t('options.common.buttons.addRow')}
        </button>
        <button type="button" className="button primary" disabled={!settings.enabled} onClick={() => void save()}>
          {t('options.common.buttons.saveAndApply')}
        </button>
      </div>
    </section>
  )
}
