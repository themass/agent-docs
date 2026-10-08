import { spawn } from 'node:child_process'
import { randomBytes } from 'node:crypto'
import { homedir } from 'node:os'
import { chmod, mkdir, readFile, readdir, rm, stat, writeFile, appendFile } from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { createTraceRecord, stringifyJsonlLine, validateTraceRecord, type TraceRecord } from '@naviforge/session'

import {
  globWorkspace,
  grepWorkspace,
  mkdirWorkspace,
  statWorkspace,
  touchWorkspace,
} from './fs-ops.js'
import { seedDefaultScripts } from './script-templates.js'
import {
  mcpHasErrors,
  parseMcpServersJson,
  serializeMcpServersJson,
  type McpIssue,
  type NormalizedMcpServer,
} from '@naviforge/shared'

export const WORKSPACE_DIRS = [
  'config',
  'skills',
  'mcp',
  'sessions',
  'shots',
  'audio',
  'pages',
  'scripts',
  'playbooks',
  'logs',
] as const

const WORKSPACE_README = `# NaviForge workspace

Disk is the source of truth. Edit JSON under config/, then reload the extension.

## Layout

- \`config/models.json\` — LLM profiles (API keys). chmod 0600.
- \`config/search.json\` — web_search provider + keys. chmod 0600.
- \`config/settings.json\` — privacy + modify-headers.
- \`mcp/servers.json\` — MCP servers (Cursor \`mcpServers\` format).
- \`skills/<id>/SKILL.md\` — user skills only. Optional \`scripts/\`, \`references/\`, \`assets/\`.
- \`sessions/*.jsonl\` — one JSON object per line (not pretty-printed).
- \`shots/\` \`audio/\` \`pages/\` \`scripts/\` \`playbooks/\` \`logs/\` \`bin/\`

System skills ship inside the extension and are not stored here. A user skill with the same id overrides a system skill.

There is no delete tool. Do not put Host URL/token in these files (\`.host-token\` is runtime).
`

const SECRET_FILES = new Set(['config/models.json', 'config/search.json'])

const TOKEN_FILE = '.host-token'
const DISABLED_FILE = path.join('skills', '.disabled')
const MCP_FILE = path.join('mcp', 'servers.json')

export type DiskSkill = {
  id: string
  version: string
  description: string
  instructions: string
  triggers?: string[]
  enabled: boolean
  relativePath: string
  files: string[]
}

export type WorkspaceEntry = {
  name: string
  kind: 'file' | 'dir'
  size?: number
  mtime?: number
}

export function defaultWorkspaceRoot(): string {
  return process.env.NAVIFORGE_WORKSPACE?.trim() || path.join(homedir(), 'NaviForge')
}

export async function ensureWorkspace(root: string): Promise<void> {
  await mkdir(root, { recursive: true })
  for (const dir of WORKSPACE_DIRS) {
    await mkdir(path.join(root, dir), { recursive: true })
  }
  const readme = path.join(root, 'README.md')
  try {
    await stat(readme)
  } catch {
    await writeFile(readme, WORKSPACE_README, 'utf8')
  }
  await seedDefaultScripts(path.join(root, 'scripts'))
}

export async function resolveHostToken(root: string, envToken?: string): Promise<string> {
  const fromEnv = envToken?.trim()
  if (fromEnv) return fromEnv
  const file = path.join(root, TOKEN_FILE)
  try {
    const existing = (await readFile(file, 'utf8')).trim()
    if (existing) return existing
  } catch {
    // first run
  }
  const token = randomBytes(24).toString('hex')
  await mkdir(root, { recursive: true })
  await writeFile(file, `${token}\n`, { encoding: 'utf8', mode: 0o600 })
  return token
}

/** Resolve `rel` under root; reject `..` and absolute paths. */
export function resolveSafe(root: string, rel: string): string {
  if (!rel || path.isAbsolute(rel) || rel.includes('\0')) throw new Error('path escapes workspace')
  const trimmed = rel.replace(/\\/g, '/')
  if (trimmed.split('/').some((part) => part === '..' || part === '')) {
    throw new Error('path escapes workspace')
  }
  const abs = path.resolve(root, trimmed)
  const base = path.resolve(root)
  const prefix = base.endsWith(path.sep) ? base : `${base}${path.sep}`
  if (abs !== base && !abs.startsWith(prefix)) throw new Error('path escapes workspace')
  return abs
}

