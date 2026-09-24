import type { McpIssue } from '@naviforge/shared'
import type {
  WorkspaceEntry,
  WorkspacePlane,
  WorkspaceSkill,
} from '@naviforge/runtime'
import type { Skill } from '@naviforge/skill-runtime'

import { DEFAULT_HOST, DEFAULT_MCP_CONNECTIONS, STORAGE, type HostSettings, type McpConnection } from './settings'

const NATIVE_HOST = 'com.naviforge.host'
const DEFAULT_URL = 'http://127.0.0.1:17373'

export type LocalHelperStatus = {
  ok: boolean
  url: string
  token: string
  workspaceRoot: string
  error?: string
}

function safeHostUrl(value: string): string {
  const url = new URL(value)
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) {
    throw new Error('Host must use local HTTP on 127.0.0.1 or localhost')
  }
  return url.href.replace(/\/$/, '')
}

export function skillToMarkdown(skill: Skill): string {
  const lines = [
    '---',
    `name: ${skill.manifest.id}`,
    `id: ${skill.manifest.id}`,
    `version: ${skill.manifest.version}`,
    `description: ${skill.manifest.description}`,
  ]
  if (skill.manifest.triggers?.length) lines.push(`triggers: ${skill.manifest.triggers.join(', ')}`)
  const source = 'source' in skill ? (skill as { source?: { pageUrl?: string } }).source : undefined
  if (source?.pageUrl) lines.push(`github-url: ${source.pageUrl}`)
  lines.push('---', '', skill.instructions.trim(), '')
  return lines.join('\n')
}

export function diskSkillToSkill(item: WorkspaceSkill): Skill {
  return {
    manifest: {
      id: item.id,
      version: item.version,
      description: item.description,
      triggers: item.triggers,
    },
    instructions: item.instructions,
    files: item.files,
  }
}

async function readHost(): Promise<HostSettings> {
  const saved = await chrome.storage.local.get(STORAGE.host)
  return { ...DEFAULT_HOST, ...(saved[STORAGE.host] as Partial<HostSettings> | undefined) }
}

async function persistHost(patch: Partial<HostSettings>): Promise<HostSettings> {
  const next = { ...(await readHost()), ...patch, enabled: true }
  await chrome.storage.local.set({ [STORAGE.host]: next })
  return next
}

async function bootstrap(url = DEFAULT_URL): Promise<LocalHelperStatus | null> {
  try {
    const response = await fetch(`${safeHostUrl(url)}/local/bootstrap`, {
      signal: AbortSignal.timeout(2500),
    })
    if (!response.ok) return null
    const body = (await response.json()) as {
      ok?: boolean
      url?: string
      token?: string
      workspaceRoot?: string
    }
    if (!body.ok || !body.token || !body.workspaceRoot) return null
    return {
      ok: true,
      url: body.url ?? safeHostUrl(url),
      token: body.token,
      workspaceRoot: body.workspaceRoot,
    }
  } catch {
    return null
  }
}

function nativeEnsure(): Promise<LocalHelperStatus | null> {
  return new Promise((resolve) => {
    if (!chrome.runtime.sendNativeMessage) {
      resolve(null)
      return
    }
    let done = false
    const finish = (value: LocalHelperStatus | null) => {
      if (done) return
      done = true
      resolve(value)
    }
    const timer = setTimeout(() => finish(null), 2000)
    chrome.runtime.sendNativeMessage(NATIVE_HOST, { op: 'ensure' }, (reply) => {
      clearTimeout(timer)
      if (chrome.runtime.lastError || !reply?.token) {
        finish(null)
        return
      }
      finish({
        ok: true,
        url: String(reply.url ?? DEFAULT_URL),
        token: String(reply.token),
        workspaceRoot: String(reply.workspaceRoot ?? ''),
      })
    })
  })
}

