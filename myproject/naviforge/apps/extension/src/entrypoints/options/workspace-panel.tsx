import { useEffect, useState } from 'react'
import { mcpHasErrors, parseMcpServersJson, type McpIssue } from '@naviforge/shared'
import type { WorkspaceEntry, WorkspaceSkill } from '@naviforge/runtime'

import { formatBytes } from '../../lib/format-bytes'
import { useI18n } from '../../i18n'
import {
  ensureLocalHelper,
  formatWorkspaceMtime,
  listWorkspaceFiles,
  loadDiskMcpFile,
  loadWorkspaceFileLists,
  persistMcpJsonToDisk,
  persistSkillDisabled,
  workspaceEmptyHint,
  workspaceRpc,
  type LocalHelperStatus,
} from '../../lib/local-workspace'
import { STORAGE } from '../../lib/settings'
import { VoiceCard } from '../../components/chat/voice-card'
import { Tabs } from './tabs'
import { BehaviorForgePanel } from '../../modules/behavior-forge/components/BehaviorForgePanel'
import { listSessions as listBehaviorSessions } from '../../modules/behavior-forge/api'

type DiskTab = 'config' | 'skills' | 'mcp' | 'logs' | 'shots' | 'audio' | 'pages' | 'scripts' | 'replay'

const LATEST_SHOTS = 50
const DISK_TABS: DiskTab[] = ['config', 'skills', 'mcp', 'logs', 'shots', 'audio', 'pages', 'scripts', 'replay']

function newestFirst(files: WorkspaceEntry[]): WorkspaceEntry[] {
  return [...files].sort((a, b) => (b.mtime ?? 0) - (a.mtime ?? 0) || b.name.localeCompare(a.name))
}

function emptyCopy(helper: LocalHelperStatus | null, ready: string): string {
  return workspaceEmptyHint(helper == null ? null : helper.ok, ready)
}

function fileMetaLabel(file: WorkspaceEntry, unit: string): string {
  const size = file.size != null ? formatBytes(file.size) : unit
  const time = formatWorkspaceMtime(file.mtime)
  return time ? `${time} · ${size}` : size
}

function DiskFiles({
  dir,
  files,
  empty,
  unit,
  scroll,
  openLabel,
}: {
  dir: string
  files: WorkspaceEntry[]
  empty: string
  unit: string
  scroll?: boolean
  openLabel: string
}) {
  return (
    <ul className={scroll ? 'file-list file-list-scroll' : 'file-list'}>
      {files.length === 0 ? <li className="file-empty">{empty}</li> : null}
      {files.map((file) => (
        <li className="file-row" key={file.name}>
          <span className="file-name" title={file.name}>
            {file.name}
          </span>
          <span className="file-meta">{fileMetaLabel(file, unit)}</span>
          <button
            className="text-button"
            onClick={() => void workspaceRpc('open', { path: `${dir}/${file.name}` })}
          >
            {openLabel}
          </button>
        </li>
      ))}
    </ul>
  )
}

function PageTitle({
  title,
  description,
  eyebrow,
}: {
  title: string
  description: string
  eyebrow: string
}) {
  return (
    <header className="page-title">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
    </header>
  )
}

