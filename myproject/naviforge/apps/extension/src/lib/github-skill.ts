import type { Skill } from '@naviforge/skill-runtime'

export type GitHubSkillSource = {
  owner: string
  repository: string
  ref: string
  path: string
  rawUrl: string
  pageUrl: string
}

export type InstalledGitHubSkill = Skill & {
  source: GitHubSkillSource & { installedAt: number }
}

const MAX_SKILL_CHARS = 200_000

function safeSegment(value: string, label: string): string {
  if (!value || value.includes('..') || value.includes('\\')) throw new Error(`Invalid GitHub ${label}`)
  return value
}

export function parseGitHubSkillUrl(value: string): GitHubSkillSource {
  const url = new URL(value)
  if (url.protocol !== 'https:') throw new Error('Skill URL must use HTTPS')
  const parts = url.pathname.split('/').filter(Boolean).map(decodeURIComponent)
  let owner: string
  let repository: string
  let ref: string
  let path: string

  if (url.hostname === 'github.com') {
    if (parts.length < 2) throw new Error('GitHub repository URL is required')
    ;[owner, repository] = parts
    if (parts[2] === 'blob' || parts[2] === 'tree') {
      ref = safeSegment(parts[3] ?? '', 'ref')
      path = parts.slice(4).join('/')
    } else {
      ref = 'HEAD'
      path = parts.slice(2).join('/')
    }
  } else if (url.hostname === 'raw.githubusercontent.com') {
    if (parts.length < 4) throw new Error('Raw GitHub SKILL.md URL is required')
    ;[owner, repository, ref] = parts
    path = parts.slice(3).join('/')
  } else {
    throw new Error('Only github.com URLs are supported')
  }

  owner = safeSegment(owner!, 'owner')
  repository = safeSegment(repository!, 'repository')
  ref = safeSegment(ref!, 'ref')
  path = path || 'SKILL.md'
  if (!path.endsWith('SKILL.md')) path = `${path.replace(/\/$/, '')}/SKILL.md`
  if (path.split('/').some((part) => !part || part === '..')) {
    throw new Error('GitHub URL must point to a safe repository path')
  }

  return {
    owner,
    repository,
    ref,
    path,
    rawUrl: `https://raw.githubusercontent.com/${owner}/${repository}/${ref}/${path}`,
    pageUrl: `https://github.com/${owner}/${repository}/blob/${ref}/${path}`,
  }
}

function frontmatter(text: string): { values: Record<string, string>; instructions: string } {
  const match = /^---\r?\n([\s\S]*?)\r?\n---\r?\n?([\s\S]*)$/.exec(text)
  if (!match) return { values: {}, instructions: text.trim() }
  const values = Object.fromEntries(
    match[1]
      .split(/\r?\n/)
      .map((line) => line.match(/^([A-Za-z][\w-]*):\s*(.+)$/))
      .filter((line): line is RegExpMatchArray => Boolean(line))
      .map((line) => [line[1].toLowerCase(), line[2].replace(/^['"]|['"]$/g, '').trim()])
  )
  return { values, instructions: match[2].trim() }
}

function skillId(value: string): string {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64) || 'github-skill'
}

export function parseSkillMarkdown(text: string, fallbackName = 'imported-skill'): Skill {
  if (!text.trim()) throw new Error('SKILL.md is empty')
  if (text.length > MAX_SKILL_CHARS) throw new Error('SKILL.md exceeds 200KB limit')
  const parsed = frontmatter(text)
  const name = parsed.values.id ?? parsed.values.name ?? fallbackName
  if (!parsed.instructions) throw new Error('SKILL.md must include instructions')
  return {
    manifest: {
      id: skillId(name),
      version: parsed.values.version ?? '0.0.0',
      description: parsed.values.description ?? name,
      triggers: parsed.values.triggers?.split(',').map((value) => value.trim()).filter(Boolean),
    },
    instructions: parsed.instructions,
  }
}

export function parseGitHubSkill(text: string, source: GitHubSkillSource): InstalledGitHubSkill {
  const name = source.path.split('/').slice(-2, -1)[0] ?? source.repository
  const skill = parseSkillMarkdown(text, name)
  return {
    ...skill,
    manifest: {
      ...skill.manifest,
      description:
        skill.manifest.description === skill.manifest.id
          ? `Imported from ${source.owner}/${source.repository}`
          : skill.manifest.description,
    },
    source: { ...source, installedAt: Date.now() },
  }
}

const RESOURCE_DIRS = new Set(['scripts', 'references', 'assets'])
const MAX_RESOURCE_FILES = 20
const MAX_RESOURCE_CHARS = 100_000

export function githubSkillDir(source: GitHubSkillSource): string {
  return source.path.replace(/\/SKILL\.md$/i, '').replace(/\/$/, '')
}

export function skillResourcePath(skillId: string, dir: string, filename: string): string {
  const id = skillId.replace(/[^a-z0-9._-]/gi, '')
  const base = filename.replace(/^.*[/\\]/, '')
  if (!id || !RESOURCE_DIRS.has(dir) || !base || base.startsWith('.')) {
    throw new Error('invalid skill resource path')
  }
  return `skills/${id}/${dir}/${base}`
}

type GitHubContent = {
  name: string
  type: string
  download_url?: string | null
}

/** One-level scripts/ references/ assets/ next to SKILL.md. Does not execute anything. */
export async function fetchGitHubSkillResources(
  source: GitHubSkillSource,
  skillId: string
): Promise<Array<{ path: string; content: string }>> {
  const dir = githubSkillDir(source)
  const listingUrl = `https://api.github.com/repos/${source.owner}/${source.repository}/contents/${dir}?ref=${encodeURIComponent(source.ref)}`
  const listing = await fetch(listingUrl, { headers: { Accept: 'application/vnd.github+json' } })
  if (!listing.ok) return []
  const entries = (await listing.json()) as GitHubContent[]
  if (!Array.isArray(entries)) return []
  const out: Array<{ path: string; content: string }> = []
  for (const entry of entries) {
    if (entry.type !== 'dir' || !RESOURCE_DIRS.has(entry.name) || out.length >= MAX_RESOURCE_FILES) continue
    const innerUrl = `https://api.github.com/repos/${source.owner}/${source.repository}/contents/${dir ? `${dir}/` : ''}${entry.name}?ref=${encodeURIComponent(source.ref)}`
    const innerRes = await fetch(innerUrl, { headers: { Accept: 'application/vnd.github+json' } })
    if (!innerRes.ok) continue
    const files = (await innerRes.json()) as GitHubContent[]
    if (!Array.isArray(files)) continue
    for (const file of files) {
      if (file.type !== 'file' || !file.download_url || out.length >= MAX_RESOURCE_FILES) continue
      const response = await fetch(file.download_url)
      if (!response.ok) continue
      const text = await response.text()
      if (!text || text.length > MAX_RESOURCE_CHARS) continue
      out.push({ path: skillResourcePath(skillId, entry.name, file.name), content: text })
    }
  }
  return out
}
