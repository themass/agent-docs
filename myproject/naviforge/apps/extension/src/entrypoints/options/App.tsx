import { useEffect, useMemo, useRef, useState, type ChangeEvent, type ReactNode } from 'react'
import type { Playbook } from '@naviforge/playbook'
import type { ScriptArtifact } from '@naviforge/runtime'
import type { Skill } from '@naviforge/skill-runtime'
import {
  formatMcpJsonText,
  mcpHasErrors,
  parseMcpServersJson,
  serializeMcpServersJson,
  type McpIssue,
  type NormalizedMcpServer,
} from '@naviforge/shared'

import { addActivity, updateActivity } from '../../lib/activity-store'
import { NewApiAuthPanel } from '../../components/newapi-auth-panel'
import { AccountLoginPage } from '../../components/account-login-page'
import {
  fetchGitHubSkillResources,
  parseGitHubSkill,
  parseGitHubSkillUrl,
  type InstalledGitHubSkill,
} from '../../lib/github-skill'
import { BUILTIN_TOOL_CATALOG } from '../../lib/builtin-tools'
import { clearPlaybooks, deletePlaybook, listPlaybooks, savePlaybook } from '../../lib/playbook-store'
import { clearScripts, createChromeScriptPlane, listScripts } from '../../lib/chrome-script-plane'
import { clearSessions, listSessions, listThreads } from '../../lib/session-store'
import { buildSessionAuditExport, downloadSessionAudit } from '../../lib/session-export'
import { deleteProfile, listLearnedProfiles } from '../../lib/site-profile-store'
import { isManagedLoginEnabled, setManagedLoginEnabled } from '../../lib/managed-login-feature'
import type { SiteProfile } from '../../lib/content-extract'
import {
  addModelProfile,
  getActiveModelProfile,
  loadModelProfiles,
  profileToLlmConfig,
  removeModelProfile,
  saveModelProfiles,
  setActiveModelProfile,
  setOcrModelProfile,
  stripModelProfileApiKeys,
  testModelProfile,
  upsertModelProfile,
  THINKING_MODES,
  THINKING_LABELS,
  normalizeThinkingMode,
  type ModelProfile,
  type ModelProfilesStore,
} from '../../lib/llm-profiles'
import type { AgentSession } from '../../lib/session-model'
import { SessionTranscript } from './session-transcript'
import { McpDiscoveryPanel } from './mcp-discovery-panel'
import type { AgentThread } from '../../lib/thread-model'
import {
  DEFAULT_HOST,
  DEFAULT_PRIVACY,
  seedMcpConnections,
  STORAGE,
  loadCustomSkills,
  mergeInstalledSkills,
  readWebSearchSettings,
  DEFAULT_WEB_SEARCH,
  normalizeMaxAgentSteps,
  normalizeRunTimeoutMs,
  normalizeSameFailureLimit,
  normalizeTokenBudget,
  normalizeMaxInputTokens,
  normalizePrivacySettings,
  runTimeoutMinutes,
  DEFAULT_MAX_AGENT_STEPS,
  DEFAULT_RUN_TIMEOUT_MS,
  DEFAULT_SAME_FAILURE_LIMIT,
  DEFAULT_TOKEN_BUDGET,
  DEFAULT_MAX_INPUT_TOKENS,
  type HostSettings,
  type McpConnection,
  type PrivacySettings,
} from '../../lib/settings'
import { DEFAULT_VOICE_UI, readVoiceUiMode, type VoiceUiMode } from '../../lib/voice-ui'
import {
  DEFAULT_SPEECH_LANG_CONFIG,
  persistSpeechLangConfig,
  readSpeechLangConfig,
  SPEECH_RECOGNITION_LANGS,
  type SpeechLangConfig,
  type SpeechRecognitionLang,
} from '../../lib/speech-lang'
import { BUNDLED_SKILLS } from '../../skills/catalog'
import { hydrateDiskConfig, syncDiskConfigFromPartial } from '../../lib/disk-config'
import {
  persistMcpJsonToDisk,
  persistSkillDisabled,
  persistSkillFiles,
  persistSkillToDisk,
  loadDiskMcpFile,
  workspaceRpc,
  ensureLocalHelper,
} from '../../lib/local-workspace'
import { openSidePanelWithGesture, openWorkspaceTab } from '../../lib/surface-launch'
import { PRIVACY_POLICY_URL } from '../../lib/compliance'
import { LOCALES, LOCALE_LABELS, useI18n, type LocalePreference } from '../../i18n'
import { BrandMark } from '../../components/brand-mark'
import { AdBanner } from '../../components/ad-banner'
import { SniffPanel } from './sniff-panel'
import { listLearnedRecipes } from '../../lib/site-recipe-store'
import { SiteRecipesPanel } from './site-recipes-panel'
import { ToolkitPanel } from './toolkit-panel'
import { ModifyHeadersPrivacyToggle } from './modify-headers-privacy-toggle'
import { AgentCapabilitiesEditor } from '../../components/chat/agent-capabilities-editor'
import { WorkspacePanel } from './workspace-panel'
import { GeniusFallPanel } from '../../modules/genius-fall/components/GeniusFallPanel'
import { Tabs } from './tabs'
import {
  NAV_ITEMS,
  nextCopyTitle,
  parseImportedSkill,
  sectionFromHash,
  type Section,
} from './model'

type PluginTab = 'skills' | 'mcp' | 'tools'
type AutomationTab = 'playbooks' | 'scripts' | 'profiles' | 'recipes' | 'sessions' | 'sniff'
type SettingsTab = 'agent' | 'privacy' | 'system'

function normalizeSettingsTab(tab: string | undefined): SettingsTab | undefined {
  if (!tab) return undefined
  if (tab === 'agent' || tab === 'privacy' || tab === 'system') return tab
  if (tab === 'models') return 'agent'
  if (tab === 'permissions') return 'privacy'
  if (tab === 'host' || tab === 'advanced') return 'system'
  return undefined
}
type HostState = 'unchecked' | 'online' | 'offline'

function PageTitle({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string
  title: string
  description: string
  action?: ReactNode
}) {
  return (
    <header className="page-title">
      <div>
        <span className="eyebrow">{eyebrow}</span>
        <h1>{title}</h1>
        <p>{description}</p>
      </div>
      {action && <div className="page-action">{action}</div>}
    </header>
  )
}

function Toggle({
  checked,
  onChange,
  label,
  description,
}: {
  checked: boolean
  onChange: (checked: boolean) => void
  label: string
  description?: string
}) {
  return (
    <label className="toggle-row">
      <span>
        <strong>{label}</strong>
        {description && <small>{description}</small>}
      </span>
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
    </label>
  )
}

function StatusDot({ state }: { state: 'on' | 'off' | 'warn' }) {
  return <span className={`status-dot ${state}`} aria-hidden="true" />
}

function Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: ReactNode
}) {
  return (
    <label className="field">
      <span>{label}</span>
      {children}
      {hint && <small>{hint}</small>}
    </label>
  )
}

function asNormalized(connection: McpConnection): NormalizedMcpServer {
  return {
    id: connection.id,
    name: connection.name,
    transport: connection.transport,
    command: connection.command,
    args: connection.args,
    env: connection.env,
    envFile: connection.envFile,
    cwd: connection.cwd,
    endpoint: connection.endpoint,
    headers: connection.headers,
    enabled: connection.enabled,
    allowedTools: connection.allowedTools,
    extra: connection.extra,
  }
}

function mergeMcpRuntime(servers: NormalizedMcpServer[], previous: McpConnection[]): McpConnection[] {
  const byId = new Map(previous.map((item) => [item.id, item]))
  return servers.map((server) => {
    const prev = byId.get(server.id)
    return {
      ...server,
      discoveredTools: prev?.discoveredTools,
      checkedAt: prev?.checkedAt,
    }
  })
}