export function WorkspacePanel() {
  const { t } = useI18n()
  const [helper, setHelper] = useState<LocalHelperStatus | null>(null)
  const [skills, setSkills] = useState<WorkspaceSkill[]>([])
  const [sessions, setSessions] = useState<WorkspaceEntry[]>([])
  const [shots, setShots] = useState<WorkspaceEntry[]>([])
  const [audioFiles, setAudioFiles] = useState<WorkspaceEntry[]>([])
  const [pageFiles, setPageFiles] = useState<WorkspaceEntry[]>([])
  const [scripts, setScripts] = useState<WorkspaceEntry[]>([])
  const [configFiles, setConfigFiles] = useState<WorkspaceEntry[]>([])
  const [mcpText, setMcpText] = useState('')
  const [mcpIssues, setMcpIssues] = useState<McpIssue[]>([])
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [listError, setListError] = useState('')
  const [tab, setTab] = useState<DiskTab>('config')
  const [replayCount, setReplayCount] = useState(0)

  async function refresh(status?: LocalHelperStatus): Promise<boolean> {
    const next = status ?? (await ensureLocalHelper())
    setHelper(next)
    if (!next.ok) {
      setSkills([])
      setSessions([])
      setShots([])
      setAudioFiles([])
      setPageFiles([])
      setScripts([])
      setConfigFiles([])
      setMcpText('')
      setMcpIssues([])
      setListError('')
      void listBehaviorSessions()
        .then((list) => setReplayCount(list.length))
        .catch(() => setReplayCount(0))
      return false
    }
    const [{ lists, errors }, skillScan, mcpFile, behaviorList] = await Promise.all([
      loadWorkspaceFileLists(
        ['sessions', 'shots', 'audio', 'pages', 'scripts', 'config'],
        listWorkspaceFiles
      ),
      workspaceRpc<{ skills: WorkspaceSkill[] }>('scanSkills').catch(() => ({ skills: [] })),
      loadDiskMcpFile(),
      listBehaviorSessions().catch(() => []),
    ])
    setReplayCount(behaviorList.length)
    setSkills(skillScan.skills)
    setSessions(lists.sessions ?? [])
    setShots(lists.shots ?? [])
    setAudioFiles(lists.audio ?? [])
    setPageFiles(lists.pages ?? [])
    setScripts(lists.scripts ?? [])
    setConfigFiles(lists.config ?? [])
    setMcpText(mcpFile?.text ?? '')
    setMcpIssues(mcpFile?.issues ?? [])
    setListError(errors.length ? errors.join('；') : '')
    return true
  }

  useEffect(() => {
    void (async () => {
      try {
        const ok = await refresh()
        if (!ok) {
          await new Promise((resolve) => setTimeout(resolve, 1000))
          await refresh()
        }
      } catch (error) {
        setNotice((error as Error).message)
      }
    })()
    void applyFocusFromStorage()
    const onChange = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string
    ): void => {
      if (area !== 'local') return
      if (changes[STORAGE.openWorkspaceDir] || changes[STORAGE.openWorkspaceNotice] || changes[STORAGE.openWorkspaceTab]) {
        void applyFocusFromStorage()
        void refresh()
      }
    }
    chrome.storage.onChanged.addListener(onChange)
    return () => chrome.storage.onChanged.removeListener(onChange)
  }, [])

  async function applyFocusFromStorage(): Promise<void> {
    const saved = await chrome.storage.local.get([
      STORAGE.openWorkspaceDir,
      STORAGE.openWorkspaceNotice,
      STORAGE.openWorkspaceTab,
    ])
    const dir = saved[STORAGE.openWorkspaceDir] as string | undefined
    const wsTab = saved[STORAGE.openWorkspaceTab] as string | undefined
    const banner = saved[STORAGE.openWorkspaceNotice] as string | undefined
    if (wsTab === 'replay') setTab('replay')
    else if (dir && DISK_TABS.includes(dir as DiskTab)) setTab(dir as DiskTab)
    if (banner) setNotice(banner)
    if (dir || banner || wsTab) {
      await chrome.storage.local.remove([
        STORAGE.openWorkspaceDir,
        STORAGE.openWorkspaceNotice,
        STORAGE.openWorkspaceTab,
      ])
    }
  }

  async function startHelper(): Promise<void> {
    setBusy(true)
    setNotice('')
    try {
      const next = await ensureLocalHelper()
      if (!next.ok) setNotice(next.error ?? t('options.notice.hostNotRunning'))
      await refresh(next)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <PageTitle
        eyebrow={t('options.workspace.eyebrow')}
        title={t('options.workspace.title')}
        description={t('options.workspace.description')}
      />
      {notice ? (
        <div className="notice" role="status">
          {notice}
        </div>
      ) : null}
      {listError ? (
        <div className="notice bad" role="status">
          {t('options.notice.partialListError', { detail: listError })}
        </div>
      ) : null}
      <section className="settings-layout">
        <div className="settings-copy">
          <span>{t('options.workspace.localDiskEyebrow')}</span>
          <h2>{t('options.workspace.localDiskTitle')}</h2>
          <p>{t('options.workspace.localDiskDesc')}</p>
        </div>
        <div className="settings-form">
          <p>
            <strong>{helper?.workspaceRoot || t('options.workspace.helperUnknown')}</strong>
          </p>
          <p>
            {t('options.workspace.helperLabel')}{' '}
            {helper?.ok ? (
              <span className="pill">{t('options.workspace.helperRunning')}</span>
            ) : (
              <span className="pill">{t('options.workspace.helperStopped')}</span>
            )}
          </p>
          <div className="button-row">
            <button className="button primary" disabled={busy} onClick={() => void startHelper()}>
              {helper?.ok ? t('options.common.buttons.refresh') : t('options.common.buttons.connectHost')}
            </button>
            <button
              className="button secondary"
              disabled={!helper?.ok}
              onClick={() =>
                void workspaceRpc('open', {}).then(() => setNotice(t('options.notice.finderOpenRequested')))
              }
            >
              {t('options.common.buttons.openInFinder')}
            </button>
          </div>
          {!helper?.ok ? <p className="tab-lead">{t('options.workspace.installHint')}</p> : null}
        </div>
      </section>

      <Tabs
        value={tab}
        onChange={setTab}
        items={[
          { id: 'replay', label: t('options.workspace.tabs.replay', { count: replayCount }) },
          { id: 'config', label: t('options.workspace.tabs.config', { count: configFiles.length }) },
          { id: 'skills', label: t('options.workspace.tabs.skills', { count: skills.length }) },
          { id: 'mcp', label: t('options.workspace.tabs.mcp') },
          { id: 'logs', label: t('options.workspace.tabs.logs', { count: sessions.length }) },
          { id: 'shots', label: t('options.workspace.tabs.shots', { count: shots.length }) },
          { id: 'audio', label: t('options.workspace.tabs.audio', { count: audioFiles.length }) },
          { id: 'pages', label: t('options.workspace.tabs.pages', { count: pageFiles.length }) },
          { id: 'scripts', label: t('options.workspace.tabs.scripts', { count: scripts.length }) },
        ]}
      />

      {tab === 'replay' ? <BehaviorForgePanel embedded /> : null}

      {tab === 'config' ? (
        <>
          <p className="tab-lead">{t('options.workspace.configLead')}</p>
          <DiskFiles
            dir="config"
            files={newestFirst(configFiles)}
            empty={emptyCopy(helper, t('options.workspace.configEmptyReady'))}
            unit={t('options.workspace.units.json')}
            openLabel={t('options.common.buttons.open')}
          />
        </>
      ) : null}

      {tab === 'skills' ? (
        <>
          <p className="tab-lead">{t('options.workspace.skillsLead')}</p>
          <div className="registry-list">
            {skills.length === 0 ? (
              <p className="tab-lead">{emptyCopy(helper, t('options.workspace.skillsEmptyReady'))}</p>
            ) : null}
            {skills.map((skill) => (
              <article className="registry-item" key={skill.id}>
                <div className="registry-main">
                  <div className="registry-title">
                    <h3>{skill.id}</h3>
                    <span className="pill">
                      {skill.enabled ? t('options.common.status.on') : t('options.common.status.off')}
                    </span>
                    <span className="version">{t('options.common.labels.version', { version: skill.version })}</span>
                  </div>
                  <p>{skill.description}</p>
                  <div className="metadata">
                    <span>{skill.relativePath}</span>
                    {skill.files?.length ? (
                      <span>
                        {t('options.skill.bundledFiles', { count: skill.files.length })}
                      </span>
                    ) : null}
                  </div>
                </div>
                <div className="registry-actions">
                  <label className="switch">
                    <input
                      type="checkbox"
                      checked={skill.enabled}
                      onChange={() =>
                        void persistSkillDisabled(skill.id, skill.enabled).then(() => refresh())
                      }
                    />
                    <span />
                  </label>
                  <button
                    className="text-button"
                    onClick={() => void workspaceRpc('open', { path: skill.relativePath })}
                  >
                    {t('options.common.buttons.open')}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </>
      ) : null}

      {tab === 'mcp' ? (
        <>
          <p className="tab-lead">{t('options.workspace.mcpLead')}</p>
          <div className="settings-form">
            <textarea
              className="mcp-json"
              value={mcpText}
              spellCheck={false}
              disabled={!helper?.ok}
              onChange={(event) => {
                const text = event.target.value
                setMcpText(text)
                setMcpIssues(parseMcpServersJson(text).issues)
              }}
            />
            {mcpIssues.length ? (
              <ul className="mcp-issues">
                {mcpIssues.map((issue, index) => (
                  <li key={`${issue.level}-${index}`} className={issue.level}>
                    <strong>
                      {issue.level === 'error'
                        ? t('options.plugins.mcp.issueError')
                        : t('options.plugins.mcp.issueHint')}
                      {issue.server ? ` · ${issue.server}` : ''}
                    </strong>
                    <span>{issue.message}</span>
                    <small>{issue.hint}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="tab-lead">{t('options.plugins.mcp.noValidationErrors')}</p>
            )}
            <div className="button-row">
              <button
                className="button primary"
                disabled={!helper?.ok || busy || mcpHasErrors(mcpIssues)}
                onClick={() =>
                  void persistMcpJsonToDisk(mcpText)
                    .then(() => {
                      setNotice(t('options.notice.mcpWritten'))
                      return refresh()
                    })
                    .catch((error) => setNotice((error as Error).message))
                }
              >
                {t('options.common.buttons.saveToDisk')}
              </button>
              <button
                className="button secondary"
                disabled={!helper?.ok}
                onClick={() =>
                  void workspaceRpc('open', { path: 'mcp/servers.json' }).then(() =>
                    setNotice(t('options.notice.mcpFileOpenRequested'))
                  )
                }
              >
                {t('options.common.buttons.openFile')}
              </button>
            </div>
          </div>
        </>
      ) : null}

      {tab === 'logs' ? (
        <>
          <p className="tab-lead">{t('options.workspace.logsLead')}</p>
          <DiskFiles
            dir="sessions"
            files={newestFirst(sessions).slice(0, LATEST_SHOTS)}
            empty={emptyCopy(helper, t('options.workspace.logsEmptyReady'))}
            unit={t('options.workspace.units.file')}
            scroll
            openLabel={t('options.common.buttons.open')}
          />
        </>
      ) : null}

      {tab === 'shots' ? (
        <>
          <p className="tab-lead">
            {t('options.workspace.shotsLead', { count: LATEST_SHOTS })}
          </p>
          <DiskFiles
            dir="shots"
            files={newestFirst(shots).slice(0, LATEST_SHOTS)}
            empty={emptyCopy(helper, t('options.workspace.shotsEmptyReady'))}
            unit={t('options.workspace.units.png')}
            scroll
            openLabel={t('options.common.buttons.open')}
          />
        </>
      ) : null}

      {tab === 'audio' ? (
        <>
          <p className="tab-lead">
            {t('options.workspace.audioLead', { count: LATEST_SHOTS })}
          </p>
          <ul className="file-list file-list-scroll">
            {audioFiles.length === 0 ? (
              <li className="file-empty">{emptyCopy(helper, t('options.workspace.audioEmptyReady'))}</li>
            ) : null}
            {newestFirst(audioFiles)
              .slice(0, LATEST_SHOTS)
              .map((file) => (
                <li className="file-row" key={file.name}>
                  <span className="file-name" title={file.name}>
                    {file.name}
                  </span>
                  <span className="file-meta">{fileMetaLabel(file, t('options.workspace.units.audio'))}</span>
                  <VoiceCard path={`audio/${file.name}`} compact lazy />
                  <button
                    className="text-button"
                    onClick={() => void workspaceRpc('open', { path: `audio/${file.name}` })}
                  >
                    {t('options.common.buttons.open')}
                  </button>
                </li>
              ))}
          </ul>
        </>
      ) : null}

      {tab === 'pages' ? (
        <>
          <p className="tab-lead">
            {t('options.workspace.pagesLead', { count: LATEST_SHOTS })}
          </p>
          <DiskFiles
            dir="pages"
            files={newestFirst(pageFiles).slice(0, LATEST_SHOTS)}
            empty={emptyCopy(helper, t('options.workspace.pagesEmptyReady'))}
            unit={t('options.workspace.units.file')}
            scroll
            openLabel={t('options.common.buttons.open')}
          />
        </>
      ) : null}

      {tab === 'scripts' ? (
        <>
          <p className="tab-lead">{t('options.workspace.scriptsLead')}</p>
          <DiskFiles
            dir="scripts"
            files={newestFirst(scripts)}
            empty={emptyCopy(helper, t('options.workspace.scriptsEmptyReady'))}
            unit={t('options.workspace.units.script')}
            openLabel={t('options.common.buttons.open')}
          />
        </>
      ) : null}
    </>
  )
}
