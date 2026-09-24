import { mkdir, readdir, readFile, stat, utimes, writeFile } from 'node:fs/promises'
import path from 'node:path'

import { resolveSafe } from './workspace.js'

const SKIP_DIRS = new Set(['bin', 'logs', 'node_modules', '.git'])
const GLOB_LIMIT = 200
const GREP_LIMIT = 50
const GREP_MAX_BYTES = 1_000_000
const BINARY_EXT = /\.(png|jpe?g|gif|webp|pdf|woff2?|zip|gz|tgz|mp4|mp3|wasm|bin)$/i

export type WorkspaceStat = {
  path: string
  kind: 'file' | 'dir'
  size?: number
  mtime?: number
}

export type GrepHit = {
  path: string
  line: number
  text: string
}

/** Convert a glob pattern to a full-string RegExp. */
export function globToRegExp(pattern: string): RegExp {
  const src = pattern.replace(/\\/g, '/').replace(/^\/+/, '')
  let out = '^'
  for (let i = 0; i < src.length; i++) {
    if (src.startsWith('**/', i)) {
      out += '(?:.*/)?'
      i += 2
      continue
    }
    if (src[i] === '*' && src[i + 1] === '*') {
      out += '.*'
      i += 1
      continue
    }
    if (src[i] === '*') {
      out += '[^/]*'
      continue
    }
    if (src[i] === '?') {
      out += '[^/]'
      continue
    }
    const ch = src[i]!
    out += '\\^$+()[]{}|.'.includes(ch) ? `\\${ch}` : ch
  }
  return new RegExp(`${out}$`)
}

export async function mkdirWorkspace(root: string, rel: string): Promise<void> {
  await mkdir(resolveSafe(root, rel), { recursive: true })
}

export async function touchWorkspace(root: string, rel: string): Promise<void> {
  const abs = resolveSafe(root, rel)
  await mkdir(path.dirname(abs), { recursive: true })
  try {
    const now = new Date()
    await utimes(abs, now, now)
  } catch {
    await writeFile(abs, '', { flag: 'wx' })
  }
}

export async function statWorkspace(root: string, rel: string): Promise<WorkspaceStat> {
  const posix = rel.replace(/\\/g, '/')
  const info = await stat(resolveSafe(root, posix))
  return {
    path: posix,
    kind: info.isDirectory() ? 'dir' : 'file',
    size: info.isFile() ? info.size : undefined,
    mtime: info.mtimeMs,
  }
}

export async function globWorkspace(
  root: string,
  pattern: string,
  prefix = ''
): Promise<string[]> {
  const matcher = globToRegExp(pattern.trim() || '**/*')
  const acc: string[] = []
  await walkFiles(root, prefix.replace(/\\/g, '/').replace(/^\/+|\/+$/g, ''), acc, matcher, GLOB_LIMIT)
  return acc
}

export async function grepWorkspace(
  root: string,
  pattern: string,
  opts: { path?: string; glob?: string; max?: number } = {}
): Promise<GrepHit[]> {
  let re: RegExp
  try {
    re = new RegExp(pattern)
  } catch {
    throw new Error('invalid grep pattern')
  }
  const max = Math.min(200, Math.max(1, opts.max ?? GREP_LIMIT))
  const base = (opts.path ?? '').replace(/\\/g, '/').replace(/^\/+|\/+$/g, '')
  let files: string[]
  if (base) {
    const abs = resolveSafe(root, base)
    const info = await stat(abs)
    files = info.isFile()
      ? [base]
      : await globWorkspace(root, opts.glob ?? '**/*', base)
  } else {
    files = await globWorkspace(root, opts.glob ?? '**/*', '')
  }
  const hits: GrepHit[] = []
  for (const rel of files) {
    if (hits.length >= max) break
    if (BINARY_EXT.test(rel)) continue
    const abs = path.join(root, rel)
    let content: string
    try {
      const info = await stat(abs)
      if (!info.isFile() || info.size > GREP_MAX_BYTES) continue
      content = await readFile(abs, 'utf8')
    } catch {
      continue
    }
    if (content.includes('\0')) continue
    const lines = content.split('\n')
    for (let i = 0; i < lines.length; i++) {
      if (!re.test(lines[i]!)) continue
      hits.push({ path: rel, line: i + 1, text: lines[i]!.slice(0, 240) })
      if (hits.length >= max) break
    }
  }
  return hits
}

async function walkFiles(
  root: string,
  dirRel: string,
  acc: string[],
  matcher: RegExp,
  limit: number
): Promise<void> {
  if (acc.length >= limit) return
  const abs = dirRel ? resolveSafe(root, dirRel) : path.resolve(root)
  let names: string[]
  try {
    names = await readdir(abs)
  } catch {
    return
  }
  names.sort()
  for (const name of names) {
    if (acc.length >= limit) return
    if (name.startsWith('.')) continue
    const rel = dirRel ? `${dirRel}/${name}` : name
    let info: Awaited<ReturnType<typeof stat>>
    try {
      info = await stat(path.join(abs, name))
    } catch {
      continue
    }
    if (info.isDirectory()) {
      if (SKIP_DIRS.has(name)) continue
      await walkFiles(root, rel, acc, matcher, limit)
      continue
    }
    if (matcher.test(rel)) acc.push(rel)
  }
}
