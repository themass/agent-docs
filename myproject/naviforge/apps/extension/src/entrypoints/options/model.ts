import type { Skill } from '@naviforge/skill-runtime'
import { parseSkillMarkdown } from '../../lib/github-skill'
import { trimActivities } from '../../lib/settings'

export { trimActivities }

export type Section =
  | 'account'
  | 'toolkit'
  | 'plugins'
  | 'automation'
  | 'workspace'
  | 'geniusFall'
  | 'behaviorForge'
  | 'settings'

export const NAV_ITEMS: {
  id: Section
  label: string
  eyebrow: string
}[] = [
  { id: 'account', label: '登录', eyebrow: 'Account' },
  { id: 'toolkit', label: '工具', eyebrow: 'Toolkit' },
  { id: 'plugins', label: '插件', eyebrow: 'Extend' },
  { id: 'automation', label: '自动化', eyebrow: 'Forge' },
  { id: 'workspace', label: '工作区', eyebrow: 'Disk' },
  { id: 'geniusFall', label: '天才陨落', eyebrow: 'Quota' },
  { id: 'settings', label: '设置', eyebrow: 'Control' },
]

export const SETTINGS_SECTION_IDS = NAV_ITEMS.map((item) => item.id)

export function sectionFromHash(raw: string = location.hash): Section {
  const hash = raw.replace(/^#/, '')
  if (hash === 'behaviorForge') return 'workspace'
  const ids = NAV_ITEMS.map((item) => item.id)
  return ids.includes(hash as Section) ? (hash as Section) : 'settings'
}

export const SESSION_NAV_ITEM = NAV_ITEMS.find((item) => item.id === 'automation')!

export function isEmbeddedSurface(search: string): boolean {
  return new URLSearchParams(search).get('embedded') === '1'
}

export function describeSystem(input: {
  modelConfigured: boolean
  hostEnabled: boolean
  enabledSkills: number
  totalSkills: number
  enabledConnections: number
}): { ready: number; total: number } {
  return {
    ready: [
      input.modelConfigured,
      input.hostEnabled,
      input.enabledSkills > 0,
      input.enabledConnections > 0,
    ].filter(Boolean).length,
    total: 4,
  }
}

export function parseImportedSkill(text: string): Skill {
  const trimmed = text.trim().replace(/^\uFEFF/, '')
  if (trimmed.startsWith('{')) {
    const value = JSON.parse(trimmed) as Skill
    if (
      !value?.manifest?.id ||
      !value.manifest.version ||
      !value.manifest.description ||
      !value.instructions
    ) {
      throw new Error('必须包含 manifest.id/version/description 与 instructions')
    }
    return value
  }
  return parseSkillMarkdown(trimmed)
}

export function nextCopyTitle(title: string, existingTitles: string[]): string {
  // Strip any stacked " · Copy" / " · Copy N" suffixes left by older builds.
  const base = title.replace(/(?: · Copy(?: \d+)?)+$/g, '').trim()
  const copies = existingTitles
    .map((value) => {
      const cleaned = value.replace(/(?: · Copy(?: \d+)?)+$/g, '').trim()
      if (cleaned !== base) return 0
      const numbered = /(?: · Copy(?: (\d+))?)+$/.exec(value)
      return numbered ? Number(numbered[1] ?? 1) : 0
    })
    .filter((n) => n > 0)
  const next = copies.length ? Math.max(...copies) + 1 : 1
  return `${base} · Copy ${next}`
}

