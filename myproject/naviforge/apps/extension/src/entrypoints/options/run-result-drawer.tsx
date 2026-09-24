import type { DomContentItem } from '@naviforge/dom-plane'

import { useI18n } from '../../i18n'
import { openStreetMapMarkerUrl, openStreetMapStaticUrl } from '../../lib/net-diag'
import { formatRunSubtitle } from '../../lib/toolkit-run-result'
import { ToolkitSideDrawer } from './toolkit-side-drawer'

export type ToolkitRunResult =
  | {
      kind: 'ip'
      title: string
      target?: string
      elapsedMs: number
      text: string
      latitude?: number
      longitude?: number
      traceroute?: string
    }
  | { kind: 'screenshot'; title: string; target?: string; elapsedMs: number; dataUrl: string; meta?: string }
  | { kind: 'list'; title: string; target?: string; elapsedMs: number; items: DomContentItem[]; meta?: string }
  | { kind: 'note'; title: string; target?: string; elapsedMs: number; text: string }

export function RunResultDrawer({
  result,
  onClose,
  onCopy,
  onExportList,
  onSaveImage,
  onDownloadText,
  onTraceroute,
  tracerouteBusy,
}: {
  result: ToolkitRunResult | null
  onClose: () => void
  onCopy: (text: string) => void
  onExportList: () => void
  onSaveImage: (dataUrl: string) => void
  onDownloadText?: (text: string) => void
  onTraceroute?: () => void
  tracerouteBusy?: boolean
}) {
  const { t } = useI18n()
  const hasMap =
    result?.kind === 'ip' &&
    result.latitude != null &&
    result.longitude != null &&
    Number.isFinite(result.latitude) &&
    Number.isFinite(result.longitude)

  return (
    <ToolkitSideDrawer
      open={Boolean(result)}
      onClose={onClose}
      label={result?.title ?? t('options.runResult.drawerFallback')}
    >
      {result ? (
        <>
          <header className="toolkit-drawer-head">
            <div>
              <p className="eyebrow">{t('options.runResult.eyebrow')}</p>
              <h2>{result.title}</h2>
              <p className="session-hint">{formatRunSubtitle(result)}</p>
            </div>
            <button type="button" className="button ghost" onClick={onClose}>
              {t('options.runResult.close')}
            </button>
          </header>
          <div className="toolkit-drawer-actions">
            {result.kind === 'ip' || result.kind === 'note' ? (
              <button type="button" className="button secondary" onClick={() => onCopy(result.text)}>
                {t('options.runResult.copy')}
              </button>
            ) : null}
            {result.kind === 'ip' && onTraceroute ? (
              <button
                type="button"
                className="button secondary"
                disabled={tracerouteBusy}
                onClick={onTraceroute}
                title={t('options.runResult.tracerouteTitle')}
              >
                {tracerouteBusy
                  ? t('options.runResult.tracerouteBusy')
                  : t('options.runResult.traceroute')}
              </button>
            ) : null}
            {result.kind === 'note' && onDownloadText ? (
              <button
                type="button"
                className="button secondary"
                onClick={() => onDownloadText(result.text)}
              >
                {t('options.runResult.downloadTxt')}
              </button>
            ) : null}
            {result.kind === 'screenshot' ? (
              <button
                type="button"
                className="button secondary"
                onClick={() => onSaveImage(result.dataUrl)}
              >
                {t('options.runResult.reSave')}
              </button>
            ) : null}
            {result.kind === 'list' ? (
              <button
                type="button"
                className="button secondary"
                disabled={!result.items.length}
                onClick={onExportList}
              >
                {t('options.runResult.exportJsonl')}
              </button>
            ) : null}
          </div>
          <p className="toolkit-drawer-status muted">{t('options.runResult.resizeHint')}</p>
          <div className="toolkit-run-body">
            {result.kind === 'ip' || result.kind === 'note' ? (
              <pre className="toolkit-run-text">{result.text}</pre>
            ) : null}
            {result.kind === 'ip' && hasMap ? (
              <div className="toolkit-ip-map">
                <img
                  className="toolkit-ip-map-img"
                  alt={t('options.runResult.ipMapAlt', {
                    lat: result.latitude!,
                    lng: result.longitude!,
                  })}
                  src={openStreetMapStaticUrl(result.latitude!, result.longitude!)}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                />
                <a
                  className="text-button"
                  href={openStreetMapMarkerUrl(result.latitude!, result.longitude!)}
                  target="_blank"
                  rel="noreferrer"
                >
                  {t('options.runResult.openStreetMap')}
                </a>
              </div>
            ) : null}
            {result.kind === 'ip' && result.traceroute ? (
              <pre className="toolkit-run-text toolkit-traceroute">{result.traceroute}</pre>
            ) : null}
            {result.kind === 'screenshot' ? (
              <>
                {result.meta ? <p className="session-hint">{result.meta}</p> : null}
                <img src={result.dataUrl} alt={t('options.runResult.screenshotAlt')} className="toolkit-preview" />
              </>
            ) : null}
            {result.kind === 'list' ? (
              <>
                {result.meta ? <p className="session-hint">{result.meta}</p> : null}
                {!result.items.length ? (
                  <div className="empty">
                    <strong>{t('options.runResult.listEmptyTitle')}</strong>
                    <span>{t('options.runResult.listEmptyBody')}</span>
                  </div>
                ) : (
                  <div className="data-list">
                    <div className="data-list-head data-list-extract">
                      <span>{t('options.runResult.table.index')}</span>
                      <span>{t('options.runResult.table.title')}</span>
                      <span>{t('options.runResult.table.link')}</span>
                    </div>
                    {result.items.map((item) => (
                      <article
                        className="data-list-row data-list-extract"
                        key={`${item.index}-${item.title}-${item.url ?? ''}`}
                      >
                        <span className="data-list-badge">{item.label ?? `#${item.index}`}</span>
                        <div className="data-list-main">
                          <strong>{item.title || t('options.common.labels.noTitle')}</strong>
                          {item.fields && Object.keys(item.fields).length ? (
                            <small>
                              {Object.entries(item.fields)
                                .filter(([key]) => key !== 'count')
                                .map(([key, value]) => `${key}: ${value}`)
                                .join(' · ')}
                            </small>
                          ) : null}
                        </div>
                        <span className="data-list-meta">
                          {item.url ? (
                            <a href={item.url} target="_blank" rel="noreferrer">
                              {item.url}
                            </a>
                          ) : (
                            t('options.common.labels.dash')
                          )}
                        </span>
                      </article>
                    ))}
                  </div>
                )}
              </>
            ) : null}
          </div>
        </>
      ) : null}
    </ToolkitSideDrawer>
  )
}
