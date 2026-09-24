import { useMemo } from 'react'

import { useI18n } from '../../../i18n'
import type { BehaviorNetworkRequest } from '../network-summary.js'

type Props = {
  requests: BehaviorNetworkRequest[]
  sessionDurationMs: number
}

function formatMs(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

export function NetworkWaterfall({ requests, sessionDurationMs }: Props) {
  const { t } = useI18n()
  const spanMs = useMemo(
    () => Math.max(sessionDurationMs, ...requests.map((r) => r.startMs + r.durationMs), 1),
    [requests, sessionDurationMs]
  )

  if (!requests.length) return null

  return (
    <div className="bf-waterfall">
      <div className="bf-waterfall-head">
        <span>{t('options.behaviorForge.waterfallTitle')}</span>
        <span className="bf-waterfall-span">{formatMs(spanMs)}</span>
      </div>
      <div className="bf-waterfall-axis" aria-hidden>
        <span>0</span>
        <span>{formatMs(spanMs / 2)}</span>
        <span>{formatMs(spanMs)}</span>
      </div>
      <ul className="bf-waterfall-list">
        {requests.map((r) => {
          const left = (r.startMs / spanMs) * 100
          const width = Math.max(0.6, (Math.max(r.durationMs, 8) / spanMs) * 100)
          const err = r.status != null && r.status >= 400
          return (
            <li key={r.id} className="bf-waterfall-row">
              <div className="bf-waterfall-meta">
                <span className={`bf-net-status${err ? ' err' : ''}`}>{r.status ?? '…'}</span>
                <span className="bf-net-method">{r.method}</span>
                <span className="bf-waterfall-url" title={r.url}>
                  {r.url}
                </span>
                <span className="bf-waterfall-dur">{formatMs(r.durationMs)}</span>
              </div>
              <div className="bf-waterfall-track" aria-hidden>
                <span
                  className={`bf-waterfall-bar${err ? ' err' : ''}${r.api ? ' api' : ''}`}
                  style={{ left: `${left}%`, width: `${Math.min(width, 100 - left)}%` }}
                />
              </div>
            </li>
          )
        })}
      </ul>
    </div>
  )
}
