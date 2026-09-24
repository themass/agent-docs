/**
 * Unified slash-command registry (pi / Agent Skills / Cursor-style composer).
 *
 * ## 两类命令 — 不是都用 Skill 实现
 *
 * | kind     | source   | 注册方式                         | 执行方式                    |
 * |----------|----------|----------------------------------|-----------------------------|
 * | handler  | builtin  | `BUILTIN_SLASH_COMMANDS` 表       | TS handler（不走 LLM）      |
 * | expand   | skill    | 扫描已启用 Skill → `/skill:id`  | 展开 SKILL 正文 + args → Agent |
 * | expand   | prompt   | （预留）prompt 模板目录           | 展开模板 → Agent            |
 *
 * **Skill 只负责 `expand` 类**；`/hello`、`/check` 等内置是 `handler`。
 * 扩展命令（未来）用 `registerSlashCommand()` 追加 handler，与 pi `registerCommand` 同层。
 */
import { skillSlashName, type Skill } from '@naviforge/skill-runtime'

export type SlashCommandSource = 'builtin' | 'skill' | 'prompt' | 'extension'

/** handler = 立即执行代码；expand = 改写成 Agent 用户消息 */
export type SlashCommandKind = 'handler' | 'expand'

export type SlashCommandDef = {
  /** Invocation name without `/` — e.g. `hello` or `skill:catalog-crawl-sop` */
  name: string
  label: string
  hint: string
  argumentHint?: string
  source: SlashCommandSource
  kind: SlashCommandKind
  aliases?: string[]
  /** Set when source === 'skill' */
  skillId?: string
}

/** Matches `hello`, `check`, `skill:my-skill` (Agent Skills id chars). */
export const SLASH_COMMAND_NAME_PATTERN = '(?:skill:[\\w.-]+|[\\w-]+)'
const SLASH_DRAFT_RE = new RegExp(`^\\/(${SLASH_COMMAND_NAME_PATTERN})(?:\\s([\\s\\S]*))?$`)
const SLASH_AUTO_LOCK_RE = new RegExp(`^\\/(${SLASH_COMMAND_NAME_PATTERN})\\s+([\\s\\S]*)$`)

const BUILTIN_SLASH_COMMANDS: SlashCommandDef[] = [
  {
    name: 'hello',
    label: 'Hello',
    hint: '连通性自检 · 返回 pong',
    source: 'builtin',
    kind: 'handler',
  },
  {
    name: 'check',
    label: 'Check',
    hint: '扩展 · 模型 · 托管登录状态检查',
    argumentHint: '',
    source: 'builtin',
    kind: 'handler',
    aliases: ['status'],
  },
  {
    name: 'page',
    label: 'Page Q&A',
    hint: '页面问答（单次看图/读页）',
    argumentHint: '<question>',
    source: 'builtin',
    kind: 'handler',
    aliases: ['ask'],
  },
  {
    name: 'summarize',
    label: 'Summarize page',
    hint: '总结当前网页',
    argumentHint: '<instruction>',
    source: 'builtin',
    kind: 'handler',
    aliases: ['sum'],
  },
  {
    name: 'explain',
    label: 'Explain selection',
    hint: '解释网页选中内容',
    argumentHint: '<question>',
    source: 'builtin',
    kind: 'handler',
  },
  {
    name: 'copy',
    label: 'Copy article',
    hint: '复制正文到剪贴板',
    source: 'builtin',
    kind: 'handler',
    aliases: ['article'],
  },
]

const extensionCommands: SlashCommandDef[] = []

/** Runtime extension hook — mirrors pi `registerCommand` (handler only). */
export function registerSlashCommand(def: SlashCommandDef): void {
  if (def.kind !== 'handler' || def.source !== 'extension') {
    throw new Error('registerSlashCommand: only extension handler commands are supported')
  }
  const key = def.name.trim().toLowerCase()
  const dup = [...BUILTIN_SLASH_COMMANDS, ...extensionCommands].find(
    (item) => item.name.toLowerCase() === key
  )
  if (dup) throw new Error(`slash command already registered: ${def.name}`)
  extensionCommands.push(def)
}