export function App() {
  const { t, preference, setPreference } = useI18n()
  const [section, setSection] = useState<Section>(() => sectionFromHash())
  const [pluginTab, setPluginTab] = useState<PluginTab>('skills')
  const [automationTab, setAutomationTab] = useState<AutomationTab>('playbooks')
  const [sniffReload, setSniffReload] = useState(0)
  const [settingsTab, setSettingsTab] = useState<SettingsTab>('agent')
  const [modelProfiles, setModelProfiles] = useState<ModelProfilesStore | null>(null)
  const [editingProfileId, setEditingProfileId] = useState('')
  const [host, setHost] = useState(DEFAULT_HOST)
  const [hostState, setHostState] = useState<HostState>('unchecked')
  const [privacy, setPrivacy] = useState(DEFAULT_PRIVACY)
  const [webSearch, setWebSearch] = useState(DEFAULT_WEB_SEARCH)
  const [connections, setConnections] = useState<McpConnection[]>([])
  const [mcpJson, setMcpJson] = useState('')
  const [mcpIssues, setMcpIssues] = useState<McpIssue[]>([])
  const [customSkills, setCustomSkills] = useState<Skill[]>([])
  const [disabledSkills, setDisabledSkills] = useState<string[]>([])
  const [playbooks, setPlaybooks] = useState<Playbook[]>([])
  const [siteProfiles, setSiteProfiles] = useState<SiteProfile[]>([])
  const [disabledPlaybooks, setDisabledPlaybooks] = useState<string[]>([])
  const [sessions, setSessions] = useState<AgentSession[]>([])
  const [scripts, setScripts] = useState<ScriptArtifact[]>([])
  const [recipeCount, setRecipeCount] = useState(0)
  const [managedLoginEnabled, setManagedLoginEnabledState] = useState(false)
  const [threads, setThreads] = useState<AgentThread[]>([])
  const [skillDraft, setSkillDraft] = useState('')
  const [githubSkillUrl, setGithubSkillUrl] = useState('')
  const [githubSkillPreview, setGithubSkillPreview] = useState<InstalledGitHubSkill | null>(null)
  const [mcpQuickUrl, setMcpQuickUrl] = useState('')
  const [showSkillImport, setShowSkillImport] = useState(false)
  const [query, setQuery] = useState('')
  const [notice, setNotice] = useState('')
  const noticeTimer = useRef<number | null>(null)
  const [testingModel, setTestingModel] = useState(false)
  const [voiceUi, setVoiceUi] = useState<VoiceUiMode>(DEFAULT_VOICE_UI)
  const [speechLangConfig, setSpeechLangConfig] = useState<SpeechLangConfig>(DEFAULT_SPEECH_LANG_CONFIG)

  function flashNotice(message: string, ms = 2200): void {
    if (noticeTimer.current != null) window.clearTimeout(noticeTimer.current)
    setNotice(message)
    if (!message) {
      noticeTimer.current = null
      return
    }
    noticeTimer.current = window.setTimeout(() => {
      setNotice('')
      noticeTimer.current = null
    }, ms)
  }

  const editingProfile =
    modelProfiles?.profiles.find((profile) => profile.id === editingProfileId) ??
    (modelProfiles ? getActiveModelProfile(modelProfiles) : null)

  function patchEditingProfile(patch: Partial<ModelProfile>): void {
    if (!modelProfiles || !editingProfile) return
    setModelProfiles(upsertModelProfile(modelProfiles, { ...editingProfile, ...patch }))
  }

  async function persistModelProfiles(next: ModelProfilesStore, notice: string): Promise<void> {
    setModelProfiles(next)
    await saveModelProfiles(next)
    flashNotice(notice)
  }

  async function persistModelsTab(notice: string): Promise<void> {
    if (!modelProfiles) return
    setModelProfiles(modelProfiles)
    await saveModelProfiles(modelProfiles)
    await chrome.storage.local.set({
      [STORAGE.privacy]: privacy,
      [STORAGE.webSearch]: webSearch,
    })
    await syncDiskConfigFromPartial({
      [STORAGE.privacy]: privacy,
      [STORAGE.webSearch]: webSearch,
    })
    flashNotice(notice)
  }

  async function refreshLocalData(): Promise<void> {
    const helper = await ensureLocalHelper()
    setHostState(helper.ok ? 'online' : 'offline')
    await hydrateDiskConfig()
    const [
      saved,
      skills,
      storedPlaybooks,
      storedSessions,
      storedThreads,
      storedScripts,
      storedProfiles,
      storedRecipes,
      diskMcp,
    ] = await Promise.all([
      chrome.storage.local.get([
        STORAGE.llmProfiles,
        STORAGE.llm,
        STORAGE.host,
        STORAGE.privacy,
        STORAGE.webSearch,
        STORAGE.mcpConnections,
        STORAGE.disabledSkills,
        STORAGE.disabledPlaybooks,
        STORAGE.voiceUi,
        STORAGE.speechLang,
        STORAGE.speechLangMode,
        STORAGE.speechTargets,
        STORAGE.speechLangFixed,
      ]),
      loadCustomSkills(),
      listPlaybooks(),
      listSessions(),
      listThreads(),
      listScripts(),
      listLearnedProfiles(),
      listLearnedRecipes(),
      loadDiskMcpFile(),
    ])
    const modelStore = await loadModelProfiles()
    setModelProfiles(modelStore)
    setEditingProfileId(modelStore.activeProfileId)
    setHost({ ...DEFAULT_HOST, ...(saved[STORAGE.host] as Partial<HostSettings> | undefined) })
    setVoiceUi(readVoiceUiMode(saved[STORAGE.voiceUi]))
    setSpeechLangConfig(
      readSpeechLangConfig({
        speechLang: saved[STORAGE.speechLang],
        speechLangMode: saved[STORAGE.speechLangMode],
        speechTargets: saved[STORAGE.speechTargets],
        speechLangFixed: saved[STORAGE.speechLangFixed],
      })
    )
    {
      const merged = {
        ...DEFAULT_PRIVACY,
        ...(saved[STORAGE.privacy] as Partial<PrivacySettings> | undefined),
      }
      const { privacy, changed } = normalizePrivacySettings(merged)
      setPrivacy(privacy)
      if (changed) void chrome.storage.local.set({ [STORAGE.privacy]: privacy })
    }
    setWebSearch(readWebSearchSettings(saved[STORAGE.webSearch]))
    const seeded = seedMcpConnections(saved[STORAGE.mcpConnections])
    const diskText = diskMcp?.text.trim() ?? ''
    if (diskMcp && (diskText || diskMcp.connections.length)) {
      const text = diskText || serializeMcpServersJson(diskMcp.connections.map(asNormalized))
      const parsed = parseMcpServersJson(text)
      setMcpJson(text)
      setMcpIssues(parsed.issues.length ? parsed.issues : diskMcp.issues)
      const next = mcpHasErrors(parsed.issues) ? seeded : mergeMcpRuntime(parsed.servers, seeded)
      setConnections(next)
      if (!mcpHasErrors(parsed.issues)) {
        void chrome.storage.local.set({ [STORAGE.mcpConnections]: next })
      }
    } else {
      setConnections(seeded)
      const text = serializeMcpServersJson(seeded.map(asNormalized))
      setMcpJson(text)
      setMcpIssues(parseMcpServersJson(text).issues)
      if (!Array.isArray(saved[STORAGE.mcpConnections]) || !saved[STORAGE.mcpConnections].length) {
        void chrome.storage.local.set({ [STORAGE.mcpConnections]: seeded })
      }
    }
    setDisabledSkills(
      Array.isArray(saved[STORAGE.disabledSkills])
        ? (saved[STORAGE.disabledSkills] as string[])
        : []
    )
    setDisabledPlaybooks(
      Array.isArray(saved[STORAGE.disabledPlaybooks])
        ? (saved[STORAGE.disabledPlaybooks] as string[])
        : []
    )
    setCustomSkills(skills)
    setPlaybooks(storedPlaybooks)
    setScripts(storedScripts)
    setSessions(storedSessions)
    setThreads(storedThreads)
    setSiteProfiles(storedProfiles)
    setRecipeCount(storedRecipes.length)
    setManagedLoginEnabledState(await isManagedLoginEnabled())
  }

  async function refreshAutomation(): Promise<void> {
    await refreshLocalData()
    setSniffReload((n) => n + 1)
    flashNotice(t('options.notice.refreshed'))
  }

  async function removeSiteProfile(id: string): Promise<void> {
    if (!confirm(t('options.confirm.deleteSiteProfile'))) return
    await deleteProfile(id)
    setSiteProfiles(await listLearnedProfiles())
    flashNotice(t('options.notice.siteProfileDeleted'))
  }

  useEffect(() => {
    void refreshLocalData()
    const syncHash = (): void => setSection(sectionFromHash())
    window.addEventListener('hashchange', syncHash)
    void chrome.storage.local.get(STORAGE.openSection).then((saved) => {
      const next = saved[STORAGE.openSection] as Section | undefined
      if (next === 'behaviorForge') {
        void chrome.storage.local.set({ [STORAGE.openWorkspaceTab]: 'replay' })
        setSection('workspace')
        window.location.hash = 'workspace'
        void chrome.storage.local.remove(STORAGE.openSection)
        return
      }
      if (next && NAV_ITEMS.some((item) => item.id === next)) {
        setSection(next)
        window.location.hash = next
        void chrome.storage.local.remove(STORAGE.openSection)
      }
      void chrome.storage.local.get(STORAGE.openSettingsTab).then((tabSaved) => {
        const tab = normalizeSettingsTab(tabSaved[STORAGE.openSettingsTab] as string | undefined)
        if (tab) {
          setSettingsTab(tab)
          void chrome.storage.local.remove(STORAGE.openSettingsTab)
        }
      })
    })
    const onStorageChange = (
      changes: Record<string, chrome.storage.StorageChange>,
      area: string
    ): void => {
      if (area !== 'local' || !changes[STORAGE.openSection]?.newValue) return
      const next = changes[STORAGE.openSection].newValue as Section
      if (next === 'behaviorForge') {
        void chrome.storage.local.set({ [STORAGE.openWorkspaceTab]: 'replay' })
        setSection('workspace')
        window.location.hash = 'workspace'
        void chrome.storage.local.remove(STORAGE.openSection)
        return
      }
      setSection(next)
      window.location.hash = next
      void chrome.storage.local.remove(STORAGE.openSection)
    }
    chrome.storage.onChanged.addListener(onStorageChange)
    return () => {
      window.removeEventListener('hashchange', syncHash)
      chrome.storage.onChanged.removeListener(onStorageChange)
    }
  }, [])

  async function save(values: Record<string, unknown>, message = t('options.saved')): Promise<void> {
    await chrome.storage.local.set(values)
    await syncDiskConfigFromPartial(values)
    flashNotice(message)
  }

  function navigate(next: Section, tab?: string): void {
    setSection(next)
    window.location.hash = next
    if (next === 'plugins' && (tab === 'skills' || tab === 'mcp' || tab === 'tools')) {
      setPluginTab(tab)
    }
    if (
      next === 'automation' &&
      (tab === 'playbooks' ||
        tab === 'scripts' ||
        tab === 'profiles' ||
        tab === 'recipes' ||
        tab === 'sessions' ||
        tab === 'sniff')
    ) {
      setAutomationTab(tab)
    }
    if (next === 'settings' && tab) {
      const normalized = normalizeSettingsTab(tab)
      if (normalized) setSettingsTab(normalized)
    }
  }

  const visibleNavItems = useMemo(
    () => NAV_ITEMS.filter((item) => item.id !== 'account' || managedLoginEnabled),
    [managedLoginEnabled]
  )

  useEffect(() => {
    if (section === 'account' && !managedLoginEnabled) {
      navigate('settings', 'agent')
    }
  }, [section, managedLoginEnabled])

  const allSkills = useMemo(() => mergeInstalledSkills(BUNDLED_SKILLS, customSkills), [customSkills])
  const userSkillIds = useMemo(
    () => new Set(customSkills.map((skill) => skill.manifest.id)),
    [customSkills]
  )
  const systemSkills = allSkills.filter((skill) => !userSkillIds.has(skill.manifest.id))
  const userSkills = allSkills.filter((skill) => userSkillIds.has(skill.manifest.id))
  async function toggleSkill(id: string): Promise<void> {
    const next = disabledSkills.includes(id)
      ? disabledSkills.filter((value) => value !== id)
      : [...disabledSkills, id]
    setDisabledSkills(next)
    await persistSkillDisabled(id, next.includes(id))
    flashNotice(t('options.notice.skillStatusUpdated'))
  }

  async function importSkill(): Promise<void> {
    try {
      const parsed = parseImportedSkill(skillDraft)
      const next = [...customSkills.filter((skill) => skill.manifest.id !== parsed.manifest.id), parsed]
      setCustomSkills(next)
      setSkillDraft('')
      setShowSkillImport(false)
      await save(
        { [STORAGE.customSkills]: next },
        t('options.notice.skillAdded', { id: parsed.manifest.id })
      )
      await persistSkillToDisk(parsed).catch(() => flashNotice(t('options.notice.skillCacheOnly')))
    } catch (error) {
      flashNotice(t('options.notice.importFailed', { message: (error as Error).message }))
    }
  }

  async function previewGitHubSkill(): Promise<void> {
    try {
      const source = parseGitHubSkillUrl(githubSkillUrl)
      const response = await fetch(source.rawUrl)
      if (!response.ok) throw new Error(`GitHub returned HTTP ${response.status}`)
      setGithubSkillPreview(parseGitHubSkill(await response.text(), source))
    } catch (error) {
      setGithubSkillPreview(null)
      flashNotice(t('options.notice.githubSkillReadFailed', { message: (error as Error).message }))
    }
  }

  async function installGitHubSkill(): Promise<void> {
    if (!githubSkillPreview) return
    const installed = githubSkillPreview
    const next = [
      ...customSkills.filter((skill) => skill.manifest.id !== installed.manifest.id),
      installed,
    ]
    setCustomSkills(next)
    setGithubSkillUrl('')
    setGithubSkillPreview(null)
    setShowSkillImport(false)
    await save(
      { [STORAGE.customSkills]: next },
      t('options.notice.skillInstalled', { id: installed.manifest.id })
    )
    try {
      await persistSkillToDisk(installed)
      const files = await fetchGitHubSkillResources(installed.source, installed.manifest.id)
      if (files.length) await persistSkillFiles(files)
    } catch {
      flashNotice(t('options.notice.skillCacheOnly'))
    }
  }

  async function checkGitHubSkillUpdate(skill: InstalledGitHubSkill): Promise<void> {
    setGithubSkillUrl(skill.source.pageUrl)
    setShowSkillImport(true)
    try {
      const response = await fetch(skill.source.rawUrl)
      if (!response.ok) throw new Error(`GitHub returned HTTP ${response.status}`)
      setGithubSkillPreview(parseGitHubSkill(await response.text(), skill.source))
      flashNotice(t('options.notice.githubVersionRead'))
    } catch (error) {
      flashNotice(t('options.notice.checkUpdateFailed', { message: (error as Error).message }))
    }
  }

  async function readSkillFile(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0]
    if (file) setSkillDraft(await file.text())
  }

  function syncMcpJson(next: McpConnection[]): McpConnection[] {
    const text = serializeMcpServersJson(next.map(asNormalized))
    setMcpJson(text)
    setMcpIssues(parseMcpServersJson(text).issues)
    return next
  }

  function addConnection(): void {
    const id = `mcp-${crypto.randomUUID().slice(0, 8)}`
    setConnections((current) =>
      syncMcpJson([
        {
          id,
          name: id,
          transport: 'streamable-http',
          endpoint: 'http://127.0.0.1:3000/mcp',
          enabled: false,
          allowedTools: ['*'],
        },
        ...current,
      ])
    )
  }

  async function addQuickConnection(): Promise<void> {
    try {
      const endpoint = new URL(mcpQuickUrl)
      if (!['https:', 'http:'].includes(endpoint.protocol)) throw new Error('MCP URL must use HTTP(S)')
      const connection: McpConnection = {
        id: endpoint.hostname.replace(/[^A-Za-z0-9._-]/g, '-') || crypto.randomUUID(),
        name: endpoint.hostname,
        transport: 'streamable-http',
        endpoint: endpoint.href,
        enabled: false,
        allowedTools: ['*'],
      }
      setConnections((current) => syncMcpJson([connection, ...current]))
      setMcpQuickUrl('')
      await testConnection(connection)
    } catch (error) {
      flashNotice(t('options.notice.mcpUrlInvalid', { message: (error as Error).message }))
    }
  }

  function patchConnection(id: string, patch: Partial<McpConnection>): void {
    setConnections((current) =>
      syncMcpJson(
        current.map((connection) => {
          if (connection.id !== id) return connection
          const next = { ...connection, ...patch }
          if (typeof patch.id === 'string' && patch.id.trim()) next.name = patch.id
          return next
        })
      )
    )
  }

  function formatMcpJsonEditor(): void {
    const result = formatMcpJsonText(mcpJson)
    setMcpJson(result.text)
    setMcpIssues(result.issues)
    if (!mcpHasErrors(result.issues)) {
      setConnections((current) => mergeMcpRuntime(parseMcpServersJson(result.text).servers, current))
    }
    if (result.changed) flashNotice(t('options.notice.mcpJsonFormatted'))
  }

  async function saveMcp(): Promise<void> {
    const formatted = formatMcpJsonText(mcpJson)
    const text = formatted.changed ? formatted.text : mcpJson
    const issues = formatted.issues
    if (formatted.changed) {
      setMcpJson(text)
      setMcpIssues(issues)
    }
    if (mcpHasErrors(issues)) {
      flashNotice(t('options.notice.fixMcpJsonBeforeSave'))
      return
    }
    const parsed = parseMcpServersJson(text)
    const next = mergeMcpRuntime(parsed.servers, connections)
    setConnections(next)
    await save({ [STORAGE.mcpConnections]: next }, t('options.notice.mcpSaved'))
    try {
      await persistMcpJsonToDisk(text)
    } catch (error) {
      flashNotice(t('options.notice.mcpCacheDiskFailed', { message: (error as Error).message }))
    }
  }

  async function testHost(): Promise<boolean> {
    try {
      const url = new URL(host.url)
      if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) {
        throw new Error(t('options.host.httpOnlyError'))
      }
      const base = url.href.replace(/\/$/, '')
      const response = await fetch(`${base}/health`, {
        headers: host.token ? { Authorization: `Bearer ${host.token}` } : {},
      })
      if (!response.ok) throw new Error(`HTTP ${response.status}`)
      setHostState('online')
      flashNotice(t('options.notice.hostConnected'))
      return true
    } catch (error) {
      setHostState('offline')
      flashNotice(t('options.notice.hostNotConnected', { message: (error as Error).message }))
      return false
    }
  }

  async function testModel(): Promise<void> {
    if (!editingProfile) return
    setTestingModel(true)
    try {
      const reply = await testModelProfile(editingProfile)
      flashNotice(t('options.notice.modelReplied', { reply }))
    } catch (error) {
      flashNotice(t('options.notice.modelTestFailed', { message: (error as Error).message }))
    } finally {
      setTestingModel(false)
    }
  }

  async function testConnection(connection: McpConnection): Promise<void> {
    const activity = await addActivity({
      kind: 'mcp',
      status: 'running',
      title: t('options.plugins.mcp.testActivityTitle', { name: connection.name }),
    })
    let message = ''
    let base = ''
    try {
      if (!host.enabled || !host.token || !(await testHost())) {
        throw new Error(t('options.plugins.mcp.hostRequired'))
      }
      base = host.url.replace(/\/$/, '')
      const headers = {
        Authorization: `Bearer ${host.token}`,
        'Content-Type': 'application/json',
      }
      const sync = await fetch(`${base}/mcp/connections`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          connections: [{ ...connection, enabled: true, allowedTools: ['*'] }],
        }),
      })
      if (!sync.ok) throw new Error(t('options.plugins.mcp.syncFailed', { status: sync.status }))
      const response = await fetch(`${base}/mcp/discover`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          connection: { ...connection, enabled: true, allowedTools: ['*'] },
        }),
      })
      const body = (await response.json()) as {
        tools?: Array<{ name: string; description?: string; inputSchema?: unknown }>
        resources?: Array<{ uri: string; name?: string; description?: string; mimeType?: string }>
        prompts?: Array<{ name: string; description?: string; arguments?: unknown }>
        error?: string
      }
      if (!response.ok) throw new Error(body.error ?? `HTTP ${response.status}`)
      if (body.error) throw new Error(body.error)
      const detail = t('options.plugins.mcp.catalogDiscovered', {
        tools: body.tools?.length ?? 0,
        resources: body.resources?.length ?? 0,
        prompts: body.prompts?.length ?? 0,
      })
      const discoveredTools = (body.tools ?? []).map((tool) => ({
        name: tool.name,
        description: tool.description,
        inputSchema: tool.inputSchema,
      }))
      const discoveredResources = body.resources ?? []
      const discoveredPrompts = body.prompts ?? []
      setConnections((current) => {
        const found = current.some((item) => item.id === connection.id)
        const next = (found ? current : [connection, ...current]).map((item) =>
          item.id === connection.id
            ? {
                ...item,
                discoveredTools,
                discoveredResources,
                discoveredPrompts,
                checkedAt: Date.now(),
              }
            : item
        )
        void chrome.storage.local.set({ [STORAGE.mcpConnections]: next })
        return next
      })
      await updateActivity(activity.id, { status: 'success', detail })
      message = t('options.notice.mcpConnected', { name: connection.name, detail })
    } catch (error) {
      const detail = (error as Error).message
      await updateActivity(activity.id, { status: 'failed', detail })
      message = t('options.notice.mcpTestFailed', { detail })
    } finally {
      if (base) {
        await fetch(`${base}/mcp/connections`, {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${host.token}`,
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({ connections }),
        }).catch(() => {})
      }
      flashNotice(message)
    }
  }

  async function togglePlaybook(id: string): Promise<void> {
    const next = disabledPlaybooks.includes(id)
      ? disabledPlaybooks.filter((value) => value !== id)
      : [...disabledPlaybooks, id]
    setDisabledPlaybooks(next)
    await save({ [STORAGE.disabledPlaybooks]: next }, t('options.notice.playbookStatusUpdated'))
  }

  async function duplicatePlaybook(playbook: Playbook): Promise<void> {
    const copy: Playbook = {
      ...playbook,
      id: crypto.randomUUID(),
      title: nextCopyTitle(playbook.title, playbooks.map((item) => item.title)),
      playbookVersion: 1,
      createdAt: Date.now(),
    }
    await savePlaybook(copy)
    setPlaybooks(await listPlaybooks())
    flashNotice(t('options.notice.playbookDuplicated', { title: copy.title }))
  }

  async function copyPlaybookJson(playbook: Playbook): Promise<void> {
    try {
      await navigator.clipboard.writeText(JSON.stringify(playbook, null, 2))
      flashNotice(t('options.notice.playbookJsonCopied'))
    } catch (error) {
      flashNotice(t('options.notice.copyFailed', { message: (error as Error).message }))
    }
  }

  async function removePlaybook(id: string): Promise<void> {
    if (!confirm(t('options.confirm.deletePlaybook'))) return
    await deletePlaybook(id)
    setPlaybooks(await listPlaybooks())
    flashNotice(t('options.notice.playbookDeleted'))
  }

  function exportPlaybook(playbook: Playbook): void {
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(playbook, null, 2)], { type: 'application/json' })
    )
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = `${playbook.id}.json`
    anchor.click()
    URL.revokeObjectURL(url)
  }

  async function importPlaybook(event: ChangeEvent<HTMLInputElement>): Promise<void> {
    const file = event.target.files?.[0]
    if (!file) return
    try {
      const playbook = JSON.parse(await file.text()) as Playbook
      if (playbook.schemaVersion !== 1 || !playbook.id || !playbook.title || !playbook.steps) {
        throw new Error(t('options.automation.playbooks.invalidSchema'))
      }
      await savePlaybook(playbook)
      setPlaybooks(await listPlaybooks())
      flashNotice(t('options.notice.playbookImported', { title: playbook.title }))
    } catch (error) {
      flashNotice(t('options.notice.importFailed', { message: (error as Error).message }))
    }
  }

  const filteredPlaybooks = playbooks.filter((playbook) =>
    `${playbook.title} ${playbook.host ?? ''}`.toLowerCase().includes(query.toLowerCase())
  )

  function skillRow(skill: Skill, origin: 'system' | 'user') {
    const enabled = !disabledSkills.includes(skill.manifest.id)
    const githubSkill =
      origin === 'user' && 'source' in skill ? (skill as InstalledGitHubSkill) : undefined
    return (
      <article className="registry-item" key={skill.manifest.id}>
        <div className="registry-symbol">{skill.manifest.id.slice(0, 2).toUpperCase()}</div>
        <div className="registry-main">
          <div className="registry-title">
            <h3>{skill.manifest.id}</h3>
            <span className="pill">
              {origin === 'system'
                ? t('options.skill.pills.system')
                : githubSkill
                  ? t('options.skill.pills.github')
                  : t('options.skill.pills.local')}
            </span>
            <span className="version">{t('options.common.labels.version', { version: skill.manifest.version })}</span>
          </div>
          <p>{skill.manifest.description}</p>
          <div className="metadata">
            <span>{t('options.skill.triggers', { value: skill.manifest.triggers?.join(', ') || t('options.common.labels.manual') })}</span>
            <span>
              {t('options.skill.tools', {
                value: skill.manifest.permissions?.tools?.length ?? t('options.common.labels.allTools'),
              })}
            </span>
            {githubSkill && (
              <span>
                {t('options.skill.source', {
                  owner: githubSkill.source.owner,
                  repo: githubSkill.source.repository,
                })}
              </span>
            )}
          </div>
        </div>
        <div className="registry-actions">
          <label className="switch">
            <input type="checkbox" checked={enabled} onChange={() => void toggleSkill(skill.manifest.id)} />
            <span />
          </label>
          {githubSkill && (
            <button className="text-button" onClick={() => void checkGitHubSkillUpdate(githubSkill)}>
              {t('options.skill.checkUpdate')}
            </button>
          )}
          {origin === 'user' && (
            <button
              className="text-button danger"
              onClick={() => {
                const next = customSkills.filter((item) => item.manifest.id !== skill.manifest.id)
                setCustomSkills(next)
                void save({ [STORAGE.customSkills]: next }, t('options.notice.skillDeleted'))
                void workspaceRpc('removeSkill', { id: skill.manifest.id }).catch(() => {})
              }}
            >
              {t('options.skill.delete')}
            </button>
          )}
        </div>
      </article>
    )
  }

  return (
    <div className="control-center">
      <aside className="sidebar">
        <div className="brand">
          <BrandMark size={38} />
          <div>
            <strong>{t('options.brand.name')}</strong>
            <span>{t('options.brand.subtitle')}</span>
          </div>
        </div>
        <nav aria-label={t('options.navAria')}>
          {visibleNavItems.map((item, index) => (
            <button
              key={item.id}
              type="button"
              className={section === item.id ? 'nav-item active' : 'nav-item'}
              onClick={() => navigate(item.id)}
            >
              <span className="nav-index">{String(index + 1).padStart(2, '0')}</span>
              <span>
                <small>{item.eyebrow}</small>
                {t(`options.nav.${item.id}`)}
              </span>
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <p>{t('options.sidebarFoot')}</p>
          <button
            type="button"
            className="button secondary"
            style={{ marginTop: 10, width: '100%' }}
            onClick={() => void openWorkspaceTab()}
          >
            {t('options.openWorkspace')}
          </button>
        </div>
      </aside>

      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            {t('options.topbar.breadcrumbPrefix')} / {section.toUpperCase()}
          </div>
          <div className="top-status">
            {managedLoginEnabled ? (
              <button
                type="button"
                className="text-button top-login-link"
                onClick={() => navigate('account')}
              >
                <i className={`status-dot ${editingProfile?.apiKey ? 'on' : 'warn'}`} />
                {t('options.nav.account')}
              </button>
            ) : null}
            <span>
              <i className={`status-dot ${editingProfile?.apiKey ? 'on' : 'warn'}`} />
              {t('options.topbar.modelLabel')}{' '}
              {editingProfile?.apiKey ? t('options.topbar.modelOk') : t('options.topbar.modelMissing')}
            </span>
            <span>
              <i
                className={`status-dot ${
                  hostState === 'online' ? 'on' : hostState === 'offline' ? 'off' : ''
                }`}
              />
              {t('options.topbar.hostLabel')}{' '}
              {hostState === 'unchecked'
                ? t('options.topbar.hostUnchecked')
                : hostState === 'online'
                  ? t('options.topbar.hostOnline')
                  : t('options.topbar.hostOffline')}
            </span>
          </div>
        </header>

        <main className="page">
          <AdBanner surface="options" className="options-ad-banner" />
          {notice ? (
            <div className="notice" role="status">
              {notice}
            </div>
          ) : null}

          {section === 'account' && managedLoginEnabled && (
            <AccountLoginPage onGoToModels={() => navigate('settings', 'agent')} />
          )}

          {section === 'toolkit' && <ToolkitPanel />}

          {section === 'workspace' && <WorkspacePanel />}

          {section === 'geniusFall' && <GeniusFallPanel />}

          {section === 'plugins' && (
            <>
              <PageTitle
                eyebrow={t('options.plugins.eyebrow')}
                title={t('options.plugins.title')}
                description={t('options.plugins.description')}
                action={
                  pluginTab === 'tools' ? undefined : (
                    <button
                      className="button primary"
                      onClick={() =>
                        pluginTab === 'skills' ? setShowSkillImport(true) : addConnection()
                      }
                    >
                      + {pluginTab === 'skills' ? t('options.common.buttons.addSkill') : t('options.common.buttons.addMcp')}
                    </button>
                  )
                }
              />
              <Tabs
                value={pluginTab}
                onChange={setPluginTab}
                items={[
                  { id: 'skills', label: t('options.plugins.tabs.skills', { count: allSkills.length }) },
                  { id: 'tools', label: t('options.plugins.tabs.tools', { count: BUILTIN_TOOL_CATALOG.length }) },
                  { id: 'mcp', label: t('options.plugins.tabs.mcp', { count: connections.length }) },
                ]}
              />
              {pluginTab === 'skills' && (
                <>
                  {showSkillImport && (
                    <section className="composer">
                      <div className="section-heading">
                        <span>{t('options.plugins.skills.safeInstallEyebrow')}</span>
                        <h2>{t('options.plugins.skills.safeInstallTitle')}</h2>
                      </div>
                      <p>{t('options.plugins.skills.safeInstallLead')}</p>
                      <Field label={t('options.plugins.skills.githubUrlLabel')} hint={t('options.plugins.skills.githubUrlHint')}>
                        <input value={githubSkillUrl} onChange={(event) => setGithubSkillUrl(event.target.value)} placeholder={t('options.plugins.skills.githubUrlPlaceholder')} />
                      </Field>
                      <div className="button-row">
                        <button className="button secondary" onClick={() => void previewGitHubSkill()}>{t('options.common.buttons.readPreview')}</button>
                        {githubSkillPreview && (
                          <button className="button primary" onClick={() => void installGitHubSkill()}>
                            {t('options.common.buttons.confirmInstall', { id: githubSkillPreview.manifest.id })}
                          </button>
                        )}
                      </div>
                      {githubSkillPreview && (
                        <div className="inline-callout">
                          <div><StatusDot state="on" /><strong>{githubSkillPreview.manifest.description}</strong></div>
                          <span>{githubSkillPreview.source.owner}/{githubSkillPreview.source.repository}@{githubSkillPreview.source.ref} · {githubSkillPreview.instructions.length} {t('options.common.labels.chars')}</span>
                        </div>
                      )}
                      <p>{t('options.plugins.skills.orImportLocal')}</p>
                      <textarea value={skillDraft} onChange={(event) => setSkillDraft(event.target.value)} placeholder={t('options.plugins.skills.skillDraftPlaceholder')} />
                      <div className="button-row">
                        <label className="button secondary file-button">{t('options.common.buttons.chooseFile')}<input type="file" accept=".json,.md,text/markdown" onChange={(event) => void readSkillFile(event)} /></label>
                        <button className="button primary" onClick={() => void importSkill()}>{t('options.common.buttons.verifyAndAdd')}</button>
                        <button className="button ghost" onClick={() => setShowSkillImport(false)}>{t('options.common.buttons.cancel')}</button>
                      </div>
                    </section>
                  )}
                  <div className="registry-list">
                    <div className="section-heading">
                      <span>{t('options.plugins.skills.systemEyebrow')}</span>
                      <h2>{t('options.plugins.skills.systemTitle')}</h2>
                    </div>
                    <p className="tab-lead">{t('options.plugins.skills.systemLead')}</p>
                    {systemSkills.map((skill) => skillRow(skill, 'system'))}
                    <div className="section-heading">
                      <span>{t('options.plugins.skills.userEyebrow')}</span>
                      <h2>{t('options.plugins.skills.userTitle')}</h2>
                    </div>
                    <p className="tab-lead">{t('options.plugins.skills.userLead')}</p>
                    {userSkills.length === 0 ? (
                      <p className="tab-lead">{t('options.plugins.skills.userEmpty')}</p>
                    ) : (
                      userSkills.map((skill) => skillRow(skill, 'user'))
                    )}
                  </div>
                </>
              )}
              {pluginTab === 'tools' && (
                <>
                  <p className="tab-lead">{t('options.plugins.tools.lead')}</p>
                  {(['DOM', 'Tabs', 'Web', 'Network', 'System'] as const).map((group) => (
                    <section className="tool-group" key={group}>
                      <div className="section-heading">
                        <span>{group.toUpperCase()}</span>
                        <h2>{t(`options.common.toolGroups.${group}`)}</h2>
                      </div>
                      <div className="tools-grid">
                        {BUILTIN_TOOL_CATALOG.filter((tool) => tool.group === group).map((tool) => {
                          return (
                            <article className="tool-card" key={tool.id}>
                              <code className="tool-id">{tool.id}</code>
                              <p className="tool-desc">{tool.description}</p>
                            </article>
                          )
                        })}
                      </div>
                    </section>
                  ))}
                </>
              )}
              {pluginTab === 'mcp' && (
                <>
                  <p className="tab-lead">{t('options.plugins.mcp.lead')}</p>
                  <div className="inline-callout">
                    <div><StatusDot state={hostState === 'online' ? 'on' : 'warn'} /><strong>{t('options.plugins.mcp.hostCalloutTitle')}</strong></div>
                    <span>{hostState === 'online' ? t('options.plugins.mcp.hostOnline') : t('options.plugins.mcp.hostOffline')}</span>
                    <button className="text-button" onClick={() => void testHost()}>{t('options.common.buttons.checkConnection')}</button>
                  </div>
                  <section className="composer">
                    <div className="section-heading"><span>{t('options.plugins.mcp.cursorFormatEyebrow')}</span><h2>{t('options.plugins.mcp.cursorFormatTitle')}</h2></div>
                    <p>{t('options.plugins.mcp.cursorFormatLead')}</p>
                    <textarea
                      className="mcp-json"
                      value={mcpJson}
                      spellCheck={false}
                      onChange={(event) => {
                        const text = event.target.value
                        setMcpJson(text)
                        const parsed = parseMcpServersJson(text)
                        setMcpIssues(parsed.issues)
                        if (!mcpHasErrors(parsed.issues)) {
                          setConnections((current) => mergeMcpRuntime(parsed.servers, current))
                        }
                      }}
                    />
                    {mcpIssues.length > 0 && (
                      <ul className="mcp-issues">
                        {mcpIssues.map((issue, index) => (
                          <li key={`${issue.level}-${index}`} className={issue.level}>
                            <strong>
                              {issue.level === 'error' ? t('options.plugins.mcp.issueError') : t('options.plugins.mcp.issueHint')}
                              {issue.server ? ` · ${issue.server}` : ''}
                            </strong>
                            <span>{issue.message}</span>
                            <small>{issue.hint}</small>
                          </li>
                        ))}
                      </ul>
                    )}
                    <div className="button-row">
                      <button className="button secondary" onClick={formatMcpJsonEditor}>
                        {t('options.plugins.mcp.formatJson')}
                      </button>
                      <button className="button primary" disabled={mcpHasErrors(mcpIssues)} onClick={() => void saveMcp()}>
                        {t('options.common.buttons.saveToDisk')}
                      </button>
                    </div>
                  </section>
                  <section className="composer">
                    <div className="section-heading"><span>{t('options.plugins.mcp.quickConnectEyebrow')}</span><h2>{t('options.plugins.mcp.quickConnectTitle')}</h2></div>
                    <p>{t('options.plugins.mcp.quickConnectLead')}</p>
                    <div className="button-row">
                      <input value={mcpQuickUrl} onChange={(event) => setMcpQuickUrl(event.target.value)} placeholder={t('options.plugins.mcp.quickConnectPlaceholder')} />
                      <button className="button primary" onClick={() => void addQuickConnection()}>{t('options.common.buttons.addAndTest')}</button>
                    </div>
                  </section>
                  <div className="registry-list">
                    {!connections.length && (
                      <div className="empty">
                        <strong>{t('options.plugins.mcp.emptyTitle')}</strong>
                        <span>{t('options.plugins.mcp.emptyBody')}</span>
                      </div>
                    )}
                    {connections.map((connection) => (
                      <article className="mcp-card" key={connection.id}>
                        <div className="mcp-head">
                          <input className="name-input" value={connection.id} onChange={(event) => patchConnection(connection.id, { id: event.target.value })} />
                          <select value={connection.transport} onChange={(event) => patchConnection(connection.id, { transport: event.target.value as McpConnection['transport'] })}>
                            <option value="streamable-http">{t('options.common.transport.streamableHttp')}</option>
                            <option value="sse">{t('options.common.transport.sse')}</option>
                            <option value="stdio">{t('options.common.transport.stdioViaHost')}</option>
                          </select>
                          <label className="switch"><input type="checkbox" checked={connection.enabled} onChange={(event) => patchConnection(connection.id, { enabled: event.target.checked })} /><span /></label>
                        </div>
                        <div className="form-grid">
                          <Field label={connection.transport === 'stdio' ? t('options.plugins.mcp.executableLabel') : t('options.plugins.mcp.endpointLabel')}>
                            <input value={connection.transport === 'stdio' ? connection.command ?? '' : connection.endpoint ?? ''} onChange={(event) => patchConnection(connection.id, connection.transport === 'stdio' ? { command: event.target.value } : { endpoint: event.target.value })} />
                          </Field>
                          {connection.transport === 'stdio' && (
                            <Field label={t('options.plugins.mcp.argumentsLabel')} hint={t('options.plugins.mcp.argumentsHint')}>
                              <textarea value={(connection.args ?? []).join('\n')} onChange={(event) => patchConnection(connection.id, { args: event.target.value.split('\n').filter(Boolean) })} />
                            </Field>
                          )}
                          <Field label={t('options.plugins.mcp.toolAuthLabel')} hint={t('options.plugins.mcp.toolAuthHint')}>
                            {connection.discoveredTools?.length ? (
                              <div className="tool-picker">
                                {connection.discoveredTools.map((tool) => (
                                  <label key={tool.name}>
                                    <input
                                      type="checkbox"
                                      checked={connection.allowedTools.includes('*') || connection.allowedTools.includes(tool.name)}
                                      onChange={(event) => {
                                        const names = connection.discoveredTools?.map((item) => item.name) ?? []
                                        if (connection.allowedTools.includes('*')) {
                                          patchConnection(connection.id, {
                                            allowedTools: event.target.checked
                                              ? ['*']
                                              : names.filter((name) => name !== tool.name),
                                          })
                                          return
                                        }
                                        patchConnection(connection.id, {
                                          allowedTools: event.target.checked
                                            ? [...connection.allowedTools, tool.name]
                                            : connection.allowedTools.filter((name) => name !== tool.name),
                                        })
                                      }}
                                    />
                                    <span><strong>{tool.name}</strong>{tool.description ? ` · ${tool.description}` : ''}</span>
                                  </label>
                                ))}
                              </div>
                            ) : (
                              <input value={connection.allowedTools.join(', ')} onChange={(event) => patchConnection(connection.id, { allowedTools: event.target.value.split(',').map((value) => value.trim()).filter(Boolean) })} placeholder={t('options.plugins.mcp.toolAuthPlaceholder')} />
                            )}
                          </Field>
                        </div>
                        <McpDiscoveryPanel
                          connection={connection}
                          labels={{
                            title: t('options.plugins.mcp.discoveryTitle'),
                            tools: t('options.plugins.mcp.discoveryTools'),
                            resources: t('options.plugins.mcp.discoveryResources'),
                            prompts: t('options.plugins.mcp.discoveryPrompts'),
                            qualified: t('options.plugins.mcp.discoveryQualified'),
                            empty: t('options.plugins.mcp.discoveryEmpty'),
                            checkedAt: t('options.plugins.mcp.discoveryCheckedAt'),
                          }}
                        />
                        <div className="button-row">
                          <button className="button secondary" onClick={() => void testConnection(connection)}>{t('options.common.buttons.testAndDiscover')}</button>
                          <button className="button primary" onClick={() => void saveMcp()}>{t('options.common.buttons.save')}</button>
                          <button className="button ghost danger" onClick={() => setConnections((items) => syncMcpJson(items.filter((item) => item.id !== connection.id)))}>{t('options.common.buttons.delete')}</button>
                        </div>
                      </article>
                    ))}
                  </div>
                </>
              )}
            </>
          )}

          {section === 'automation' && (
            <>
              <PageTitle
                eyebrow={t('options.automation.eyebrow')}
                title={t('options.automation.title')}
                description={t('options.automation.description')}
                action={
                  <div className="button-row">
                    <button className="button secondary" onClick={() => void refreshAutomation()}>
                      {t('options.common.buttons.refresh')}
                    </button>
                    <label className="button primary file-button">
                      {t('options.common.buttons.importPlaybook')}
                      <input type="file" accept=".json" onChange={(event) => void importPlaybook(event)} />
                    </label>
                    {automationTab === 'playbooks' && (
                      <button
                        className="button secondary"
                        disabled={!playbooks.length}
                        onClick={() =>
                          void clearPlaybooks().then(() => {
                            setPlaybooks([])
                            setDisabledPlaybooks([])
                            flashNotice(t('options.notice.playbooksCleared'))
                          })
                        }
                      >
                        {t('options.common.buttons.clearAll')}
                      </button>
                    )}
                    {automationTab === 'scripts' && (
                      <button
                        className="button secondary"
                        disabled={!scripts.length}
                        onClick={() =>
                          void clearScripts().then(() => {
                            setScripts([])
                            flashNotice(t('options.notice.scriptsCleared'))
                          })
                        }
                      >
                        {t('options.common.buttons.clearAll')}
                      </button>
                    )}
                    {automationTab === 'sessions' && (
                      <button className="button secondary" onClick={() => void clearSessions().then(() => setSessions([]))}>
                        {t('options.common.buttons.clearSessions')}
                      </button>
                    )}
                  </div>
                }
              />
              <Tabs
                value={automationTab}
                onChange={setAutomationTab}
                items={[
                  { id: 'playbooks', label: t('options.automation.tabs.playbooks', { count: playbooks.length }) },
                  { id: 'scripts', label: t('options.automation.tabs.scripts', { count: scripts.length }) },
                  { id: 'profiles', label: t('options.automation.tabs.profiles', { count: siteProfiles.length }) },
                  { id: 'recipes', label: t('options.automation.tabs.recipes', { count: recipeCount }) },
                  { id: 'sniff', label: t('options.automation.tabs.sniff') },
                  { id: 'sessions', label: t('options.automation.tabs.sessions', { count: sessions.length }) },
                ]}
              />
              {automationTab === 'playbooks' ? (
                <>
                  <div className="filter-bar">
                    <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={t('options.automation.playbooks.filterPlaceholder')} />
                    <span>{filteredPlaybooks.length} {t('options.common.labels.workflows')}</span>
                  </div>
                  {!filteredPlaybooks.length ? (
                    <div className="empty">
                      <strong>{t('options.automation.playbooks.emptyTitle')}</strong>
                      <span>{t('options.automation.playbooks.emptyBody')}</span>
                    </div>
                  ) : (
                    <div className="data-list">
                      <div className="data-list-head data-list-playbook">
                        <span>{t('options.automation.playbooks.table.enabled')}</span>
                        <span>{t('options.automation.playbooks.table.name')}</span>
                        <span>{t('options.automation.playbooks.table.scale')}</span>
                        <span>{t('options.automation.playbooks.table.host')}</span>
                        <span>{t('options.automation.playbooks.table.actions')}</span>
                      </div>
                      {filteredPlaybooks.map((playbook) => {
                        const enabled = !disabledPlaybooks.includes(playbook.id)
                        return (
                          <article className="data-list-row data-list-playbook" key={playbook.id}>
                            <label className="switch" title={enabled ? t('options.common.buttons.enabled') : t('options.common.buttons.disabled')}>
                              <input type="checkbox" checked={enabled} onChange={() => void togglePlaybook(playbook.id)} />
                              <span />
                            </label>
                            <div className="data-list-main">
                              <strong>{playbook.title}</strong>
                              <small>{playbook.task || t('options.automation.playbooks.taskFallback')}</small>
                            </div>
                            <span className="data-list-meta">
                              {t('options.automation.playbooks.scaleMeta', {
                                steps: playbook.steps.length,
                                inputs: Object.keys(playbook.inputs ?? {}).length,
                              })}
                            </span>
                            <span className="data-list-meta">{playbook.host || t('options.common.labels.anyHost')}</span>
                            <div className="data-list-actions">
                              <button className="text-button" onClick={() => void copyPlaybookJson(playbook)}>{t('options.common.buttons.copy')}</button>
                              <button className="text-button" onClick={() => void duplicatePlaybook(playbook)}>{t('options.common.buttons.duplicate')}</button>
                              <button className="text-button" onClick={() => exportPlaybook(playbook)}>{t('options.common.buttons.export')}</button>
                              <button className="text-button danger" onClick={() => void removePlaybook(playbook.id)}>{t('options.common.buttons.delete')}</button>
                            </div>
                          </article>
                        )
                      })}
                    </div>
                  )}
                </>
              ) : automationTab === 'scripts' ? (
                !scripts.length ? (
                  <div className="empty">
                    <strong>{t('options.automation.scripts.emptyTitle')}</strong>
                    <span>{t('options.automation.scripts.emptyBody')}</span>
                  </div>
                ) : (
                  <div className="data-list">
                    <div className="data-list-head data-list-script">
                      <span>{t('options.automation.scripts.table.language')}</span>
                      <span>{t('options.automation.scripts.table.name')}</span>
                      <span>{t('options.automation.scripts.table.file')}</span>
                      <span>{t('options.automation.scripts.table.actions')}</span>
                    </div>
                    {scripts.map((script) => (
                      <article className="data-list-row data-list-script" key={script.id}>
                        <span className="data-list-badge">{script.language.toUpperCase()}</span>
                        <div className="data-list-main">
                          <strong>{script.title}</strong>
                          <small>{script.sourceUrl || t('options.automation.scripts.noSourceUrl')}</small>
                        </div>
                        <span className="data-list-meta">{script.filename}</span>
                        <div className="data-list-actions">
                          <button className="text-button" onClick={() => void navigator.clipboard.writeText(script.content).then(() => flashNotice(t('options.notice.scriptCopied')))}>{t('options.common.buttons.copy')}</button>
                          <button className="text-button" onClick={() => void createChromeScriptPlane().download(script.id)}>{t('options.common.buttons.download')}</button>
                        </div>
                      </article>
                    ))}
                  </div>
                )
              ) : automationTab === 'profiles' ? (
                !siteProfiles.length ? (
                  <div className="empty">
                    <strong>{t('options.automation.profiles.emptyTitle')}</strong>
                    <span>{t('options.automation.profiles.emptyBody')}</span>
                  </div>
                ) : (
                  <div className="data-list">
                    <div className="data-list-head data-list-profile">
                      <span>{t('options.automation.profiles.table.source')}</span>
                      <span>{t('options.automation.profiles.table.profile')}</span>
                      <span>{t('options.automation.profiles.table.site')}</span>
                      <span>{t('options.automation.profiles.table.actions')}</span>
                    </div>
                    {siteProfiles.map((profile) => (
                      <article className="data-list-row data-list-profile" key={profile.id}>
                        <span className="data-list-badge">
                          {profile.source === 'user'
                            ? t('options.automation.profiles.sourceUser')
                            : t('options.automation.profiles.sourceLearned')}
                        </span>
                        <div className="data-list-main">
                          <strong>{profile.id}</strong>
                          <small>
                            {t('options.automation.profiles.detailMeta', {
                              detail: profile.detailUrl ?? t('options.common.labels.dash'),
                              container: profile.record ?? t('options.common.labels.dash'),
                            })}
                          </small>
                        </div>
                        <span className="data-list-meta">{profile.host.join(', ')}</span>
                        <div className="data-list-actions">
                          <button className="text-button danger" onClick={() => void removeSiteProfile(profile.id)}>
                            {t('options.common.buttons.delete')}
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                )
              ) : automationTab === 'recipes' ? (
                <SiteRecipesPanel
                  onNotice={flashNotice}
                  onRecipesChange={(count) => setRecipeCount(count)}
                />
              ) : automationTab === 'sniff' ? (
                <SniffPanel onNotice={flashNotice} reloadNonce={sniffReload} />
              ) : (
                <SessionList
                  sessions={sessions}
                  threads={threads}
                  onResume={(session, task) => {
                    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
                      const tab = tabs[0]
                      if (tab?.id != null) {
                        openSidePanelWithGesture(tab.id, tab.windowId)
                      }
                      void chrome.storage.local
                        .set({
                          [STORAGE.resumeSession]: {
                            threadId: session.threadId,
                            sessionId: session.id,
                            task: task ?? session.task,
                            page: session.page,
                          },
                        })
                        .then(() => {
                          flashNotice(
                            task ? t('options.notice.resumeWithTask') : t('options.notice.resumeSession')
                          )
                        })
                    })
                  }}
                />
              )}
            </>
          )}

          {section === 'settings' && (
            <>
              <PageTitle eyebrow="CONTROL PLANE" title={t('options.settingsTitle')} description={t('options.settingsDesc')} />
              <Tabs
                value={settingsTab}
                onChange={setSettingsTab}
                items={[
                  { id: 'agent', label: t('options.tab.agent') },
                  { id: 'privacy', label: t('options.tab.privacy') },
                  { id: 'system', label: t('options.tab.system') },
                ]}
              />
              <Field label={t('options.language')} hint={t('options.languageHint')}>
                <select
                  value={preference}
                  onChange={(event) => setPreference(event.target.value as LocalePreference)}
                >
                  <option value="auto">{t('options.languageAuto')}</option>
                  {LOCALES.map((id) => (
                    <option key={id} value={id}>
                      {LOCALE_LABELS[id]}
                    </option>
                  ))}
                </select>
              </Field>
              <Field label={t('options.voiceUi')} hint={t('options.voiceUiHint')}>
                <select
                  value={voiceUi}
                  onChange={(event) => {
                    const next = readVoiceUiMode(event.target.value)
                    setVoiceUi(next)
                    void chrome.storage.local.set({ [STORAGE.voiceUi]: next })
                    flashNotice(t('options.saved'))
                  }}
                >
                  <option value="bar">{t('options.voiceUiBar')}</option>
                  <option value="orb">{t('options.voiceUiOrb')}</option>
                </select>
              </Field>
              <Field label={t('options.speechLang')} hint={t('options.speechLangHint')}>
                <select
                  value={speechLangConfig.mode}
                  onChange={(event) => {
                    const mode = event.target.value === 'fixed' ? 'fixed' : 'auto'
                    const next: SpeechLangConfig = { ...speechLangConfig, mode }
                    setSpeechLangConfig(next)
                    void persistSpeechLangConfig(next).then(() => flashNotice(t('options.saved')))
                  }}
                >
                  <option value="auto">{t('options.speechLangModeAuto')}</option>
                  <option value="fixed">{t('options.speechLangModeFixed')}</option>
                </select>
              </Field>
              {speechLangConfig.mode === 'auto' ? (
                <Field label={t('options.speechTargets')} hint={t('options.speechTargetsHint')}>
                  <div className="checkbox-grid">
                    {SPEECH_RECOGNITION_LANGS.map((lang) => (
                      <label key={lang.id} className="checkbox-row">
                        <input
                          type="checkbox"
                          checked={speechLangConfig.targets.includes(lang.id)}
                          onChange={(event) => {
                            const checked = event.target.checked
                            const targets = checked
                              ? [...speechLangConfig.targets, lang.id]
                              : speechLangConfig.targets.filter((item) => item !== lang.id)
                            const next: SpeechLangConfig = {
                              ...speechLangConfig,
                              targets: targets.length ? targets : [lang.id],
                            }
                            setSpeechLangConfig(next)
                            void persistSpeechLangConfig(next).then(() => flashNotice(t('options.saved')))
                          }}
                        />
                        <span>{t(lang.labelKey)}</span>
                      </label>
                    ))}
                  </div>
                </Field>
              ) : (
                <Field label={t('options.speechLangFixed')}>
                  <select
                    value={speechLangConfig.fixed}
                    onChange={(event) => {
                      const fixed = event.target.value as SpeechRecognitionLang
                      const next: SpeechLangConfig = {
                        ...speechLangConfig,
                        fixed,
                        targets: [fixed],
                      }
                      setSpeechLangConfig(next)
                      void persistSpeechLangConfig(next).then(() => flashNotice(t('options.saved')))
                    }}
                  >
                    {SPEECH_RECOGNITION_LANGS.map((lang) => (
                      <option key={lang.id} value={lang.id}>
                        {t(lang.labelKey)}
                      </option>
                    ))}
                  </select>
                </Field>
              )}
              {settingsTab === 'agent' && (
                <>
                  <section className="settings-layout">
                    <div className="settings-copy">
                      <span>{t('options.agent.capabilitiesEyebrow')}</span>
                      <h2>{t('options.agent.capabilitiesTitle')}</h2>
                      <p>{t('options.agent.capabilitiesDesc')}</p>
                    </div>
                    <div className="settings-form">
                      <AgentCapabilitiesEditor
                        privacy={privacy}
                        persist
                        onPrivacyChange={setPrivacy}
                      />
                      <p className="settings-hint text-xs">{t('options.agent.capabilitiesAutoSave')}</p>
                    </div>
                  </section>
                  {editingProfile && modelProfiles ? (
                  <>
                  <section className="settings-layout">
                  <div className="settings-copy">
                    <span>{t('options.models.sectionEyebrow')}</span>
                    <h2>{t('options.models.sectionTitle')}</h2>
                    <p>{t('options.models.sectionDesc')}</p>
                  </div>
                  <div className="settings-form">
                    <Field label={t('options.models.savedProfilesLabel')}>
                      <select
                        value={editingProfileId}
                        onChange={(event) => setEditingProfileId(event.target.value)}
                      >
                        {modelProfiles.profiles.map((profile) => (
                          <option key={profile.id} value={profile.id}>
                            {profile.name} · {profile.model}
                            {profile.id === modelProfiles.activeProfileId ? t('options.common.labels.defaultSuffix') : ''}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label={t('options.models.displayNameLabel')}>
                      <input
                        value={editingProfile.name}
                        onChange={(event) => patchEditingProfile({ name: event.target.value })}
                      />
                    </Field>
                    <Field label={t('options.models.baseUrlLabel')}>
                      <input
                        value={editingProfile.baseURL}
                        onChange={(event) => patchEditingProfile({ baseURL: event.target.value })}
                      />
                    </Field>
                    <Field label={t('options.models.modelIdLabel')}>
                      <input
                        value={editingProfile.model}
                        onChange={(event) => patchEditingProfile({ model: event.target.value })}
                      />
                    </Field>
                    <Field label={t('options.models.thinkingLabel')} hint={t('options.models.thinkingHint')}>
                      <select
                        value={normalizeThinkingMode(editingProfile.thinking)}
                        onChange={(event) =>
                          patchEditingProfile({
                            thinking: normalizeThinkingMode(event.target.value),
                          })
                        }
                      >
                        {THINKING_MODES.map((mode) => (
                          <option key={mode} value={mode}>
                            {THINKING_LABELS[mode]}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <Field label={t('options.models.apiKeyLabel')}>
                      <input
                        type="password"
                        autoComplete="off"
                        value={editingProfile.apiKey}
                        onChange={(event) => patchEditingProfile({ apiKey: event.target.value })}
                      />
                    </Field>
                    <Field label={t('options.models.webSearchLabel')} hint={t('options.models.webSearchHint')}>
                      <div className="button-row">
                        <label>
                          <input
                            type="radio"
                            name="web-search-provider"
                            checked={webSearch.provider === 'brave'}
                            onChange={() => setWebSearch({ ...webSearch, provider: 'brave' })}
                          />{' '}
                          Brave
                        </label>
                        <label>
                          <input
                            type="radio"
                            name="web-search-provider"
                            checked={webSearch.provider === 'tavily'}
                            onChange={() => setWebSearch({ ...webSearch, provider: 'tavily' })}
                          />{' '}
                          Tavily
                        </label>
                      </div>
                    </Field>
                    <Field label={t('options.models.braveKeyLabel')} hint={t('options.models.braveKeyHint')}>
                      <input
                        type="password"
                        autoComplete="off"
                        value={webSearch.braveApiKey}
                        onChange={(event) =>
                          setWebSearch({ ...webSearch, braveApiKey: event.target.value })
                        }
                      />
                    </Field>
                    <Field label={t('options.models.tavilyKeyLabel')} hint={t('options.models.tavilyKeyHint')}>
                      <input
                        type="password"
                        autoComplete="off"
                        value={webSearch.tavilyApiKey}
                        onChange={(event) =>
                          setWebSearch({ ...webSearch, tavilyApiKey: event.target.value })
                        }
                      />
                    </Field>
                    <Field label={t('options.models.ocrLabel')} hint={t('options.models.ocrHint')}>
                      <select
                        value={modelProfiles.ocrProfileId ?? ''}
                        onChange={(event) => {
                          const next = setOcrModelProfile(
                            modelProfiles,
                            event.target.value || undefined
                          )
                          void persistModelProfiles(
                            next,
                            event.target.value ? t('options.notice.ocrSet') : t('options.notice.ocrCleared')
                          )
                        }}
                      >
                        <option value="">{t('options.models.ocrUnset')}</option>
                        {modelProfiles.profiles.map((profile) => (
                          <option key={profile.id} value={profile.id}>
                            {profile.name} · {profile.model}
                          </option>
                        ))}
                      </select>
                    </Field>
                    <div className="button-row">
                      <button
                        className="button primary"
                        onClick={() => void persistModelsTab(t('options.notice.modelsAndAgentSaved'))}
                      >
                        {t('options.common.buttons.saveAll')}
                      </button>
                      <button
                        className="button secondary"
                        disabled={testingModel}
                        onClick={() => void testModel()}
                      >
                        {testingModel ? t('options.common.buttons.testing') : t('options.common.buttons.testConnection')}
                      </button>
                      <button
                        className="button secondary"
                        onClick={() => {
                          const next = setActiveModelProfile(modelProfiles, editingProfile.id)
                          void persistModelProfiles(
                            next,
                            t('options.notice.defaultModelSet', { name: editingProfile.name })
                          )
                        }}
                      >
                        {t('options.common.buttons.setDefault')}
                      </button>
                      <button
                        className="button secondary"
                        onClick={() => {
                          const next = setOcrModelProfile(modelProfiles, editingProfile.id)
                          void persistModelProfiles(
                            next,
                            t('options.notice.ocrModelSet', { name: editingProfile.name })
                          )
                        }}
                      >
                        {t('options.common.buttons.setOcr')}
                      </button>
                      <button
                        className="button secondary"
                        onClick={() => {
                          const next = addModelProfile(modelProfiles)
                          setEditingProfileId(next.activeProfileId)
                          void persistModelProfiles(next, t('options.notice.modelAdded'))
                        }}
                      >
                        + {t('options.common.buttons.add')}
                      </button>
                      <button
                        className="button ghost"
                        disabled={modelProfiles.profiles.length <= 1}
                        onClick={() => {
                          const next = removeModelProfile(modelProfiles, editingProfile.id)
                          setEditingProfileId(next.activeProfileId)
                          void persistModelProfiles(next, t('options.notice.modelDeleted'))
                        }}
                      >
                        {t('options.common.buttons.delete')}
                      </button>
                    </div>
                  </div>
                </section>
                <section className="settings-layout settings-layout-follow">
                  <div className="settings-copy">
                    <span>{t('options.models.agentEyebrow')}</span>
                    <h2>{t('options.models.agentTitle')}</h2>
                    <p>{t('options.models.agentDesc')}</p>
                  </div>
                  <div className="settings-form">
                    <Field label={t('options.models.hitlLabel')} hint={t('options.models.hitlHint')}>
                      <select
                        value={privacy.hitlPolicy ?? 'balanced'}
                        onChange={(event) =>
                          setPrivacy({
                            ...privacy,
                            hitlPolicy: event.target.value as PrivacySettings['hitlPolicy'],
                          })
                        }
                      >
                        <option value="balanced">{t('options.models.hitlBalanced')}</option>
                        <option value="strict">{t('options.models.hitlStrict')}</option>
                        <option value="permissive">{t('options.models.hitlPermissive')}</option>
                      </select>
                    </Field>
                    <Field label={t('options.models.maxStepsLabel')}>
                      <input
                        type="number"
                        min={1}
                        max={500}
                        value={privacy.maxAgentSteps ?? DEFAULT_MAX_AGENT_STEPS}
                        onChange={(event) =>
                          setPrivacy({
                            ...privacy,
                            maxAgentSteps: normalizeMaxAgentSteps(event.target.value),
                          })
                        }
                      />
                    </Field>
                    <Field label={t('options.models.sameFailureLabel')} hint={t('options.models.sameFailureHint')}>
                      <input
                        type="number"
                        min={0}
                        max={10}
                        value={privacy.sameFailureLimit ?? DEFAULT_SAME_FAILURE_LIMIT}
                        onChange={(event) =>
                          setPrivacy({
                            ...privacy,
                            sameFailureLimit: normalizeSameFailureLimit(event.target.value),
                          })
                        }
                      />
                    </Field>
                    <Field label={t('options.models.runTimeoutLabel')} hint={t('options.models.runTimeoutHint')}>
                      <input
                        type="number"
                        min={0}
                        max={60}
                        value={runTimeoutMinutes(privacy.runTimeoutMs ?? DEFAULT_RUN_TIMEOUT_MS)}
                        onChange={(event) => {
                          const minutes = Number(event.target.value)
                          setPrivacy({
                            ...privacy,
                            runTimeoutMs:
                              !Number.isFinite(minutes) || minutes <= 0
                                ? 0
                                : normalizeRunTimeoutMs(minutes * 60_000),
                          })
                        }}
                      />
                    </Field>
                    <Field label={t('options.models.maxInputTokensLabel')} hint={t('options.models.maxInputTokensHint')}>
                      <input
                        type="number"
                        min={0}
                        max={2_000_000}
                        step={1000}
                        value={privacy.maxInputTokens ?? DEFAULT_MAX_INPUT_TOKENS}
                        onChange={(event) => {
                          const raw = Number(event.target.value)
                          setPrivacy({
                            ...privacy,
                            maxInputTokens:
                              !Number.isFinite(raw) || raw <= 0 ? 0 : normalizeMaxInputTokens(raw),
                          })
                        }}
                      />
                    </Field>
                    <Field label={t('options.models.tokenBudgetLabel')} hint={t('options.models.tokenBudgetHint')}>
                      <input
                        type="number"
                        min={0}
                        max={2_000_000}
                        step={1000}
                        value={privacy.tokenBudget ?? DEFAULT_TOKEN_BUDGET}
                        onChange={(event) => {
                          const raw = Number(event.target.value)
                          setPrivacy({
                            ...privacy,
                            tokenBudget:
                              !Number.isFinite(raw) || raw <= 0 ? 0 : normalizeTokenBudget(raw),
                          })
                        }}
                      />
                    </Field>
                    <p className="hint">
                      {t('options.models.agentDefaultsHint', {
                        steps: DEFAULT_MAX_AGENT_STEPS,
                        failures: DEFAULT_SAME_FAILURE_LIMIT,
                        minutes: DEFAULT_RUN_TIMEOUT_MS / 60_000,
                        tokens: DEFAULT_TOKEN_BUDGET,
                      })}
                    </p>
                  </div>
                </section>
                </>
                  ) : null}
                </>
              )}
              {settingsTab === 'privacy' && (
                <section className="settings-layout">
                  <div className="settings-copy">
                    <span>{t('options.permissions.eyebrow')}</span>
                    <h2>{t('options.permissions.title')}</h2>
                    <p>{t('options.privacy.permissionsInTabHint')}</p>
                  </div>
                  <div className="settings-form permission-list">
                    {(
                      [
                        ['tabs', t('options.permissions.items.tabs')],
                        ['scripting', t('options.permissions.items.scripting')],
                        ['debugger', t('options.permissions.items.debugger')],
                        ['declarativeNetRequest', t('options.permissions.items.declarativeNetRequest')],
                        ['storage', t('options.permissions.items.storage')],
                        ['alarms', t('options.permissions.items.alarms')],
                      ] as const
                    ).map(([name, detail]) => (
                      <div key={name}>
                        <StatusDot state="on" />
                        <strong>{name}</strong>
                        <span>{detail}</span>
                      </div>
                    ))}
                  </div>
                </section>
              )}
              {settingsTab === 'privacy' && (
                <section className="settings-layout">
                  <div className="settings-copy">
                    <span>{t('options.privacy.eyebrow')}</span>
                    <h2>{t('options.privacy.title')}</h2>
                    <p>{t('options.privacy.description')}</p>
                  </div>
                  <div className="settings-form">
                    <Toggle checked={privacy.storeApiKey} onChange={(checked) => setPrivacy({ ...privacy, storeApiKey: checked })} label={t('options.privacy.storeApiKeyLabel')} description={t('options.privacy.storeApiKeyDesc')} />
                    <p className="settings-hint">{t('options.privacy.captchaHint')}</p>
                    <Toggle
                      checked={privacy.rollbackUrlDrift !== false}
                      onChange={(checked) => setPrivacy({ ...privacy, rollbackUrlDrift: checked })}
                      label={t('options.privacy.rollbackLabel')}
                      description={t('options.privacy.rollbackDesc')}
                    />
                    <ModifyHeadersPrivacyToggle />
                    <Toggle
                      checked={privacy.enforceSkillToolAllowlist === true}
                      onChange={(checked) =>
                        setPrivacy({ ...privacy, enforceSkillToolAllowlist: checked })
                      }
                      label={t('options.privacy.skillAllowlistLabel')}
                      description={t('options.privacy.skillAllowlistDesc')}
                    />
                    <Field label={t('options.privacy.retainHistoryLabel')}>
                      <input type="number" min={0} max={365} value={privacy.retainHistoryDays} onChange={(event) => setPrivacy({ ...privacy, retainHistoryDays: Number(event.target.value) })} />
                    </Field>
                    <p className="settings-hint">{t('options.privacy.policyHint')}</p>
                    {PRIVACY_POLICY_URL ? (
                      <p className="settings-hint">
                        <a href={PRIVACY_POLICY_URL} target="_blank" rel="noreferrer">
                          {t('options.privacy.policyLink')}
                        </a>
                      </p>
                    ) : null}
                    <button className="button primary" onClick={() => {
                      const clearedProfiles = privacy.storeApiKey || !modelProfiles
                        ? modelProfiles
                        : stripModelProfileApiKeys(modelProfiles)
                      if (clearedProfiles) setModelProfiles(clearedProfiles)
                      if (!privacy.storeApiKey) {
                        setWebSearch({ ...webSearch, braveApiKey: '', tavilyApiKey: '' })
                      }
                      void save({
                        [STORAGE.privacy]: privacy,
                        ...(privacy.storeApiKey
                          ? {}
                          : {
                              [STORAGE.webSearch]: {
                                ...webSearch,
                                braveApiKey: '',
                                tavilyApiKey: '',
                              },
                            }),
                        ...(privacy.storeApiKey || !clearedProfiles
                          ? {}
                          : {
                              [STORAGE.llmProfiles]: clearedProfiles,
                              [STORAGE.llm]: profileToLlmConfig(getActiveModelProfile(clearedProfiles!)),
                            }),
                      }, t('options.notice.privacySaved'))
                    }}>{t('options.common.buttons.savePrivacy')}</button>
                  </div>
                </section>
              )}
              {settingsTab === 'system' && (
                <>
                <section className="settings-layout">
                  <div className="settings-copy">
                    <span>{t('options.host.eyebrow')}</span>
                    <h2>{t('options.host.title')}</h2>
                    <p>{t('options.host.description')}</p>
                  </div>
                  <div className="settings-form">
                    <Toggle checked={host.enabled} onChange={(checked) => setHost({ ...host, enabled: checked })} label={t('options.host.enabledLabel')} />
                    <Field label={t('options.host.urlLabel')}><input value={host.url} onChange={(event) => setHost({ ...host, url: event.target.value })} /></Field>
                    <Field label={t('options.host.tokenLabel')} hint={t('options.host.tokenHint')}>
                      <input type="password" value={host.token} onChange={(event) => setHost({ ...host, token: event.target.value })} />
                    </Field>
                    <div className="button-row">
                      <button className="button primary" onClick={() => void save({ [STORAGE.host]: host }, t('options.notice.hostSaved'))}>
                        {t('options.common.buttons.saveHost')}
                      </button>
                      <button className="button secondary" onClick={() => void testHost()}>{t('options.common.buttons.testConnection')}</button>
                    </div>
                  </div>
                </section>
                <section className="settings-layout settings-layout-follow">
                  <div className="settings-copy">
                    <span>{t('options.advanced.eyebrow')}</span>
                    <h2>{t('options.advanced.title')}</h2>
                    <p>{t('options.advanced.description')}</p>
                  </div>
                  <div className="settings-form">
                    <Toggle
                      checked={managedLoginEnabled}
                      onChange={(checked) => {
                        void setManagedLoginEnabled(checked).then(() => {
                          setManagedLoginEnabledState(checked)
                          flashNotice(t('options.notice.saved'))
                        })
                      }}
                      label={t('options.advanced.managedLoginLabel')}
                      description={t('options.advanced.managedLoginDesc')}
                    />
                  </div>
                  <div className="settings-form danger-zone">
                    <strong>{t('options.advanced.dangerTitle')}</strong>
                    <p>{t('options.advanced.dangerBody')}</p>
                    <button className="button danger" onClick={() => {
                      if (confirm(t('options.confirm.deleteAllLocalData'))) void chrome.storage.local.clear().then(() => location.reload())
                    }}>{t('options.advanced.clearAllButton')}</button>
                  </div>
                </section>
                </>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  )
}

function SessionList({
  sessions,
  threads,
  onResume,
}: {
  sessions: AgentSession[]
  threads: AgentThread[]
  onResume: (session: AgentSession, task?: string) => void
}) {
  const { t } = useI18n()
  const [selectedRunId, setSelectedRunId] = useState('')
  const orderedSessions = [...sessions].sort((a, b) => b.updatedAt - a.updatedAt)
  const selected =
    orderedSessions.find((session) => session.id === selectedRunId) ?? null

  function exportAudit() {
    downloadSessionAudit(buildSessionAuditExport(threads, sessions))
  }

  if (!sessions.length && !threads.length) {
    return (
      <div className="empty">
        <strong>{t('options.automation.sessions.emptyTitle')}</strong>
        <span>{t('options.automation.sessions.emptyBody')}</span>
      </div>
    )
  }

  return (
    <div className="session-browser">
      <div className="session-index">
        <p className="session-hint">
          {t('options.automation.sessions.hint')}
          <button className="text-button" style={{ marginLeft: 8 }} onClick={exportAudit}>
            {t('options.common.buttons.exportJson')}
          </button>
        </p>
        <div className="session-run-list">
          {orderedSessions.map((session) => (
            <button
              key={session.id}
              className={selected?.id === session.id ? 'session-row active' : 'session-row'}
              onClick={() => setSelectedRunId(session.id)}
            >
              <StatusDot
                state={
                  session.status === 'success'
                    ? 'on'
                    : session.status === 'running' || session.status === 'waiting'
                      ? 'warn'
                      : 'off'
                }
              />
              <span>
                <strong>{session.task}</strong>
                <small>
                  {t('options.automation.sessions.messagesMeta', {
                    count: session.records.length,
                    time: new Date(session.updatedAt).toLocaleString(),
                  })}
                </small>
              </span>
            </button>
          ))}
        </div>
      </div>
      {selected ? (
        <SessionTranscript
          session={selected}
          onClose={() => setSelectedRunId('')}
          onResume={onResume}
        />
      ) : (
        <div className="session-transcript session-transcript-empty">
          <div className="empty">
            <strong>{t('options.automation.sessions.selectTitle')}</strong>
            <span>{t('options.automation.sessions.selectBody')}</span>
          </div>
        </div>
      )}
    </div>
  )
}

