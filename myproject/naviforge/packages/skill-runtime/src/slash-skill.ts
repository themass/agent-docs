import type { Skill } from './index.js'

/** Pi / Agent Skills compatible slash prefix. */
export const SKILL_SLASH_PREFIX = 'skill:'

export function skillSlashName(skillId: string): string {
  return `${SKILL_SLASH_PREFIX}${skillId}`
}

export function parseSkillSlashName(commandName: string): string | null {
  const trimmed = commandName.trim()
  if (!trimmed.startsWith(SKILL_SLASH_PREFIX)) return null
  const id = trimmed.slice(SKILL_SLASH_PREFIX.length).trim()
  return id || null
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

/**
 * Expand `/skill:<id> [args]` to agent user prompt (pi-compatible XML block).
 * @see https://agentskills.io — progressive disclosure L2 inject on explicit slash.
 */
export function expandSkillSlashPayload(
  skill: Skill,
  args: string,
  opts?: { location?: string; baseDir?: string }
): string {
  const location = opts?.location ?? `skill://${skill.manifest.id}`
  const baseDir = opts?.baseDir ?? location
  const body = skill.instructions.trim()
  const files = skill.files?.length
    ? `\n\nBundled files (read on demand):\n${skill.files.map((file) => `- ${file}`).join('\n')}`
    : ''
  const skillBlock = `<skill name="${escapeXml(skill.manifest.id)}" location="${escapeXml(location)}">
References are relative to ${baseDir}.

${body}${files}
</skill>`
  const trimmedArgs = args.trim()
  return trimmedArgs ? `${skillBlock}\n\n${trimmedArgs}` : skillBlock
}
