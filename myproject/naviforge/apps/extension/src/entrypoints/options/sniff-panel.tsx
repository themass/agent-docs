import { useCallback, useEffect, useState } from 'react'

import { useI18n } from '../../i18n'
import {
  downloadSniffJson,
  getActiveTab,
  hostFromUrl,
  sniffFlush,
  sniffListApis,
  sniffListSamples,
  sniffStart,
  sniffStatus,
  sniffStop,
} from '../../lib/sniff-actions'
import type { SniffApi, SniffProject, SniffSample } from '../../lib/sniff-model'
import {
  createSniffProject,
  deleteSniffProject,
  exportSniffProjectJson,
  listSniffProjects,
} from '../../lib/sniff-store'

function formatTs(ts: number): string {
  return new Date(ts).toLocaleString()
}

export function SniffPanel({
  onNotice,
  reloadNonce = 0,
}: {
  onNotice: (message: string) => void
  reloadNonce?: number
}) {
  const { t } = useI18n()
  const [projects, setProjects] = useState<SniffProject[]>([])
  const [selectedId, setSelectedId] = useState<string>('')
  const [apis, setApis] = useState<SniffApi[]>([])
  const [selectedApiId, setSelectedApiId] = useState<string>('')
  const [samples, setSamples] = useState<SniffSample[]>([])
  const [name, setName] = useState('')
  const [origin, setOrigin] = useState('')
  const [tabId, setTabId] = useState<number | undefined>()
  const [liveCount, setLiveCount] = useState(0)
  const [busy, setBusy] = useState('')

  const selected = projects.find((project) => project.id === selectedId)
  const selectedApi = apis.find((api) => api.id === selectedApiId)
  const recording = selected?.status === 'recording'

  const reloadProjects = useCallback(async () => {
    const next = await listSniffProjects()
    setProjects(next)
    if (!selectedId && next[0]) setSelectedId(next[0].id)
  }, [selectedId])

  const reloadApis = useCallback(async (projectId: string) => {
    if (!projectId) {
      setApis([])
      return
    }
    setApis(await sniffListApis(projectId))
  }, [])

  const reloadSamples = useCallback(async (apiId: string) => {
    if (!apiId) {
      setSamples([])
      return
    }
    setSamples(await sniffListSamples(apiId))
  }, [])

  useEffect(() => {
    void reloadProjects()
    void getActiveTab().then((tab) => {
      setTabId(tab?.id)
      setOrigin(hostFromUrl(tab?.url))
      if (!name) setName(hostFromUrl(tab?.url) || 'Sniff project')
    })
  }, [name, reloadProjects, reloadNonce])

  useEffect(() => {
    if (!selectedId) return
    void reloadApis(selectedId)
  }, [selectedId, reloadApis, projects])

  useEffect(() => {
    if (!selectedApiId) return
    void reloadSamples(selectedApiId)
  }, [selectedApiId, reloadSamples])

  useEffect(() => {
    if (!recording || !tabId) {
      setLiveCount(0)
      return
    }
    let cancelled = false
    const tick = async () => {
      const status = await sniffStatus(tabId)
      if (!cancelled) setLiveCount(status.live)
    }
    void tick()
    const timer = window.setInterval(() => void tick(), 1500)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [recording, tabId])

  async function handleCreate(): Promise<void> {
    setBusy('create')
    try {
      const project = await createSniffProject(name, origin)
      setSelectedId(project.id)
      await reloadProjects()
      onNotice(t('options.notice.sniffProjectCreated', { name: project.name }))
    } catch (error) {
      onNotice(t('options.notice.sniffCreateFailed', { message: (error as Error).message }))
    } finally {
      setBusy('')
    }
  }

  async function handleStart(): Promise<void> {
    if (!selected || !tabId) {
      onNotice(t('options.notice.sniffSelectTab'))
      return
    }
    setBusy('start')
    try {
      await sniffStart(selected.id, tabId)
      await reloadProjects()
      onNotice(t('options.notice.sniffRecordingStarted'))
    } catch (error) {
      onNotice(t('options.notice.sniffStartFailed', { message: (error as Error).message }))
    } finally {
      setBusy('')
    }
  }

  async function handleStop(): Promise<void> {
    if (!selected || !tabId) return
    setBusy('stop')
    try {
      const ingested = await sniffStop(tabId, selected.id)
      await reloadProjects()
      await reloadApis(selected.id)
      onNotice(t('options.notice.sniffStopped', { count: ingested.samples }))
    } catch (error) {
      onNotice(t('options.notice.sniffStopFailed', { message: (error as Error).message }))
    } finally {
      setBusy('')
    }
  }

  async function handleFlush(): Promise<void> {
    if (!selected || !tabId) return
    setBusy('flush')
    try {
      const ingested = await sniffFlush(tabId, selected.id)
      await reloadApis(selected.id)
      onNotice(t('options.notice.sniffSynced', { count: ingested.samples }))
    } catch (error) {
      onNotice(t('options.notice.sniffSyncFailed', { message: (error as Error).message }))
    } finally {
      setBusy('')
    }
  }

  async function handleExport(): Promise<void> {
    if (!selected) return
    const json = await exportSniffProjectJson(selected.id)
    if (!json) {
      onNotice(t('options.notice.sniffExportFailed'))
      return
    }
    downloadSniffJson(`${selected.name.replace(/\s+/g, '-').toLowerCase()}-sniff.json`, json)
    onNotice(t('options.notice.sniffExported'))
  }

  async function handleDelete(): Promise<void> {
    if (!selected || !window.confirm(t('options.confirm.deleteSniffProject', { name: selected.name }))) return
    await deleteSniffProject(selected.id)
    setSelectedId('')
    setSelectedApiId('')
    await reloadProjects()
    onNotice(t('options.notice.sniffDeleted'))
  }

  return (
    <div className="sniff-layout">
      <section className="sniff-column">
        <div className="filter-bar">
          <strong>{t('options.sniff.projectsTitle')}</strong>
          <span>{projects.length} {t('options.common.labels.total')}</span>
        </div>
        <div className="settings-form compact">
          <label>
            {t('options.sniff.nameLabel')}
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder={t('options.sniff.namePlaceholder')}
            />
          </label>
          <label>
            {t('options.sniff.originLabel')}
            <input
              value={origin}
              onChange={(event) => setOrigin(event.target.value)}
              placeholder={t('options.sniff.originPlaceholder')}
            />
          </label>
          <div className="button-row compact">
            <button className="button secondary" disabled={busy === 'create'} onClick={() => void handleCreate()}>
              {t('options.common.buttons.createProject')}
            </button>
          </div>
        </div>
        <div className="sniff-project-list">
          {!projects.length && (
            <div className="empty">
              <strong>{t('options.sniff.emptyTitle')}</strong>
              <span>{t('options.sniff.emptyBody')}</span>
            </div>
          )}
          {projects.map((project) => (
            <button
              key={project.id}
              className={`sniff-project-card${project.id === selectedId ? ' active' : ''}`}
              onClick={() => {
                setSelectedId(project.id)
                setSelectedApiId('')
              }}
            >
              <div className="playbook-top">
                <span>
                  {project.status === 'recording'
                    ? t('options.common.status.recording')
                    : t('options.common.status.idle')}
                </span>
                <span>{formatTs(project.updatedAt)}</span>
              </div>
              <h3>{project.name}</h3>
              <p>{project.origin || t('options.sniff.allHttps')}</p>
              <span>
                {project.status === 'recording'
                  ? `${t('options.common.status.live')} · ${liveCount}`
                  : t('options.common.status.clickToSelect')}
              </span>
            </button>
          ))}
        </div>
      </section>

      <section className="sniff-column">
        {selected ? (
          <>
            <div className="button-row compact">
              {!recording ? (
                <button className="button primary" disabled={!!busy} onClick={() => void handleStart()}>
                  {t('options.common.buttons.startRecording')}
                </button>
              ) : (
                <button className="button primary" disabled={!!busy} onClick={() => void handleStop()}>
                  {t('options.common.buttons.stopAndIngest')}
                </button>
              )}
              <button className="button secondary" disabled={!!busy || !recording} onClick={() => void handleFlush()}>
                {t('options.common.buttons.syncSamples')}
              </button>
              <button className="button secondary" onClick={() => void handleExport()}>
                {t('options.common.buttons.exportJson')}
              </button>
              <button className="text-button danger" onClick={() => void handleDelete()}>
                {t('options.common.buttons.delete')}
              </button>
            </div>
            <p className="sniff-hint">
              {t('options.sniff.hint')}
              {tabId
                ? ` ${t('options.sniff.activeTab', { id: tabId })}`
                : ` ${t('options.sniff.noActiveTab')}`}
            </p>
            <div className="filter-bar">
              <strong>{t('options.sniff.apiTitle')}</strong>
              <span>{apis.length} {t('options.common.labels.endpoints')}</span>
            </div>
            <div className="sniff-api-list">
              {!apis.length && (
                <div className="empty">
                  <strong>{t('options.sniff.apiEmptyTitle')}</strong>
                  <span>{t('options.sniff.apiEmptyBody')}</span>
                </div>
              )}
              {apis.map((api) => (
                <button
                  key={api.id}
                  className={`sniff-api-row${api.id === selectedApiId ? ' active' : ''}`}
                  onClick={() => setSelectedApiId(api.id)}
                >
                  <span className="method">{api.method}</span>
                  <span className="url">{api.displayUrl}</span>
                  <span className="meta">
                    {api.sampleCount} · {api.lastStatus ?? t('options.common.labels.dash')}
                  </span>
                </button>
              ))}
            </div>
          </>
        ) : (
          <div className="empty">
            <strong>{t('options.sniff.selectProjectTitle')}</strong>
            <span>{t('options.sniff.selectProjectBody')}</span>
          </div>
        )}
      </section>

      <section className="sniff-column">
        {selectedApi ? (
          <>
            <div className="filter-bar">
              <strong>{selectedApi.method}</strong>
              <span>{selectedApi.displayUrl}</span>
            </div>
            {selectedApi.outputSchema && (
              <pre className="sniff-schema">{JSON.stringify(selectedApi.outputSchema, null, 2)}</pre>
            )}
            <div className="sniff-sample-list">
              {samples.map((sample) => (
                <article className="sniff-sample-card" key={sample.id}>
                  <div className="playbook-top">
                    <span>{sample.status ?? t('options.common.labels.dash')}</span>
                    <span>{formatTs(sample.ts)}</span>
                  </div>
                  <p className="mono">{sample.url}</p>
                  {sample.resBody && <pre className="sniff-body">{sample.resBody.slice(0, 1200)}</pre>}
                </article>
              ))}
            </div>
          </>
        ) : (
          <div className="empty">
            <strong>{t('options.sniff.selectApiTitle')}</strong>
            <span>{t('options.sniff.selectApiBody')}</span>
          </div>
        )}
      </section>
    </div>
  )
}
