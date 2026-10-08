import {
  capabilityGatesFromPrivacy,
  parseMcpServersJson,
  type AgentCapabilityGates,
  type McpConnection,
  type NormalizedMcpServer,
} from '@naviforge/shared'
import type { Skill } from '@naviforge/skill-runtime'

export type { McpConnection }

export const STORAGE = {
  llm: 'naviforgeLlm',
  llmProfiles: 'naviforgeLlmProfiles',
  disabledSkills: 'naviforgeDisabledSkills',
  customSkills: 'naviforgeCustomSkills',
  mcpConnections: 'naviforgeMcpConnections',
  playbooksPurged: 'naviforgePlaybooksPurged',
  host: 'naviforgeHost',
  privacy: 'naviforgePrivacy',
  activities: 'naviforgeActivities',
  disabledPlaybooks: 'naviforgeDisabledPlaybooks',
  sessions: 'naviforgeAgentSessions',
  threads: 'naviforgeAgentThreads',
  activeRun: 'naviforgeActiveRun',
  agentPresence: 'naviforgeAgentPresence',
  resumeSession: 'naviforgeResumeSession',
  tabWorkspaces: 'naviforgeTabWorkspaces',
  /** One-shot deep link: open side panel to this section (toolkit, agent, …). */
  openSection: 'naviforgeOpenSection',
  openSettingsTab: 'naviforgeOpenSettingsTab',
  /** One-shot: workspace panel disk tab (shots, audio, …). */
  openWorkspaceDir: 'naviforgeOpenWorkspaceDir',
  /** One-shot: workspace panel tab (replay, config, …). */
  openWorkspaceTab: 'naviforgeOpenWorkspaceTab',
  /** One-shot banner after a popup capture. */
  openWorkspaceNotice: 'naviforgeOpenWorkspaceNotice',
  /** One-shot: open Toolkit JSON drawer after options loads. */
  openJsonDrawer: 'naviforgeOpenJsonDrawer',
  /** One-shot: open Toolkit run-result drawer with list/ip payload. */
  openToolkitRunResult: 'naviforgeOpenToolkitRunResult',
  /** Persisted JSON drawer width (px). */
  jsonDrawerWidth: 'naviforgeJsonDrawerWidth',
  sniff: 'naviforgeSniff',
  toolkitTabId: 'naviforgeToolkitTabId',
  modifyHeaders: 'naviforgeModifyHeaders',
  /** Web search provider + keys for web.search. */
  webSearch: 'naviforgeWebSearch',
  /** First-run consent: OCR crop is sent to the vision model. */
  ocrUploadConfirmed: 'naviforgeOcrUploadConfirmed',
  /** Toolkit in-page translate target (zh-CN, en, ja, ko). */
  translateTargetLang: 'naviforgeTranslateTargetLang',
  /** UI language: `auto` or a LocaleId (`en` | `zh-CN` | `es`). */
  locale: 'naviforgeLocale',
  /** Voice capture overlay: `bar` (strip) or `orb` (floating mic). */
  voiceUi: 'naviforgeVoiceUi',
  /** Speech recognition language: `auto` or a Web Speech BCP-47 tag. */
  speechLang: 'naviforgeSpeechLang',
  /** `auto` | `fixed` — auto picks among {@link STORAGE.speechTargets}. */
  speechLangMode: 'naviforgeSpeechLangMode',
  /** Target languages for auto ASR (BCP-47 tags). */
  speechTargets: 'naviforgeSpeechTargets',
  /** Fixed ASR language when mode is `fixed`. */
  speechLangFixed: 'naviforgeSpeechLangFixed',
  /** Last successful dictation language (auto mode hint). */
  lastSpeechLang: 'naviforgeLastSpeechLang',
  /** NewAPI managed login session (see docs/NEWAPI_PLUGIN_API.md). */
  newapiAuth: 'naviforgeNewapiAuth',
  /** Pending OAuth callback URL while login tab is open. */
  newapiPendingAuth: 'naviforgeNewapiPendingAuth',
  /** Genius Fall: enabled quota provider ids. */
  geniusFall: 'naviforgeGeniusFall',
  /** Floating HUD position on page. */
  geniusFallHud: 'naviforgeGeniusFallHud',
  /** Global HUD follow: { visible, tabId }. */
  geniusFallHudGlobal: 'naviforgeGeniusFallHudGlobal',
  /** Behavior replay session index. */
  behaviorForgeIndex: 'naviforgeBehaviorForgeIndex',
  /** Per-session payload prefix — `${behaviorForgeSession}:${id}`. */
  behaviorForgeSession: 'naviforgeBehaviorForgeSession',
  /** Per-session rrweb DOM events — `${behaviorForgeRrweb}:${id}`. */
  behaviorForgeRrweb: 'naviforgeBehaviorForgeRrweb',
  /** Behavior replay prefs (captureDom, pointer throttle, …). */
  behaviorForgePrefs: 'naviforgeBehaviorForgePrefs',
  /** Global behavior recording HUD: { visible, tabId, x, y }. */
  behaviorRecordingHudGlobal: 'naviforgeBehaviorRecordingHudGlobal',
  /** Experimental NaviForge hosted login (NewAPI). Off for store default (BYOK). */
  managedLoginEnabled: 'naviforgeManagedLoginEnabled',
} as const