/** Discover or start the on-device helper. Never claims disk writes if this fails. */
export async function ensureLocalHelper(): Promise<LocalHelperStatus> {
  const saved = await readHost()
  const first = await bootstrap(saved.url || DEFAULT_URL)
  const found = first ?? (await nativeEnsure()) ?? (saved.url !== DEFAULT_URL ? await bootstrap(DEFAULT_URL) : null)
  if (!found) {
    return {
      ok: false,
      url: saved.url || DEFAULT_URL,
      token: saved.token,
      workspaceRoot: saved.workspaceRoot ?? '',
      error: '本机助手未运行。在仓库执行 npm run host:install（登录后自动拉起），或 npm run host。',
    }
  }
  await persistHost({
    url: found.url,
    token: found.token,
    workspaceRoot: found.workspaceRoot,
    enabled: true,
  })
  return found
}

export async function workspaceRpc<T>(op: string, extra: Record<string, unknown> = {}): Promise<T> {
  const helper = await ensureLocalHelper()
  if (!helper.ok) throw new Error(helper.error ?? 'local helper offline')
  const response = await fetch(`${safeHostUrl(helper.url)}/workspace`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${helper.token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ op, ...extra }),
    signal: AbortSignal.timeout(8000),
  })
  const body = (await response.json()) as T & { error?: string }
  if (!response.ok) throw new Error(hostOpError(body.error ?? `Host returned HTTP ${response.status}`))
  return body
}

function hostOpError(message: string): string {
  if (/unknown workspace op:\s*(readDataUrl|audio)/i.test(message)) {
    return '本机 Host 版本过旧，读不了截图/录音。请在仓库执行 npm run host:install 重启本地 Host。'
  }
  return message
}

function stripDataUrl(value: unknown): unknown {
  if (!value || typeof value !== 'object') return value
  if (Array.isArray(value)) return value.map(stripDataUrl)
  const rec = value as Record<string, unknown>
  const next: Record<string, unknown> = {}
  for (const [key, item] of Object.entries(rec)) {
    if (
      (key === 'dataUrl' || key === 'imageDataUrl' || key === 'audioDataUrl') &&
      typeof item === 'string' &&
      (item.startsWith('data:image/') || item.startsWith('data:audio/'))
    ) {
      next[key] = `[omitted ${item.length} chars]`
      continue
    }
    next[key] = stripDataUrl(item)
  }
  return next
}

export async function appendWorkspaceLedger(input: {
  threadId: string
  slug?: string
  title?: string
  line: unknown
}): Promise<string | undefined> {
  try {
    const result = await workspaceRpc<{ relativePath: string }>('append', {
      threadId: input.threadId,
      slug: input.slug,
      title: input.title,
      line: stripDataUrl(input.line),
    })
    return result.relativePath
  } catch {
    return undefined
  }
}

export async function saveWorkspaceShot(input: {
  kind: string
  dataUrl: string
  threadId?: string
  slug?: string
  title?: string
  runId?: string
  tool?: string
}): Promise<{ relativePath: string } | undefined> {
  try {
    return await workspaceRpc<{ relativePath: string }>('shot', input)
  } catch {
    return undefined
  }
}

export async function saveWorkspaceAudio(input: {
  kind?: string
  dataUrl: string
}): Promise<{ relativePath: string } | undefined> {
  try {
    return await workspaceRpc<{ relativePath: string }>('audio', input)
  } catch {
    return undefined
  }
}

export async function saveWorkspacePage(input: {
  kind: 'md' | 'pdf'
  content?: string
  dataUrl?: string
  slug?: string
}): Promise<{ relativePath: string } | undefined> {
  try {
    return await workspaceRpc<{ relativePath: string }>('page', input)
  } catch {
    return undefined
  }
}

export async function loadDiskSkills(): Promise<WorkspaceSkill[] | null> {
  try {
    const result = await workspaceRpc<{ skills: WorkspaceSkill[] }>('scanSkills')
    return result.skills
  } catch {
    return null
  }
}

export async function persistSkillToDisk(skill: Skill): Promise<void> {
  await workspaceRpc('writeSkill', { id: skill.manifest.id, markdown: skillToMarkdown(skill) })
}

export async function persistSkillFiles(files: Array<{ path: string; content: string }>): Promise<void> {
  for (const file of files) {
    await workspaceRpc('write', { path: file.path, content: file.content })
  }
}