export function parseSkillMarkdown(text: string): {
  id: string
  version: string
  description: string
  instructions: string
  triggers?: string[]
  enabled: boolean
} {
  if (!text.trim()) throw new Error('SKILL.md is empty')
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text)
  const values: Record<string, string> = {}
  let instructions = text.trim()
  if (match) {
    for (const line of match[1].split(/\r?\n/)) {
      const field = line.match(/^([A-Za-z][\w-]*):\s*(.*)$/)
      if (field) values[field[1].toLowerCase()] = field[2].replace(/^['"]|['"]$/g, '').trim()
    }
    instructions = match[2].trim()
  }
  if (!instructions) throw new Error('SKILL.md must include instructions')
  const name = values.id || values.name || 'skill'
  const id = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64) || 'skill'
  const triggers = values.triggers
    ?.split(',')
    .map((item) => item.trim())
    .filter(Boolean)
  return {
    id,
    version: values.version || '0.0.0',
    description: values.description || name,
    instructions,
    triggers: triggers?.length ? triggers : undefined,
    enabled: values.enabled !== 'false',
  }
}

async function readDisabled(root: string): Promise<string[]> {
  try {
    const raw = JSON.parse(await readFile(path.join(root, DISABLED_FILE), 'utf8')) as unknown
    return Array.isArray(raw) ? raw.filter((id): id is string => typeof id === 'string') : []
  } catch {
    return []
  }
}

async function writeDisabled(root: string, ids: string[]): Promise<void> {
  await mkdir(path.join(root, 'skills'), { recursive: true })
  await writeFile(path.join(root, DISABLED_FILE), `${JSON.stringify([...new Set(ids)], null, 2)}\n`)
}

const MAX_LIST_ENTRIES = 500 // ponytail: cap recursive list; paginate if a folder grows past this

export async function listDir(
  root: string,
  rel: string,
  recursive = false
): Promise<WorkspaceEntry[]> {
  const dir = rel ? resolveSafe(root, rel) : path.resolve(root)
  let names: string[]
  try {
    names = await readdir(dir)
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code
    if (code !== 'ENOENT') throw error
    const top = rel.split('/')[0]
    if (top && (WORKSPACE_DIRS as readonly string[]).includes(top)) {
      await mkdir(dir, { recursive: true })
    }
    return []
  }
  const entries: WorkspaceEntry[] = []
  for (const name of names) {
    if (name.startsWith('.') || entries.length >= MAX_LIST_ENTRIES) continue
    const abs = path.join(dir, name)
    const info = await stat(abs)
    if (recursive && info.isDirectory()) {
      const inner = await listDir(root, rel ? `${rel}/${name}` : name, true)
      for (const item of inner) {
        if (entries.length >= MAX_LIST_ENTRIES) break
        entries.push({ ...item, name: `${name}/${item.name}` })
      }
      continue
    }
    entries.push({
      name,
      kind: info.isDirectory() ? 'dir' : 'file',
      size: info.isFile() ? info.size : undefined,
      mtime: info.mtimeMs,
    })
  }
  return entries.sort((a, b) => a.name.localeCompare(b.name))
}

export async function readText(root: string, rel: string): Promise<string> {
  return readFile(resolveSafe(root, rel), 'utf8')
}

const IMAGE_MIME: Record<string, string> = {
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.webp': 'image/webp',
  '.gif': 'image/gif',
}

const AUDIO_MIME: Record<string, string> = {
  '.webm': 'audio/webm',
  '.ogg': 'audio/ogg',
  '.mp3': 'audio/mpeg',
  '.m4a': 'audio/mp4',
  '.wav': 'audio/wav',
}

/** ponytail: 8MB cap; compress client-side if vision APIs start 413ing. */
const MAX_IMAGE_BYTES = 8 * 1024 * 1024
const MAX_AUDIO_BYTES = 8 * 1024 * 1024

/** Raster image or short voice clip as a data URL. SVG rejected. */
export async function readDataUrl(root: string, rel: string): Promise<string> {
  const posix = rel.replace(/\\/g, '/')
  const ext = path.posix.extname(posix).toLowerCase()
  const mime = IMAGE_MIME[ext] ?? AUDIO_MIME[ext]
  if (!mime) throw new Error('not an image')
  const buf = await readFile(resolveSafe(root, posix))
  const kind = mime.startsWith('audio/') ? 'audio' : 'image'
  if (!buf.length) throw new Error(`empty ${kind}`)
  const max = kind === 'audio' ? MAX_AUDIO_BYTES : MAX_IMAGE_BYTES
  if (buf.length > max) throw new Error(`${kind} too large`)
  return `data:${mime};base64,${buf.toString('base64')}`
}

