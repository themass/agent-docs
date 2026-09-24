import { useMemo } from 'react'

import { useI18n } from '../../../i18n'
import type { BehaviorSessionRecord } from '../types.js'
import { formatDurationSec, pageDwellLines, statsForSession } from '../session-stats.js'
import { NetworkWaterfall } from './NetworkWaterfall.js'

type Props = {
  session: BehaviorSessionRecord
}

export function SessionInsights({ session }: Props) {
  const { t } = useI18n()
  const stats = useMemo(() => statsForSession(session), [session])
  const dwell = useMemo(() => pageDwellLines(session.events), [session.events])
  const net = session.networkDigest

  return (
    <div className="bf-insights">
      <div className="bf-stat-chips" role="list">
        <span className="bf-stat-chip" role="listitem">
          <em>{stats.clicks}</em> {t('options.behaviorForge.statClicks')}
        </span>
        <span className="bf-stat-chip" role="listitem">
          <em>{stats.scrolls}</em> {t('options.behaviorForge.statScrolls')}
        </span>
        <span className="bf-stat-chip" role="listitem">
          <em>{stats.pages}</em> {t('options.behaviorForge.statPages')}
        </span>
        <span className="bf-stat-chip" role="listitem">
          <em>{formatDurationSec(stats.activeMs)}</em> {t('options.behaviorForge.statActive')}
        </span>
        <span className="bf-stat-chip" role="listitem">
          <em>{formatDurationSec(stats.idleMs)}</em> {t('options.behaviorForge.statIdle')}
        </span>
        {net ? (
          <>
            <span className="bf-stat-chip" role="listitem">
              <em>{net.requestCount}</em> {t('options.behaviorForge.statRequests')}
            </span>
            <span className={`bf-stat-chip${net.errorCount ? ' warn' : ''}`} role="listitem">
              <em>{net.errorCount}</em> {t('options.behaviorForge.statErrors')}
            </span>
            <span className="bf-stat-chip" role="listitem">
              <em>{net.xhrCount}</em> {t('options.behaviorForge.statApi')}
            </span>
          </>
        ) : (
          <span className="bf-stat-chip muted" role="listitem">
            {t('options.behaviorForge.noNetwork')}
          </span>
        )}
      </div>

      {dwell.length > 1 ? (
        <details className="bf-dwell">
          <summary>{t('options.behaviorForge.dwellTitle')}</summary>
          <ul>
            {dwell.map((row) => (
              <li key={`${row.url}-${row.ms}`}>
                <span className="bf-dwell-ms">{formatDurationSec(row.ms)}</span>
                <span className="bf-dwell-url" title={row.url}>
                  {row.url}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}

      {net?.requests.length ? (
        <details className="bf-network-panel" open>
          <summary>{t('options.behaviorForge.networkTitle')}</summary>
          <NetworkWaterfall requests={net.requests} sessionDurationMs={session.durationMs} />
        </details>
      ) : net?.samples.length ? (
        <details className="bf-network-samples">
          <summary>{t('options.behaviorForge.networkTitle')}</summary>
          <ul>
            {net.samples.map((s, i) => (
              <li key={`${s.url}-${i}`}>
                <span className={`bf-net-status${s.status && s.status >= 400 ? ' err' : ''}`}>
                  {s.status ?? '…'}
                </span>
                <span className="bf-net-method">{s.method}</span>
                <span className="bf-net-url" title={s.url}>
                  {s.url}
                </span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  )
}