/** Disk `.disabled` is source of truth; chrome.storage is the sidebar hot cache. */
export async function persistSkillDisabled(id: string, disabled: boolean): Promise<void> {
  const saved = await chrome.storage.local.get(STORAGE.disabledSkills)
  const prev = Array.isArray(saved[STORAGE.disabledSkills])
    ? (saved[STORAGE.disabledSkills] as string[])
    : []
  const next = disabled ? [...new Set([...prev, id])] : prev.filter((item) => item !== id)
  await chrome.storage.local.set({ [STORAGE.disabledSkills]: next })
  await workspaceRpc('setSkillDisabled', { id, disabled }).catch(() => {})
}

export async function persistMcpToDisk(connections: McpConnection[]): Promise<void> {
  await workspaceRpc('writeMcp', { connections })
}

export async function persistMcpJsonToDisk(text: string): Promise<void> {
  await workspaceRpc('writeMcpText', { text })
}

export type DiskMcpFile = {
  connections: McpConnection[]
  issues: McpIssue[]
  text: string
  format: string
}

export async function loadDiskMcpFile(): Promise<DiskMcpFile | null> {
  try {
    const result = await workspaceRpc<DiskMcpFile>('readMcp')
    return {
      connections: Array.isArray(result.connections) ? result.connections : [],
      issues: Array.isArray(result.issues) ? result.issues : [],
      text: typeof result.text === 'string' ? result.text : '',
      format: result.format ?? 'empty',
    }
  } catch {
    return null
  }
}

export async function loadDiskMcp(): Promise<McpConnection[] | null> {
  const file = await loadDiskMcpFile()
  return file ? file.connections : null
}

export async function migrateStorageToWorkspace(): Promise<void> {
  const helper = await ensureLocalHelper()
  if (!helper.ok) return
  const saved = await chrome.storage.local.get([
    STORAGE.customSkills,
    STORAGE.mcpConnections,
    STORAGE.playbooksPurged,
    STORAGE.disabledPlaybooks,
  ])
  if (!saved[STORAGE.playbooksPurged]) {
    await chrome.storage.local.remove(['naviforgePlaybooks', STORAGE.disabledPlaybooks])
    await chrome.storage.local.set({ [STORAGE.playbooksPurged]: true })
  }
  try {
    await workspaceRpc('registerNative', { extensionId: chrome.runtime.id })
  } catch {
    // helper too old or id rejected
  }
  const diskSkills = await loadDiskSkills()
  const storedSkills = Array.isArray(saved[STORAGE.customSkills])
    ? (saved[STORAGE.customSkills] as Skill[])
    : []
  if (diskSkills && !diskSkills.length && storedSkills.length) {
    for (const skill of storedSkills) {
      await persistSkillToDisk(skill).catch(() => {})
    }
  }
  const diskMcp = await loadDiskMcp()
  const storedMcp = Array.isArray(saved[STORAGE.mcpConnections])
    ? (saved[STORAGE.mcpConnections] as McpConnection[])
    : []
  if (diskMcp && !diskMcp.length) {
    const seed = storedMcp.length ? storedMcp : DEFAULT_MCP_CONNECTIONS
    await persistMcpToDisk(seed).catch(() => {})
    if (!storedMcp.length) {
      await chrome.storage.local.set({ [STORAGE.mcpConnections]: seed })
    }
  } else if (diskMcp?.length) {
    await chrome.storage.local.set({ [STORAGE.mcpConnections]: diskMcp })
  }
  const { hydrateDiskConfig } = await import('./disk-config')
  await hydrateDiskConfig()
}

