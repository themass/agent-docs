export type SkillManifest = {
  id: string
  version: string
  description: string
  triggers?: string[]
  /** Hidden from L1 catalog; `skill_load` still resolves via `aliasOf`. */
  aliasOf?: string
  l1?: boolean
  permissions?: {
    /** Exact Agent tool names this skill may use. Empty means no additional restriction. */
    tools?: string[]
    /** Informational Chrome match patterns for future install-time host grants. */
    hosts?: string[]
  }
}

export type Skill = {
  manifest: SkillManifest
  /**
   * Full body (SKILL.md instructions). Progressive disclosure L2 — returned only via
   * `skill_load`, never dumped into the system/user prompt by default.
   */
  instructions: string
  /**
   * Workspace-relative paths under scripts/, references/, assets/ (Agent Skills L3).
   * Read on demand with workspace read action; never dumped into L1.
   */
  files?: string[]
}

const MIN_ROUTE_SCORE = 2

export function isL1Skill(skill: Skill): boolean {
  return !skill.manifest.aliasOf && skill.manifest.l1 !== false
}

function routingPositiveText(description: string): string {
  const non = description.split(/非：|不要用于|不适用/i)[0] ?? description
  return non.replace(/何时使用：|用途：|触发：/g, ' ')
}

function routingExclusions(description: string): string[] {
  const tail = description.split(/非：|不要用于|不适用/i)[1]
  if (!tail) return []
  return tail
    .toLowerCase()
    .split(/[^a-z0-9\u4e00-\u9fff]+/)
    .filter((word) => word.length >= 2)
}

/** Soft routing hint — never injects body; model still chooses via skill_load. */
export function routeSkills(task: string, skills: Skill[], limit = 3): Skill[] {
  const t = task.toLowerCase()
  const tokenize = (text: string): string[] =>
    text
      .toLowerCase()
      .split(/[^a-z0-9\u4e00-\u9fff]+/)
      .filter((word) => word.length >= 2)
  const scored = skills
    .filter(isL1Skill)
    .map((s) => {
      const exclusions = routingExclusions(s.manifest.description)
      if (exclusions.some((word) => t.includes(word))) return { s, score: 0 }
      let score = 0
      if (t.includes(s.manifest.id.toLowerCase())) score += 3
      for (const trigger of s.manifest.triggers ?? []) {
        const key = trigger.toLowerCase()
        if (key.length >= 2 && t.includes(key)) score += 2
      }
      for (const word of tokenize(routingPositiveText(s.manifest.description))) {
        if (t.includes(word)) score += 1
      }
      return { s, score }
    })
    .filter((x) => x.score >= MIN_ROUTE_SCORE)
    .sort((a, b) => b.score - a.score)
  return scored.slice(0, limit).map((x) => x.s)
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * L1 advertise — name + description only (progressive disclosure).
 * Bodies stay behind skill_load; lookup still accepts id@version.
 */
export function formatSkillCatalog(skills: Skill[]): string {
  const visible = skills.filter(isL1Skill)
  if (!visible.length) return '(none installed)'
  const items = visible
    .map(
      (s) =>
        `  <skill>\n    <name>${escapeXml(s.manifest.id)}</name>\n    <description>${escapeXml(s.manifest.description)}</description>\n  </skill>`
    )
    .join('\n')
  return `<available_skills>\n${items}\n</available_skills>`
}

/** Optional soft hint line for the model (not a body inject). */
export function formatSkillHints(skills: Skill[]): string {
  if (!skills.length) return ''
  return `suggested: ${skills.map((s) => s.manifest.id).join(', ')}`
}

/**
 * One Skill section body for system instructions: protocol + L1 catalog.
 * Bodies are NEVER included — model calls skill_load for L2.
 */
export function formatSkillGuidance(
  skills: Skill[],
  opts: { expandBody?: boolean; hints?: Skill[] } = {}
): string {
  if (!skills.length) return ''
  const catalog = [
    'Skills: L1=下列目录；正文仅 skill_load；不得声称未加载的 skill。',
    '尚未加载时才 skill_load；已加载的勿重复 load。',
    '',
    formatSkillCatalog(skills),
  ].join('\n')
  const hint = opts.hints?.length ? `\n${formatSkillHints(opts.hints)}` : ''
  if (opts.expandBody) {
    /* kept for API compat; do not expand */
  }
  return `${catalog}${hint}`
}

/** Accept `id` or `id@version` from model / catalog copy-paste. */
export function parseSkillRef(ref: string): { id: string; version?: string } {
  const at = ref.lastIndexOf('@')
  if (at <= 0) return { id: ref }
  return { id: ref.slice(0, at), version: ref.slice(at + 1) || undefined }
}

export function findSkill(skills: Skill[], ref: string): Skill | undefined {
  const { id, version } = parseSkillRef(ref.trim())
  const matches = skills.filter((item) => item.manifest.id === ref || item.manifest.id === id)
  if (!matches.length) return undefined
  if (version) return matches.find((item) => item.manifest.version === version)
  return matches[0]
}

export function resolveCanonicalSkill(skills: Skill[], ref: string): Skill | undefined {
  const found = findSkill(skills, ref)
  if (!found) return undefined
  if (found.manifest.aliasOf) return findSkill(skills, found.manifest.aliasOf) ?? found
  return found
}

export function formatSkillFiles(files: string[] | undefined): string {
  if (!files?.length) return ''
  return `\n\nBundled files (workspace read when needed; do not load all):\n${files.map((file) => `- ${file}`).join('\n')}`
}

export {
  expandSkillSlashPayload,
  parseSkillSlashName,
  skillSlashName,
  SKILL_SLASH_PREFIX,
} from './slash-skill.js'

export function loadSkillBody(skills: Skill[], id: string): string | null {
  const skill = resolveCanonicalSkill(skills, id)
  if (!skill) return null
  const tools = skill.manifest.permissions?.tools
  const header = [
    `# skill:${skill.manifest.id}@${skill.manifest.version}`,
    skill.manifest.description,
    tools?.length ? `Suggested tools (advisory unless hard allowlist): ${tools.join(', ')}` : '',
  ]
    .filter(Boolean)
    .join('\n')
  return `${header}\n\n${skill.instructions.trim()}${formatSkillFiles(skill.files)}`
}