/** Written by automation「继续此会话」; consumed once by AgentWorkspace. */
export type ResumeSessionPayload = {
  threadId?: string
  sessionId?: string
  task?: string
  page?: { tabId: number; url?: string; title?: string }
}

/** A resume request must name a session or provide a new task. */
export function hasResumeRequest(value: ResumeSessionPayload | undefined): value is ResumeSessionPayload {
  return Boolean(value?.sessionId || value?.task?.trim())
}

export type LlmSettings = {
  baseURL: string
  model: string
  apiKey: string
  reasoningEffort?: 'low' | 'medium' | 'high' | 'xhigh'
}

export type WebSearchProvider = 'brave' | 'tavily'

export type WebSearchSettings = {
  provider: WebSearchProvider
  braveApiKey: string
  tavilyApiKey: string
}

export const DEFAULT_WEB_SEARCH: WebSearchSettings = {
  provider: 'brave',
  braveApiKey: '',
  tavilyApiKey: '',
}

/** Read stored web.search settings. Legacy `{ apiKey }` becomes Brave. */
export function readWebSearchSettings(value: unknown): WebSearchSettings {
  if (!value || typeof value !== 'object') return { ...DEFAULT_WEB_SEARCH }
  const rec = value as Record<string, unknown>
  const provider: WebSearchProvider = rec.provider === 'tavily' ? 'tavily' : 'brave'
  const legacy = typeof rec.apiKey === 'string' ? rec.apiKey : ''
  const braveStored = typeof rec.braveApiKey === 'string' ? rec.braveApiKey : ''
  const tavilyApiKey = typeof rec.tavilyApiKey === 'string' ? rec.tavilyApiKey : ''
  return {
    provider,
    braveApiKey: braveStored || legacy,
    tavilyApiKey,
  }
}

export type HostSettings = {
  enabled: boolean
  url: string
  token: string
  /** Absolute path of the on-disk workspace (`~/NaviForge`). */
  workspaceRoot?: string
}

export type PrivacySettings = AgentCapabilityGates & {
  storeApiKey: boolean
  retainHistoryDays: number
  /** ask_user gate: strict | balanced (default) | permissive. */
  hitlPolicy?: 'strict' | 'balanced' | 'permissive'
  /** After unexpected navigation on stay-on-page tasks, call history.back(). */
  rollbackUrlDrift?: boolean
  /** Max agent loop steps per Run (default 30). */
  maxAgentSteps?: number
  /**
   * Stop after the same tool+error.code fails this many times in a row (default 2; 0 = off).
   */
  sameFailureLimit?: number
  /** Wall-clock limit for one Run in ms (default 8 min; 0 = off). */
  runTimeoutMs?: number
  /** Stop when cumulative LLM tokens for the Run reach this (default 80_000; 0 = off). */
  tokenBudget?: number
  /**
   * Estimated single-prompt input cap (system + user). L1/L2 compaction triggers here.
   * Cursor/DSH-style UIs show this as “context”; default 32k (conservative for DOM-heavy prompts).
   */
  maxInputTokens?: number
  /** When true, matched skill tool allowlist hard-blocks other tools (default off). */
  enforceSkillToolAllowlist?: boolean
}