export function createChromeWorkspacePlane(): WorkspacePlane {
  return {
    async available() {
      return (await ensureLocalHelper()).ok
    },
    async status() {
      const helper = await ensureLocalHelper()
      return { root: helper.workspaceRoot, ok: helper.ok }
    },
    async saveShot(input) {
      const saved = await saveWorkspaceShot(input)
      if (!saved) throw new Error('screenshot not written to workspace')
      return saved
    },
    async savePage(input) {
      return workspaceRpc<{ relativePath: string; bytes: number }>('page', input)
    },
    async listSkills() {
      return (await loadDiskSkills()) ?? []
    },
    async writeSkill(input) {
      await workspaceRpc('writeSkill', input)
    },
    async removeSkill(id) {
      await workspaceRpc('removeSkill', { id })
    },
    async setSkillDisabled(id, disabled) {
      await workspaceRpc('setSkillDisabled', { id, disabled })
    },
    async readMcp() {
      return { connections: (await loadDiskMcp()) ?? [] }
    },
    async writeMcp(connections) {
      await persistMcpToDisk(connections as McpConnection[])
    },
    async listDir(dir) {
      const result = await workspaceRpc<{ entries: WorkspaceEntry[] }>('list', { dir })
      return result.entries
    },
    async readFile(path) {
      const result = await workspaceRpc<{ content: string }>('read', { path })
      return result.content
    },
    async writeFile(path, content) {
      await workspaceRpc('write', { path, content })
    },
    async mkdir(path) {
      await workspaceRpc('mkdir', { path })
    },
    async touch(path) {
      await workspaceRpc('touch', { path })
    },
    async stat(path) {
      return workspaceRpc('stat', { path })
    },
    async glob(pattern, dir) {
      const result = await workspaceRpc<{ paths: string[] }>('glob', { pattern, path: dir ?? '' })
      return result.paths
    },
    async grep(pattern, opts) {
      const result = await workspaceRpc<{ hits: Array<{ path: string; line: number; text: string }> }>(
        'grep',
        { pattern, path: opts?.path, glob: opts?.glob, max: opts?.max }
      )
      return result.hits
    },
    async writeScript(input) {
      return workspaceRpc<{ relativePath: string }>('writeScript', input)
    },
    async open(path) {
      await workspaceRpc('open', path ? { path } : {})
    },
  }
}

/** Empty-state copy for workspace tabs. Offline must not look like “disk is empty”. */
export function workspaceEmptyHint(connected: boolean | null, ready: string): string {
  if (connected == null) return '正在连接本机助手…'
  if (!connected) return '本机助手未连接，无法列出磁盘上的文件。请点「连接本机助手」。'
  return ready
}

/** Local `YYYY-MM-DD HH:mm` for workspace file lists. Empty when mtime is missing. */
export function formatWorkspaceMtime(mtime?: number): string {
  if (!mtime) return ''
  const date = new Date(mtime)
  if (Number.isNaN(date.getTime())) return ''
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** List each workspace dir on its own; one failure must not wipe sibling tabs. */
export async function loadWorkspaceFileLists(
  dirs: string[],
  listFiles: (dir: string) => Promise<WorkspaceEntry[]>
): Promise<{ lists: Record<string, WorkspaceEntry[]>; errors: string[] }> {
  const lists: Record<string, WorkspaceEntry[]> = Object.fromEntries(dirs.map((dir) => [dir, []]))
  const errors: string[] = []
  await Promise.all(
    dirs.map(async (dir) => {
      try {
        lists[dir] = await listFiles(dir)
      } catch (error) {
        errors.push(`${dir}: ${(error as Error).message}`)
      }
    })
  )
  return { lists, errors }
}

export async function listWorkspaceFiles(dir: string): Promise<WorkspaceEntry[]> {
  try {
    const { entries } = await workspaceRpc<{ entries: WorkspaceEntry[] }>('list', {
      dir,
      recursive: true,
    })
    return (entries ?? []).filter((entry) => entry.kind !== 'dir')
  } catch (error) {
    const msg = (error as Error).message
    // Older Host throws if a later workspace dir was never mkdir'd.
    if (/ENOENT|no such file or directory/i.test(msg)) return []
    throw error
  }
}

export async function downloadFallback(
  dataUrl: string,
  filename: string,
  saveAs = false
): Promise<number> {
  return chrome.downloads.download({
    url: dataUrl,
    filename: `NaviForge/${filename}`,
    saveAs,
  })
}