export function buildSlashCommandRegistry(skills: Skill[]): SlashCommandDef[] {
  const skillCommands: SlashCommandDef[] = skills.map((skill) => ({
    name: skillSlashName(skill.manifest.id),
    label: skill.manifest.id,
    hint: skill.manifest.description.split('\n')[0]?.slice(0, 160) ?? skill.manifest.id,
    argumentHint: '<task>',
    source: 'skill',
    kind: 'expand',
    skillId: skill.manifest.id,
  }))
  return [...BUILTIN_SLASH_COMMANDS, ...extensionCommands, ...skillCommands]
}

export function resolveSlashCommand(
  name: string,
  registry: SlashCommandDef[]
): SlashCommandDef | undefined {
  const key = name.trim().toLowerCase()
  if (!key) return undefined
  return registry.find(
    (item) =>
      item.name.toLowerCase() === key ||
      item.aliases?.some((alias) => alias.toLowerCase() === key)
  )
}

export function filterSlashCommands(query: string, registry: SlashCommandDef[]): SlashCommandDef[] {
  const q = query.trim().toLowerCase()
  if (!q) return [...registry]
  return registry.filter((item) => {
    if (item.name.toLowerCase().includes(q)) return true
    if (item.label.toLowerCase().includes(q)) return true
    if (item.hint.toLowerCase().includes(q)) return true
    if (item.aliases?.some((alias) => alias.toLowerCase().includes(q))) return true
    if (item.skillId && `skill:${item.skillId}`.toLowerCase().includes(q)) return true
    return false
  })
}

/** Label to show in menu + where to paint the query substring red (contains match). */
export function slashCommandMenuLabel(
  item: SlashCommandDef,
  query: string
): { label: string; hitStart: number; hitEnd: number } {
  const q = query.trim().toLowerCase()
  const candidates = [item.name, ...(item.aliases ?? [])]
  if (!q) return { label: item.name, hitStart: 0, hitEnd: 0 }
  for (const candidate of candidates) {
    const idx = candidate.toLowerCase().indexOf(q)
    if (idx >= 0) return { label: candidate, hitStart: idx, hitEnd: idx + query.length }
  }
  return { label: item.name, hitStart: 0, hitEnd: 0 }
}

export type SlashDraft =
  | { kind: 'closed' }
  | { kind: 'menu'; query: string }
  | { kind: 'locked'; command: SlashCommandDef; body: string }

export function parseSlashDraft(
  value: string,
  locked: SlashCommandDef | null,
  registry: SlashCommandDef[] = buildSlashCommandRegistry([])
): SlashDraft {
  return parseSlashDraftWithRegistry(value, locked, registry)
}

export function parseSlashDraftWithRegistry(
  value: string,
  _locked: SlashCommandDef | null,
  registry: SlashCommandDef[]
): SlashDraft {
  if (!value.startsWith('/')) return { kind: 'closed' }
  const rest = value.slice(1)
  const spaceIdx = rest.search(/\s/)
  if (spaceIdx >= 0) {
    const name = rest.slice(0, spaceIdx)
    const body = rest.slice(spaceIdx + 1)
    const command = resolveSlashCommand(name, registry)
    if (command) return { kind: 'locked', command, body }
    return { kind: 'closed' }
  }
  return { kind: 'menu', query: rest }
}

export function tryParseSlashAutoLock(
  text: string,
  registry: SlashCommandDef[]
): { command: SlashCommandDef; body: string } | null {
  const match = text.match(SLASH_AUTO_LOCK_RE)
  if (!match) return null
  const command = resolveSlashCommand(match[1] ?? '', registry)
  if (!command) return null
  return { command, body: match[2] ?? '' }
}

export function slashCommandLabel(command: SlashCommandDef): string {
  return `/${command.name}`
}

export function formatSlashUserText(command: SlashCommandDef, body: string): string {
  const trimmed = body.trim()
  return trimmed ? `${slashCommandLabel(command)} ${trimmed}` : slashCommandLabel(command)
}

export function parseSlashInvocation(text: string): { name: string; args: string } | null {
  const trimmed = text.trim()
  if (!trimmed.startsWith('/')) return null
  const match = trimmed.match(SLASH_DRAFT_RE)
  if (!match?.[1]) return null
  return { name: match[1], args: (match[2] ?? '').trim() }
}