export const DEFAULT_MAX_AGENT_STEPS = 30
export const DEFAULT_SAME_FAILURE_LIMIT = 2
export const DEFAULT_RUN_TIMEOUT_MS = 8 * 60_000
export const DEFAULT_TOKEN_BUDGET = 200_000
export const DEFAULT_MAX_INPUT_TOKENS = 32_000

export function normalizeMaxAgentSteps(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return DEFAULT_MAX_AGENT_STEPS
  return Math.min(500, Math.max(1, Math.round(n)))
}

export function normalizeSameFailureLimit(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return DEFAULT_SAME_FAILURE_LIMIT
  return Math.min(10, Math.max(0, Math.round(n)))
}

export function normalizeRunTimeoutMs(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return DEFAULT_RUN_TIMEOUT_MS
  if (n <= 0) return 0
  return Math.min(60 * 60_000, Math.max(60_000, Math.round(n)))
}

/** UI helper: minutes ↔ ms (0 minutes = off). */
export function runTimeoutMinutes(ms: number | undefined): number {
  if (!ms) return 0
  return Math.round(ms / 60_000)
}

export function normalizeTokenBudget(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return DEFAULT_TOKEN_BUDGET
  if (n <= 0) return 0
  return Math.min(2_000_000, Math.max(10_000, Math.round(n)))
}

export function normalizeMaxInputTokens(value: unknown): number {
  const n = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(n)) return DEFAULT_MAX_INPUT_TOKENS
  if (n <= 0) return 0
  return Math.min(2_000_000, Math.max(4_000, Math.round(n)))
}

/** Normalize persisted privacy fields (token budget bounds). */
export function normalizePrivacySettings(privacy: PrivacySettings): {
  privacy: PrivacySettings
  changed: boolean
} {
  let changed = false
  const next = { ...privacy }
  const normalizedBudget = normalizeTokenBudget(next.tokenBudget ?? DEFAULT_TOKEN_BUDGET)
  if (normalizedBudget !== next.tokenBudget) {
    next.tokenBudget = normalizedBudget
    changed = true
  }
  const normalizedInput = normalizeMaxInputTokens(next.maxInputTokens ?? DEFAULT_MAX_INPUT_TOKENS)
  if (normalizedInput !== next.maxInputTokens) {
    next.maxInputTokens = normalizedInput
    changed = true
  }
  return { privacy: next, changed }
}

export type ActivityEntry = {
  id: string
  kind: 'agent' | 'playbook' | 'mcp'
  status: 'running' | 'success' | 'failed' | 'cancelled'
  title: string
  detail?: string
  events?: Array<{
    at: number
    level: 'info' | 'recovery' | 'error'
    message: string
  }>
  createdAt: number
}

/** Retention applies to anything timestamped — sessions carry richer fields than activities. */
export function trimActivities<T extends { createdAt: number }>(
  activities: T[],
  retentionDays: number,
  now = Date.now()
): T[] {
  const cutoff = now - Math.max(0, retentionDays) * 86_400_000
  return activities
    .filter((entry) => retentionDays > 0 && entry.createdAt >= cutoff)
    .sort((a, b) => b.createdAt - a.createdAt)
    .slice(0, 200)
}

export const DEFAULT_HOST: HostSettings = {
  enabled: false,
  url: 'http://127.0.0.1:17373',
  token: '',
}

/**
 * Default MCP: Fetch — pull URLs outside the current tab without opening a second browser.
 * Playwright MCP is intentionally not the default: NaviForge already owns the user's Chrome
 * via DomPlane; a second browser would duplicate and confuse the loop.
 *
 * Requires Host enabled (stdio). Seeded only when the user has no saved connections.
 */
