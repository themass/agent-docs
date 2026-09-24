import { useMemo, useState } from 'react'

import { useI18n } from '../../../i18n'
import type { BehaviorEvent, BehaviorSessionRecord } from '../types.js'
import { formatDurationSec, pageDwellLines, statsForSession } from '../session-stats.js'
import { normalizeSessionEvents } from '../replay-utils.js'
import { NetworkWaterfall } from './NetworkWaterfall.js'

type TabId = 'overview' | 'pages' | 'network' | 'timeline'

type Props = {
  session: BehaviorSessionRecord
  onSeek: (ms: number) => void
  formatMs: (ms: number) => string
}

export function ReplayDetailTabs({ session, onSeek, formatMs }: Props) {
  const { t } = useI18n()
  const [tab, setTab] = useState<TabId>('overview')

  const events = useMemo(() => normalizeSessionEvents(session.events), [session.events])
  const stats = useMemo(() => statsForSession({ ...session, events }), [session, events])
  const dwell = useMemo(() => pageDwellLines(events), [events])
  const timeline = useMemo(() => events.filter((e) => e.kind !== 'pointer').slice(0, 300), [events])
  const net = session.networkDigest

  const tabs: Array<{ id: TabId; label: string; badge?: number }> = [
    { id: 'overview', label: t('options.behaviorForge.tabOverview') },
    { id: 'pages', label: t('options.behaviorForge.tabPages'), badge: dwell.length || undefined },
    {
      id: 'network',
      label: t('options.behaviorForge.tabNetwork'),
      badge: net?.requestCount || net?.samples.length || undefined,
    },
    { id: 'timeline', label: t('options.behaviorForge.tabTimeline'), badge: timeline.length || undefined },
  ]

  return (
    <div className="bf-detail-tabs">
      <div className="bf-detail-tablist" role="tablist" aria-label={t('options.behaviorForge.detailTabsAria')}>
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? 'bf-detail-tab active' : 'bf-detail-tab'}
            onClick={() => setTab(item.id)}
          >
            <span>{item.label}</span>
            {item.badge != null && item.badge > 0 ? (
              <span className="bf-detail-tab-badge">{item.badge}</span>
            ) : null}
          </button>
        ))}
      </div>

      <div className="bf-detail-panel" role="tabpanel">
        {tab === 'overview' ? (
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
        ) : null}

        {tab === 'pages' ? (
          dwell.length ? (
            <ul className="bf-dwell-list">
              {dwell.map((row) => (
                <li key={`${row.url}-${row.ms}`}>
                  <span className="bf-dwell-ms">{formatDurationSec(row.ms)}</span>
                  <span className="bf-dwell-url" title={row.url}>
                    {row.url}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="gf-empty">{t('options.behaviorForge.pagesEmpty')}</p>
          )
        ) : null}

        {tab === 'network' ? (
          net?.requests.length ? (
            <NetworkWaterfall requests={net.requests} sessionDurationMs={session.durationMs} />
          ) : net?.samples.length ? (
            <ul className="bf-network-samples-list">
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
          ) : (
            <p className="gf-empty">{t('options.behaviorForge.noNetwork')}</p>
          )
        ) : null}

        {tab === 'timeline' ? (
          timeline.length ? (
            <ul className="bf-timeline">
              {timeline.map((e, i) => (
                <li key={`${e.t}-${i}`}>
                  <button type="button" className="bf-timeline-row" onClick={() => onSeek(e.t)}>
                    <span>{formatMs(e.t)}</span>
                    <span className={`bf-kind bf-kind-${e.kind}`}>{e.kind}</span>
                    <span className="bf-timeline-meta">{timelineMeta(e)}</span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="gf-empty">{t('options.behaviorForge.timelineEmpty')}</p>
          )
        ) : null}
      </div>
    </div>
  )
}

function timelineMeta(e: BehaviorEvent): string {
  if (e.kind === 'click') return `${e.tag ?? 'click'} @ ${e.x},${e.y}`
  if (e.kind === 'nav') return e.url
  if (e.kind === 'scroll') return `${e.scrollX},${e.scrollY}`
  if (e.kind === 'idle') return `${Math.round(e.durationMs / 1000)}s`
  if (e.kind === 'key') return e.key
  return ''
}
