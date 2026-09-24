import { useCallback, useEffect, useState } from 'react'

import { useI18n } from '../../../i18n'
import {
  deleteSession,
  listSessions,
  loadSession,
  markSessionCloudId,
  recordingStatus,
  startRecording,
  stopRecording,
} from '../api.js'
import type { BehaviorSessionMeta, BehaviorSessionRecord } from '../types.js'
import { uploadReplayToCloud } from '../../../lib/replay-sync.js'
import { loadBehaviorPrefs, saveBehaviorPrefs } from '../prefs.js'
import { ReplayViewport } from './ReplayViewport.js'
import { RrwebReplayViewport } from './RrwebReplayViewport.js'
import { ReplayDetailTabs } from './ReplayDetailTabs.js'
import { withNormalizedEvents } from '../replay-utils.js'

function formatMs(ms: number): string {
  const s = Math.floor(ms / 1000)
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m}:${String(rem).padStart(2, '0')}`
}

type Props = {
  embedded?: boolean
}

export function BehaviorForgePanel({ embedded = false }: Props) {
  const { t } = useI18n()
  const [sessions, setSessions] = useState<BehaviorSessionMeta[]>([])
  const [recording, setRecording] = useState(false)
  const [eventCount, setEventCount] = useState(0)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [session, setSession] = useState<BehaviorSessionRecord | null>(null)
  const [playing, setPlaying] = useState(false)
  const [timeMs, setTimeMs] = useState(0)
  const [durationMs, setDurationMs] = useState(0)
  const [error, setError] = useState<string | null>(null)
  const [replayMode, setReplayMode] = useState<'dom' | 'trail'>('dom')
  const [uploading, setUploading] = useState(false)
  const [captureDom, setCaptureDom] = useState(true)

  const refresh = useCallback(async () => {
    const [list, status] = await Promise.all([listSessions(), recordingStatus()])
    setSessions(list)
    setRecording(status.recording)
    setEventCount(status.eventCount)
  }, [])

  useEffect(() => {
    void loadBehaviorPrefs().then((prefs) => setCaptureDom(prefs.captureDom))
  }, [])

  useEffect(() => {
    void refresh()
    const id = window.setInterval(() => {
      if (recording) void recordingStatus().then((s) => setEventCount(s.eventCount))
    }, 1000)
    return () => window.clearInterval(id)
  }, [refresh, recording])

  useEffect(() => {
    if (!selectedId) {
      setSession(null)
      return
    }
    void loadSession(selectedId).then((record) => {
      if (!record) {
        setSession(null)
        return
      }
      const normalized = withNormalizedEvents(record)
      setSession(normalized)
      setTimeMs(0)
      setPlaying(false)
      setDurationMs(normalized.durationMs)
      setReplayMode(normalized.hasRrweb ? 'dom' : 'trail')
    })
  }, [selectedId])

  useEffect(() => {
    if (!playing) return
    let raf = 0
    let last = performance.now()
    const tick = (now: number) => {
      const dt = now - last
      last = now
      setTimeMs((prev) => {
        const next = Math.min(durationMs, prev + dt)
        if (next >= durationMs) setPlaying(false)
        return next
      })
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [playing, durationMs])

  const onStart = async () => {
    setError(null)
    try {
      const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
      if (!tab?.id) throw new Error(t('options.behaviorForge.needTab'))
      await startRecording(tab.id, captureDom)
      setRecording(true)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const onStop = async () => {
    setError(null)
    try {
      const record = await stopRecording()
      setRecording(false)
      await refresh()
      if (record) setSelectedId(record.id)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }

  const showDom = Boolean(session?.hasRrweb) && replayMode === 'dom'

  return (
    <div className={`bf-root${embedded ? ' bf-embedded' : ''}`}>
      <header className={embedded ? 'bf-embedded-head' : 'page-head bf-page-head'}>
        <div className="bf-head-copy">
          {!embedded ? <p className="eyebrow">{t('options.behaviorForge.eyebrow')}</p> : null}
          <h1 className={embedded ? 'bf-embedded-title' : undefined}>{t('options.behaviorForge.title')}</h1>
          <p className={embedded ? 'bf-embedded-lede' : 'lede'}>{t('options.behaviorForge.description')}</p>
        </div>
        <div className="bf-head-actions">
          {!recording ? (
            <label className="bf-capture-dom" title={t('options.behaviorForge.lightModeHint')}>
              <input
                type="checkbox"
                checked={!captureDom}
                onChange={(e) => {
                  const light = e.target.checked
                  const next = !light
                  setCaptureDom(next)
                  void saveBehaviorPrefs({ captureDom: next })
                }}
              />
              <span>{t('options.behaviorForge.lightMode')}</span>
            </label>
          ) : null}
          {recording ? (
            <span className="bf-rec-badge" aria-live="polite">
              <i aria-hidden /> {t('options.behaviorForge.recordingBadge')}
            </span>
          ) : null}
          {recording ? (
            <button type="button" className="button danger" onClick={() => void onStop()}>
              {t('options.behaviorForge.stop')} ({eventCount})
            </button>
          ) : (
            <button type="button" className="button primary" onClick={() => void onStart()}>
              {t('options.behaviorForge.start')}
            </button>
          )}
        </div>
      </header>

      {error ? (
        <div className="notice" role="alert">
          {error}
        </div>
      ) : null}

      {recording ? (
        <p className="hint bf-recording-hint">
          {captureDom
            ? t('options.behaviorForge.recordingHintDom')
            : t('options.behaviorForge.recordingHint')}
        </p>
      ) : (
        <p className="hint bf-mode-hint-line">{t('options.behaviorForge.idleHint')}</p>
      )}

      <div className="bf-studio">
        <aside className="panel-block bf-studio-sidebar">
          <div className="bf-sidebar-head">
            <h2>{t('options.behaviorForge.sessionsTitle')}</h2>
            <span className="bf-session-count">{sessions.length}</span>
          </div>
          {sessions.length === 0 ? (
            <p className="gf-empty">{t('options.behaviorForge.sessionsEmpty')}</p>
          ) : (
            <ul className="bf-session-list">
              {sessions.map((s) => (
                <li key={s.id} className="bf-session-item">
                  <button
                    type="button"
                    className={selectedId === s.id ? 'bf-session-row active' : 'bf-session-row'}
                    onClick={() => setSelectedId(s.id)}
                  >
                    <span className="bf-session-title" title={s.originUrl}>
                      {s.title}
                    </span>
                    <span className="bf-session-meta">
                      {formatMs(s.durationMs)} · {s.eventCount}
                      {s.hasRrweb ? ` · ${t('options.behaviorForge.domBadge')}` : ` · ${t('options.behaviorForge.lightBadge')}`}
                      {s.networkDigest ? ` · ${t('options.behaviorForge.netBadge')}` : ''}
                      {s.cloudId ? ` · ${t('options.behaviorForge.cloudBadge')}` : ''}
                    </span>
                  </button>
                  <button
                    type="button"
                    className="text-button danger bf-session-delete"
                    onClick={() => void deleteSession(s.id).then(refresh)}
                    aria-label={t('options.behaviorForge.delete')}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          )}
        </aside>

        <section className="panel-block bf-studio-main">
          {session ? (
            <>
              <div className="bf-session-header">
                <div>
                  <h2 className="bf-session-name">{session.title}</h2>
                  <p className="bf-session-url" title={session.originUrl}>
                    {session.originUrl}
                  </p>
                </div>
                <button
                  type="button"
                  className="button secondary"
                  disabled={uploading || Boolean(session.cloudId)}
                  onClick={() => {
                    setUploading(true)
                    setError(null)
                    void uploadReplayToCloud(session)
                      .then((cloudId) => markSessionCloudId(session.id, cloudId))
                      .then(() => refresh())
                      .catch((e) => setError(e instanceof Error ? e.message : String(e)))
                      .finally(() => setUploading(false))
                  }}
                >
                  {session.cloudId
                    ? t('options.behaviorForge.uploaded')
                    : uploading
                      ? t('options.behaviorForge.uploading')
                      : t('options.behaviorForge.upload')}
                </button>
              </div>

              <div className="bf-player-card">
                <div className="bf-replay-toolbar">
                  {session.hasRrweb ? (
                    <div className="bf-replay-mode" role="tablist" aria-label={t('options.behaviorForge.modeAria')}>
                      <button
                        type="button"
                        role="tab"
                        aria-selected={replayMode === 'dom'}
                        className={replayMode === 'dom' ? 'active' : ''}
                        onClick={() => setReplayMode('dom')}
                        title={t('options.behaviorForge.modeDomHint')}
                      >
                        <span className="bf-mode-label">{t('options.behaviorForge.modeDom')}</span>
                        <span className="bf-mode-hint">{t('options.behaviorForge.modeDomShort')}</span>
                      </button>
                      <button
                        type="button"
                        role="tab"
                        aria-selected={replayMode === 'trail'}
                        className={replayMode === 'trail' ? 'active' : ''}
                        onClick={() => setReplayMode('trail')}
                        title={t('options.behaviorForge.modeTrailHint')}
                      >
                        <span className="bf-mode-label">{t('options.behaviorForge.modeTrail')}</span>
                        <span className="bf-mode-hint">{t('options.behaviorForge.modeTrailShort')}</span>
                      </button>
                    </div>
                  ) : (
                    <p className="bf-mode-only-trail">{t('options.behaviorForge.trailOnlyHint')}</p>
                  )}
                  <div className="bf-replay-controls">
                    <button
                      type="button"
                      className="button secondary"
                      onClick={() => {
                        if (playing) setPlaying(false)
                        else {
                          if (timeMs >= durationMs) setTimeMs(0)
                          setPlaying(true)
                        }
                      }}
                    >
                      {playing ? t('options.behaviorForge.pause') : t('options.behaviorForge.play')}
                    </button>
                    <input
                      type="range"
                      min={0}
                      max={Math.max(1, durationMs)}
                      value={timeMs}
                      onChange={(e) => {
                        setPlaying(false)
                        setTimeMs(Number(e.target.value))
                      }}
                      className="bf-scrubber"
                      aria-label={t('options.behaviorForge.scrubberAria')}
                    />
                    <span className="bf-time">
                      {formatMs(timeMs)} / {formatMs(durationMs)}
                    </span>
                  </div>
                </div>

                {showDom ? (
                  <RrwebReplayViewport
                    session={session}
                    timeMs={timeMs}
                    playing={playing}
                    onDuration={setDurationMs}
                    noSnapshotLabel={t('options.behaviorForge.noDomSnapshot')}
                  />
                ) : (
                  <ReplayViewport session={session} timeMs={timeMs} onDuration={setDurationMs} />
                )}
              </div>

              <ReplayDetailTabs
                session={session}
                formatMs={formatMs}
                onSeek={(ms) => {
                  setPlaying(false)
                  setTimeMs(ms)
                }}
              />
            </>
          ) : (
            <div className="bf-empty-stage">
              <p className="gf-empty">{t('options.behaviorForge.pickSession')}</p>
              <p className="hint">{t('options.behaviorForge.emptyStageHint')}</p>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}