export const DEFAULT_MCP_CONNECTIONS: McpConnection[] = [
  {
    id: 'default-fetch',
    name: 'Fetch',
    transport: 'stdio',
    command: 'npx',
    args: ['-y', '@modelcontextprotocol/server-fetch'],
    enabled: true,
    allowedTools: ['*'],
  },
]

export function seedMcpConnections(saved: unknown): McpConnection[] {
  if (Array.isArray(saved) && saved.length) return saved as McpConnection[]
  return DEFAULT_MCP_CONNECTIONS.map((connection) => ({ ...connection }))
}

export const DEFAULT_PRIVACY: PrivacySettings = {
  networkEnabled: false,
  storeApiKey: true,
  retainHistoryDays: 30,
  allowDomInject: false,
  allowNetworkIntercept: false,
  hitlPolicy: 'balanced',
  rollbackUrlDrift: true,
  captureNetworkBodies: false,
  allowMainProbe: false,
  visionEnabled: true,
  maxAgentSteps: DEFAULT_MAX_AGENT_STEPS,
  sameFailureLimit: DEFAULT_SAME_FAILURE_LIMIT,
  runTimeoutMs: DEFAULT_RUN_TIMEOUT_MS,
  tokenBudget: DEFAULT_TOKEN_BUDGET,
  maxInputTokens: DEFAULT_MAX_INPUT_TOKENS,
  enforceSkillToolAllowlist: false,
}

export async function loadCustomSkills(): Promise<Skill[]> {
  try {
    const { diskSkillToSkill, loadDiskSkills } = await import('./local-workspace')
    const disk = await loadDiskSkills()
    if (disk) {
      const skills = disk.map(diskSkillToSkill)
      const diskIds = new Set(disk.map((item) => item.id))
      const diskDisabled = disk.filter((item) => !item.enabled).map((item) => item.id)
      const saved = await chrome.storage.local.get([STORAGE.customSkills, STORAGE.disabledSkills])
      const previous = Array.isArray(saved[STORAGE.disabledSkills])
        ? (saved[STORAGE.disabledSkills] as string[])
        : []
      const disabled = [...previous.filter((id) => !diskIds.has(id)), ...diskDisabled]
      await chrome.storage.local.set({
        [STORAGE.customSkills]: skills,
        [STORAGE.disabledSkills]: disabled,
      })
      return skills
    }
  } catch {
    // helper offline — chrome.storage hot cache
  }
  const result = await chrome.storage.local.get(STORAGE.customSkills)
  const value = result[STORAGE.customSkills]
  return Array.isArray(value) ? (value as Skill[]) : []
}

/** Disk skills with the same id replace bundled copies. */
export function mergeInstalledSkills(bundled: Skill[], custom: Skill[]): Skill[] {
  const map = new Map(bundled.map((skill) => [skill.manifest.id, skill]))
  for (const skill of custom) map.set(skill.manifest.id, skill)
  return [...map.values()]
}

/** Shared Agent + Toolkit capability gates from persisted privacy settings. */
export async function loadStoredCapabilityGates(): Promise<AgentCapabilityGates> {
  const saved = await chrome.storage.local.get(STORAGE.privacy)
  const merged = {
    ...DEFAULT_PRIVACY,
    ...(saved[STORAGE.privacy] as Partial<PrivacySettings> | undefined),
  }
  return capabilityGatesFromPrivacy(normalizePrivacySettings(merged).privacy)
}

/** Single parse entry for MCP JSON (Options + Host both use `parseMcpServersJson`). */
export function parseStoredMcpServersJson(text: string) {
  return parseMcpServersJson(text)
}

export async function loadNormalizedMcpServers(): Promise<NormalizedMcpServer[]> {
  const saved = await chrome.storage.local.get(STORAGE.mcpConnections)
  const raw = saved[STORAGE.mcpConnections]
  const text = typeof raw === 'string' ? raw : ''
  return parseMcpServersJson(text).servers
}