export async function writeText(root: string, rel: string, content: string): Promise<void> {
  const posix = rel.replace(/\\/g, '/')
  const abs = resolveSafe(root, posix)
  await mkdir(path.dirname(abs), { recursive: true })
  await writeFile(abs, content, 'utf8')
  if (SECRET_FILES.has(posix)) await chmod(abs, 0o600)
}

export async function appendJsonl(root: string, rel: string, line: TraceRecord): Promise<void> {
  const abs = resolveSafe(root, rel)
  await mkdir(path.dirname(abs), { recursive: true })
  await appendFile(abs, stringifyJsonlLine(validateTraceRecord(line)), 'utf8')
}

function shotName(kind: string): string {
  const safeKind = kind.replace(/[^a-z0-9]+/gi, '-').slice(0, 24) || 'shot'
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z')
  const shortId = randomBytes(3).toString('hex')
  return `${stamp}-${safeKind}-${shortId}.png`
}

function decodeDataUrl(dataUrl: string): Buffer {
  const match = /^data:image\/[a-zA-Z0-9+.-]+;base64,([A-Za-z0-9+/=\s]+)$/.exec(dataUrl.trim())
  if (!match) throw new Error('expected image data URL')
  const buf = Buffer.from(match[1].replace(/\s/g, ''), 'base64')
  if (!buf.length) throw new Error('empty image')
  return buf
}

function audioExtForMime(mime: string): string {
  const base = mime.split(';')[0]!.trim().toLowerCase()
  if (base === 'audio/mp4' || base === 'audio/aac' || base === 'audio/m4a') return '.m4a'
  if (base === 'audio/mpeg' || base === 'audio/mp3') return '.mp3'
  if (base === 'audio/ogg' || base === 'audio/opus') return '.ogg'
  if (base === 'audio/wav' || base === 'audio/wave') return '.wav'
  return '.webm'
}

function audioName(kind: string, ext: string): string {
  const safeKind = kind.replace(/[^a-z0-9]+/gi, '-').slice(0, 24) || 'voice'
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z')
  const shortId = randomBytes(3).toString('hex')
  return `${stamp}-${safeKind}-${shortId}${ext}`
}

/** MediaRecorder may emit `audio/webm;codecs=opus`. */
function decodeAudioDataUrl(dataUrl: string): { buf: Buffer; ext: string } {
  const match =
    /^data:(audio\/[a-zA-Z0-9+.-]+)(?:;[A-Za-z0-9.=+\-]+)*;base64,([A-Za-z0-9+/=\s]+)$/i.exec(
      dataUrl.trim()
    )
  if (!match) throw new Error('expected audio data URL')
  const buf = Buffer.from(match[2]!.replace(/\s/g, ''), 'base64')
  if (!buf.length) throw new Error('empty audio')
  return { buf, ext: audioExtForMime(match[1]!) }
}

export async function saveAudio(
  root: string,
  input: { kind?: string; dataUrl: string }
): Promise<{ relativePath: string }> {
  const { buf, ext } = decodeAudioDataUrl(input.dataUrl)
  if (buf.length > MAX_AUDIO_BYTES) throw new Error('audio too large')
  await mkdir(path.join(root, 'audio'), { recursive: true })
  const relativePath = path.join('audio', audioName(input.kind ?? 'voice', ext))
  await writeFile(resolveSafe(root, relativePath), buf)
  return { relativePath }
}

const MAX_PAGE_MD_CHARS = 2_000_000
/** ponytail: 8MB matches other media; raise with Host MAX_BODY_BYTES if printToPDF of long pages 413s. */
const MAX_PDF_BYTES = 8 * 1024 * 1024

function pageFileName(kind: 'md' | 'pdf', slug?: string): string {
  const safe =
    (slug || 'page')
      .toLowerCase()
      .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || 'page'
  const stamp = new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d+Z$/, 'Z')
  const shortId = randomBytes(3).toString('hex')
  return `${stamp}-${safe}-${shortId}.${kind}`
}

