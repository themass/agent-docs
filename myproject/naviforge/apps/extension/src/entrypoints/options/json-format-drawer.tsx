import { useEffect, useRef, useState } from 'react'

import { useI18n } from '../../i18n'
import { parseLenient } from '../../lib/json-lenient'
import { ToolkitSideDrawer } from './toolkit-side-drawer'

/** Full-page drawer for JSON format/repair — stays inside Control Center Toolkit. */
export function JsonFormatDrawer({
  open,
  onClose,
}: {
  open: boolean
  onClose: () => void
}) {
  const { t } = useI18n()
  const [source, setSource] = useState('')
  const [output, setOutput] = useState('')
  const [status, setStatus] = useState<{ text: string; ok: boolean } | null>(null)
  const sourceRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    if (!open) return
    const focusTimer = window.setTimeout(() => sourceRef.current?.focus(), 0)
    return () => window.clearTimeout(focusTimer)
  }, [open])

  function flash(text: string, ok = true): void {
    setStatus({ text, ok })
  }

  function run(pretty: boolean): void {
    try {
      const { value, repaired } = parseLenient(source)
      setOutput(pretty ? JSON.stringify(value, null, 2) : JSON.stringify(value))
      flash(
        repaired
          ? pretty
            ? t('options.jsonFormat.status.repairedFormatted')
            : t('options.jsonFormat.status.repairedMinified')
          : pretty
            ? t('options.jsonFormat.status.formatted')
            : t('options.jsonFormat.status.minified')
      )
    } catch (error) {
      setOutput('')
      flash(t('options.jsonFormat.status.repairFailed', { message: (error as Error).message }), false)
    }
  }

  return (
    <ToolkitSideDrawer open={open} onClose={onClose} label={t('options.jsonFormat.drawerLabel')}>
      <header className="toolkit-drawer-head">
        <div>
          <p className="eyebrow">{t('options.jsonFormat.eyebrow')}</p>
          <h2>{t('options.jsonFormat.title')}</h2>
        </div>
        <button type="button" className="button ghost" onClick={onClose}>
          {t('options.jsonFormat.close')}
        </button>
      </header>
      <div className="toolkit-drawer-actions">
        <button
          type="button"
          className="button ghost"
          onClick={() => {
            void navigator.clipboard
              .readText()
              .then((text) => {
                setSource(text)
                flash(t('options.jsonFormat.status.pasted'))
              })
              .catch(() => flash(t('options.jsonFormat.status.clipboardDenied'), false))
          }}
        >
          {t('options.jsonFormat.pasteSource')}
        </button>
        <button type="button" className="button primary" onClick={() => run(true)}>
          {t('options.jsonFormat.repairFormat')}
        </button>
        <button type="button" className="button secondary" onClick={() => run(false)}>
          {t('options.jsonFormat.minify')}
        </button>
        <button
          type="button"
          className="button secondary"
          onClick={() => {
            const text = output || source
            if (!text) {
              flash(t('options.jsonFormat.status.nothingToCopy'), false)
              return
            }
            void navigator.clipboard
              .writeText(text)
              .then(() =>
                flash(
                  output
                    ? t('options.jsonFormat.status.copiedResult')
                    : t('options.jsonFormat.status.copiedSource')
                )
              )
              .catch(() => flash(t('options.notice.copyFailed', { message: 'clipboard' }), false))
          }}
        >
          {t('options.jsonFormat.copyResult')}
        </button>
        <button
          type="button"
          className="button ghost"
          onClick={() => {
            setSource('')
            setOutput('')
            setStatus(null)
          }}
        >
          {t('options.jsonFormat.clear')}
        </button>
      </div>
      {status ? (
        <p className={`toolkit-drawer-status ${status.ok ? 'ok' : 'bad'}`} role="status">
          {status.text}
        </p>
      ) : (
        <p className="toolkit-drawer-status muted">{t('options.jsonFormat.hint')}</p>
      )}
      <div className="toolkit-drawer-panes">
        <label className="toolkit-drawer-pane">
          <span>{t('options.jsonFormat.sourceLabel')}</span>
          <textarea
            ref={sourceRef}
            value={source}
            spellCheck={false}
            placeholder={t('options.jsonFormat.sourcePlaceholder')}
            onChange={(event) => setSource(event.target.value)}
            onKeyDown={(event) => {
              if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
                event.preventDefault()
                run(true)
              }
            }}
          />
        </label>
        <label className="toolkit-drawer-pane">
          <span>{t('options.jsonFormat.outputLabel')}</span>
          <textarea
            value={output}
            spellCheck={false}
            readOnly
            placeholder={t('options.jsonFormat.outputPlaceholder')}
          />
        </label>
      </div>
    </ToolkitSideDrawer>
  )
}