function decodePdfDataUrl(dataUrl: string): Buffer {
  const match = /^data:application\/pdf;base64,([A-Za-z0-9+/=\s]+)$/i.exec(dataUrl.trim())
  if (!match) throw new Error('expected pdf data URL')
  const buf = Buffer.from(match[1]!.replace(/\s/g, ''), 'base64')
  if (!buf.length) throw new Error('empty pdf')
  return buf
}

export async function savePage(
  root: string,
  input: { kind: string; content?: string; dataUrl?: string; slug?: string }
): Promise<{ relativePath: string; bytes: number }> {
  const kind = input.kind === 'pdf' ? 'pdf' : input.kind === 'md' ? 'md' : null
  if (!kind) throw new Error('kind must be md or pdf')
  await mkdir(path.join(root, 'pages'), { recursive: true })
  const relativePath = path.join('pages', pageFileName(kind, input.slug))
  if (kind === 'md') {
    const content = input.content ?? ''
    if (!content.trim()) throw new Error('empty markdown')
    if (content.length > MAX_PAGE_MD_CHARS) throw new Error('markdown too large')
    const buf = Buffer.from(content, 'utf8')
    await writeFile(resolveSafe(root, relativePath), buf)
    return { relativePath, bytes: buf.length }
  }
  const buf = decodePdfDataUrl(input.dataUrl ?? '')
  if (buf.length > MAX_PDF_BYTES) throw new Error('pdf too large')
  await writeFile(resolveSafe(root, relativePath), buf)
  return { relativePath, bytes: buf.length }
}

export function sessionFileName(threadId: string, slug?: string): string {
  const id = threadId.replace(/[^a-zA-Z0-9._-]/g, '').slice(0, 64) || 'thread'
  const safeSlug = (slug || 'thread')
    .toLowerCase()
    .replace(/[^a-z0-9\u4e00-\u9fff]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 40) || 'thread'
  return `${id}-${safeSlug}.jsonl`
}

async function findSessionFile(root: string, threadId: string, slug?: string): Promise<string> {
  const dir = path.join(root, 'sessions')
  await mkdir(dir, { recursive: true })
  const prefix = `${threadId.replace(/[^a-zA-Z0-9._-]/g, '').slice(0, 64)}-`
  try {
    const names = await readdir(dir)
    const existing = names.find((name) => name.startsWith(prefix) && name.endsWith('.jsonl'))
    if (existing) return path.join('sessions', existing)
  } catch {
    // empty
  }
  return path.join('sessions', sessionFileName(threadId, slug))
}

export async function appendSession(
  root: string,
  input: { threadId: string; slug?: string; title?: string; line: TraceRecord }
): Promise<{ relativePath: string }> {
  const relativePath = await findSessionFile(root, input.threadId, input.slug)
  const abs = resolveSafe(root, relativePath)
  await mkdir(path.dirname(abs), { recursive: true })
  await appendFile(abs, stringifyJsonlLine(validateTraceRecord(input.line)), 'utf8')
  return { relativePath }
}

export async function saveShot(
  root: string,
  input: {
    kind: string
    dataUrl: string
    threadId?: string
    slug?: string
    title?: string
    runId?: string
    tool?: string
  }
): Promise<{ relativePath: string }> {
  await mkdir(path.join(root, 'shots'), { recursive: true })
  const name = shotName(input.kind)
  const relativePath = path.join('shots', name)
  await writeFile(resolveSafe(root, relativePath), decodeDataUrl(input.dataUrl))
  if (input.threadId) {
    if (!input.runId) throw new Error('runId is required when saving a session artifact')
    await appendSession(root, {
      threadId: input.threadId,
      slug: input.slug,
      title: input.title,
      line: createTraceRecord({
        type: 'artifact.saved',
        runId: input.runId,
        payload: { kind: 'shot', path: relativePath, tool: input.tool ?? 'dom_screenshot' },
      }),
    })
  }
  return { relativePath }
}

const SKILL_RESOURCE_DIRS = ['scripts', 'references', 'assets'] as const
const MAX_SKILL_FILES = 40

async function listSkillResourceFiles(root: string, folderName: string): Promise<string[]> {
  const abs = path.join(root, 'skills', folderName)
  const files: string[] = []
  for (const dir of SKILL_RESOURCE_DIRS) {
    let names: string[]
    try {
      names = await readdir(path.join(abs, dir))
    } catch {
      continue
    }
    for (const name of names) {
      if (name.startsWith('.') || files.length >= MAX_SKILL_FILES) continue
      try {
        const info = await stat(path.join(abs, dir, name))
        if (info.isFile()) files.push(`skills/${folderName}/${dir}/${name}`)
      } catch {
        // skip
      }
    }
  }
  return files.sort()
}

export async function scanSkills(root: string): Promise<DiskSkill[]> {
  const dir = path.join(root, 'skills')
  await mkdir(dir, { recursive: true })
  const disabled = new Set(await readDisabled(root))
  const names = await readdir(dir)
  const skills: DiskSkill[] = []
  for (const name of names) {
    if (name.startsWith('.')) continue
    const skillMd = path.join(dir, name, 'SKILL.md')
    try {
      const info = await stat(skillMd)
      if (!info.isFile()) continue
      const parsed = parseSkillMarkdown(await readFile(skillMd, 'utf8'))
      const id = parsed.id || name
      skills.push({
        ...parsed,
        id,
        enabled: parsed.enabled && !disabled.has(id),
        relativePath: path.join('skills', name, 'SKILL.md'),
        files: await listSkillResourceFiles(root, name),
      })
    } catch {
      // skip malformed folders
    }
  }
  return skills.sort((a, b) => a.id.localeCompare(b.id))
}

export async function writeSkill(root: string, id: string, markdown: string): Promise<void> {
  const parsed = parseSkillMarkdown(markdown)
  const safeId =
    (id || parsed.id)
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 64) || 'skill'
  const rel = path.join('skills', safeId, 'SKILL.md')
  await writeText(root, rel, markdown)
}

export async function removeSkill(root: string, id: string): Promise<void> {
  const safeId = id.replace(/[^a-z0-9._-]/gi, '')
  if (!safeId) throw new Error('invalid skill id')
  await rm(path.join(root, 'skills', safeId), { recursive: true, force: true })
  const disabled = (await readDisabled(root)).filter((item) => item !== safeId)
  await writeDisabled(root, disabled)
}

export async function setSkillDisabled(root: string, id: string, disabled: boolean): Promise<void> {
  const current = await readDisabled(root)
  const next = disabled ? [...current, id] : current.filter((item) => item !== id)
  await writeDisabled(root, next)
}

export async function readMcp(root: string): Promise<{
  connections: NormalizedMcpServer[]
  issues: McpIssue[]
  text: string
  format: string
}> {
  let text = ''
  try {
    text = await readFile(path.join(root, MCP_FILE), 'utf8')
  } catch {
    return { connections: [], issues: [], text: '', format: 'empty' }
  }
  const parsed = parseMcpServersJson(text)
  if (
    (parsed.format === 'legacy-connections' || parsed.format === 'legacy-array') &&
    !mcpHasErrors(parsed.issues)
  ) {
    const next = serializeMcpServersJson(parsed.servers)
    await mkdir(path.join(root, 'mcp'), { recursive: true })
    await writeFile(path.join(root, MCP_FILE), next)
    return { connections: parsed.servers, issues: parsed.issues, text: next, format: 'cursor' }
  }
  return {
    connections: parsed.servers,
    issues: parsed.issues,
    text,
    format: parsed.format,
  }
}

export async function writeMcpText(root: string, text: string): Promise<{ issues: McpIssue[] }> {
  const parsed = parseMcpServersJson(text)
  if (mcpHasErrors(parsed.issues)) {
    const first = parsed.issues.find((issue) => issue.level === 'error')
    throw new Error(first ? `${first.message}。${first.hint}` : 'invalid MCP JSON')
  }
  await mkdir(path.join(root, 'mcp'), { recursive: true })
  await writeFile(path.join(root, MCP_FILE), text.endsWith('\n') ? text : `${text}\n`)
  return { issues: parsed.issues }
}

export async function writeMcp(root: string, connections: unknown[]): Promise<void> {
  const parsed = parseMcpServersJson(JSON.stringify({ connections }))
  await writeMcpText(root, serializeMcpServersJson(parsed.servers))
}

export async function writeScript(
  root: string,
  filename: string,
  content: string
): Promise<{ relativePath: string }> {
  const base = path.basename(filename)
  if (!base || base !== filename || base.includes('..')) throw new Error('invalid script filename')
  const relativePath = path.join('scripts', base)
  await writeText(root, relativePath, content)
  return { relativePath }
}

const CLEARABLE_DIRS = new Set(['scripts', 'playbooks'])

export async function clearWorkspaceDir(root: string, dir: string): Promise<void> {
  if (!CLEARABLE_DIRS.has(dir)) throw new Error('clearDir only allows scripts or playbooks')
  const abs = path.join(root, dir)
  await rm(abs, { recursive: true, force: true })
  await mkdir(abs, { recursive: true })
}

const NATIVE_HOST_NAME = 'com.naviforge.host'

function nativeMessagingDirs(): string[] {
  const home = homedir()
  if (process.platform === 'darwin') {
    return [
      path.join(home, 'Library/Application Support/Google/Chrome/NativeMessagingHosts'),
      path.join(home, 'Library/Application Support/Chromium/NativeMessagingHosts'),
    ]
  }
  return [
    path.join(home, '.config/google-chrome/NativeMessagingHosts'),
    path.join(home, '.config/chromium/NativeMessagingHosts'),
  ]
}

/** Chrome native-messaging host JSON so the extension can spawn the helper without LaunchAgent. */
export async function registerNativeHost(root: string, extensionId: string): Promise<{ written: string[] }> {
  if (!/^[a-p]{32}$/.test(extensionId)) throw new Error('invalid Chrome extension id')
  const here = path.dirname(fileURLToPath(import.meta.url))
  const nativeJs = path.join(here, 'native-host.js')
  const hostJs = path.join(here, 'index.js')
  const binDir = path.join(root, 'bin')
  await mkdir(binDir, { recursive: true })
  const wrapper = path.join(binDir, 'naviforge-host')
  const nativeWrapper = path.join(binDir, 'naviforge-native-host')
  await writeFile(
    wrapper,
    `#!/bin/sh\nexport NAVIFORGE_HOST_HTTP_ONLY=1\nexport NAVIFORGE_WORKSPACE=${JSON.stringify(root)}\nexec ${JSON.stringify(process.execPath)} ${JSON.stringify(hostJs)}\n`
  )
  await writeFile(
    nativeWrapper,
    `#!/bin/sh\nexport NAVIFORGE_HOST_HTTP_ONLY=1\nexport NAVIFORGE_WORKSPACE=${JSON.stringify(root)}\nexec ${JSON.stringify(process.execPath)} ${JSON.stringify(nativeJs)}\n`
  )
  await chmod(wrapper, 0o755)
  await chmod(nativeWrapper, 0o755)
  const manifest = `${JSON.stringify(
    {
      name: NATIVE_HOST_NAME,
      description: 'NaviForge local helper',
      path: nativeWrapper,
      type: 'stdio',
      allowed_origins: [`chrome-extension://${extensionId}/`],
    },
    null,
    2
  )}\n`
  const written: string[] = []
  for (const dir of nativeMessagingDirs()) {
    await mkdir(dir, { recursive: true })
    const file = path.join(dir, `${NATIVE_HOST_NAME}.json`)
    await writeFile(file, manifest)
    written.push(file)
  }
  return { written }
}

export function fileManagerCommand(platform = process.platform): string {
  return platform === 'darwin' ? 'open' : platform === 'win32' ? 'explorer' : 'xdg-open'
}

export async function openInFileManager(abs: string): Promise<void> {
  const cmd = fileManagerCommand()
  await new Promise<void>((resolve, reject) => {
    const child = spawn(cmd, [abs], { stdio: 'ignore', detached: true })
    child.once('error', reject)
    child.unref()
    resolve()
  })
}

export async function dispatchWorkspace(root: string, body: unknown): Promise<unknown> {
  if (!body || typeof body !== 'object') throw new Error('workspace body required')
  const rec = body as Record<string, unknown>
  const op = rec.op
  switch (op) {
    case 'status':
      return { root, ok: true }
    case 'list':
      return {
        entries: await listDir(root, String(rec.dir ?? ''), rec.recursive === true),
      }
    case 'read':
      return { content: await readText(root, String(rec.path ?? '')) }
    case 'readDataUrl':
      return { dataUrl: await readDataUrl(root, String(rec.path ?? '')) }
    case 'write': {
      const rel = String(rec.path ?? '').replace(/\\/g, '/')
      const content = String(rec.content ?? '')
      if (rel === MCP_FILE || rel === 'mcp/servers.json') {
        await writeMcpText(root, content)
      } else {
        await writeText(root, rel, content)
      }
      return { ok: true }
    }
    case 'mkdir': {
      const rel = String(rec.path ?? '')
      if (!rel) throw new Error('path required')
      await mkdirWorkspace(root, rel)
      return { ok: true, path: rel }
    }
    case 'touch': {
      const rel = String(rec.path ?? '')
      if (!rel) throw new Error('path required')
      await touchWorkspace(root, rel)
      return { ok: true, path: rel }
    }
    case 'stat': {
      const rel = String(rec.path ?? '')
      if (!rel) throw new Error('path required')
      return statWorkspace(root, rel)
    }
    case 'glob':
      return {
        paths: await globWorkspace(
          root,
          String(rec.pattern ?? '**/*'),
          typeof rec.path === 'string' ? rec.path : ''
        ),
      }
    case 'grep': {
      const pattern = String(rec.pattern ?? '')
      if (!pattern) throw new Error('pattern required')
      return {
        hits: await grepWorkspace(root, pattern, {
          path: typeof rec.path === 'string' ? rec.path : undefined,
          glob: typeof rec.glob === 'string' ? rec.glob : undefined,
          max: typeof rec.max === 'number' ? rec.max : undefined,
        }),
      }
    }
    case 'append': {
      if (typeof rec.threadId === 'string' && rec.threadId) {
        return appendSession(root, {
          threadId: rec.threadId,
          slug: typeof rec.slug === 'string' ? rec.slug : undefined,
          title: typeof rec.title === 'string' ? rec.title : undefined,
          line: validateTraceRecord(rec.line),
        })
      }
      await appendJsonl(root, String(rec.path ?? ''), validateTraceRecord(rec.line))
      return { ok: true }
    }
    case 'shot':
      return saveShot(root, {
        kind: String(rec.kind ?? 'visible'),
        dataUrl: String(rec.dataUrl ?? ''),
        threadId: typeof rec.threadId === 'string' ? rec.threadId : undefined,
        slug: typeof rec.slug === 'string' ? rec.slug : undefined,
        title: typeof rec.title === 'string' ? rec.title : undefined,
        runId: typeof rec.runId === 'string' ? rec.runId : undefined,
        tool: typeof rec.tool === 'string' ? rec.tool : undefined,
      })
    case 'audio':
      return saveAudio(root, {
        kind: typeof rec.kind === 'string' ? rec.kind : 'voice',
        dataUrl: String(rec.dataUrl ?? ''),
      })
    case 'page':
      return savePage(root, {
        kind: String(rec.kind ?? ''),
        content: typeof rec.content === 'string' ? rec.content : undefined,
        dataUrl: typeof rec.dataUrl === 'string' ? rec.dataUrl : undefined,
        slug: typeof rec.slug === 'string' ? rec.slug : undefined,
      })
    case 'scanSkills':
      return { skills: await scanSkills(root) }
    case 'writeSkill':
      await writeSkill(root, String(rec.id ?? ''), String(rec.markdown ?? ''))
      return { ok: true }
    case 'removeSkill':
      await removeSkill(root, String(rec.id ?? ''))
      return { ok: true }
    case 'setSkillDisabled':
      await setSkillDisabled(root, String(rec.id ?? ''), rec.disabled === true)
      return { ok: true }
    case 'readMcp':
      return readMcp(root)
    case 'validateMcp':
      return parseMcpServersJson(String(rec.text ?? ''))
    case 'writeMcp': {
      const connections = Array.isArray(rec.connections) ? rec.connections : []
      await writeMcp(root, connections)
      return { ok: true }
    }
    case 'writeMcpText':
      return { ok: true, ...(await writeMcpText(root, String(rec.text ?? ''))) }
    case 'registerNative':
      return registerNativeHost(root, String(rec.extensionId ?? ''))
    case 'writeScript':
      return writeScript(root, String(rec.filename ?? ''), String(rec.content ?? ''))
    case 'clearDir':
      await clearWorkspaceDir(root, String(rec.dir ?? ''))
      return { ok: true }
    case 'open': {
      const rel = typeof rec.path === 'string' && rec.path ? rec.path : ''
      const abs = rel ? resolveSafe(root, rel) : path.resolve(root)
      await openInFileManager(abs)
      return { ok: true }
    }
    default:
      throw new Error(`unknown workspace op: ${String(op)}`)
  }
}
