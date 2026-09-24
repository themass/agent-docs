import type { Skill } from '@naviforge/skill-runtime'
import { expandSkillSlashPayload, findSkill } from '@naviforge/skill-runtime'

import {
  formatSlashUserText,
  resolveSlashCommand,
  type SlashCommandDef,
} from '../components/chat/composer-slash-registry'
import { getActiveModelProfile, loadModelProfiles } from '../lib/llm-profiles'
import { isNewApiLoggedIn, loadNewApiAuth, NEWAPI_PORTAL_BASE } from '../lib/newapi-auth'

export type SlashRunnerDeps = {
  registry: SlashCommandDef[]
  enabledSkills: Skill[]
  setTask(value: string): void
  setPageAskMode(enabled: boolean): void
  enqueueTask(text?: string): void
  appendLocal(
    type: 'user.task' | 'run.result' | 'run.error',
    payload: Record<string, unknown>
  ): void
  summarizeCurrentPage(): Promise<void>
  explainPickedElement(): Promise<void>
  copyPageArticle(): Promise<void>
  askAboutCurrentPage(): Promise<void>
}

async function runDiagnostics(): Promise<string[]> {
  const lines: string[] = []
  lines.push(`extension: ${chrome.runtime?.id ?? 'unknown'}`)
  try {
    const auth = await loadNewApiAuth()
    lines.push(`newapi.mode: ${auth.mode}`)
    lines.push(`newapi.loggedIn: ${isNewApiLoggedIn(auth)}`)
    lines.push(`newapi.portal: ${auth.portalBase || NEWAPI_PORTAL_BASE}`)
  } catch (error) {
    lines.push(`newapi: error — ${(error as Error).message}`)
  }
  try {
    const profiles = await loadModelProfiles()
    const active = getActiveModelProfile(profiles)
    lines.push(`model: ${active.name} (${active.model})`)
    lines.push(`baseURL: ${active.baseURL}`)
    lines.push(`apiKey: ${active.apiKey.trim() ? 'set' : 'missing'}`)
  } catch (error) {
    lines.push(`model: error — ${(error as Error).message}`)
  }
  try {
    const response = await fetch(`${NEWAPI_PORTAL_BASE.replace(/\/$/, '')}/api/plugin/meta`, {
      signal: AbortSignal.timeout(4000),
    })
    lines.push(`portal.meta: HTTP ${response.status}`)
  } catch (error) {
    lines.push(`portal.meta: ${(error as Error).message}`)
  }
  return lines
}

function resultBlock(title: string, body: string): string {
  return `\`\`\`\n${title}\n${body}\n\`\`\``
}

async function runBuiltinHandler(
  command: SlashCommandDef,
  args: string,
  deps: SlashRunnerDeps
): Promise<boolean> {
  switch (command.name) {
    case 'hello':
      deps.appendLocal('run.result', {
        text: resultBlock('hello', 'pong — NaviForge extension OK'),
      })
      return true
    case 'check': {
      const lines = await runDiagnostics()
      deps.appendLocal('run.result', {
        text: resultBlock('check', lines.join('\n')),
      })
      return true
    }
    case 'page':
      deps.setPageAskMode(true)
      if (args) deps.setTask(args)
      else await deps.askAboutCurrentPage()
      return true
    case 'summarize':
      if (args) deps.setTask(args)
      await deps.summarizeCurrentPage()
      return true
    case 'explain':
      if (args) deps.setTask(args)
      await deps.explainPickedElement()
      return true
    case 'copy':
      await deps.copyPageArticle()
      return true
    default:
      return false
  }
}

function runSkillExpand(command: SlashCommandDef, args: string, deps: SlashRunnerDeps): boolean {
  const skillId = command.skillId
  if (!skillId) return false
  const skill = findSkill(deps.enabledSkills, skillId)
  if (!skill) {
    deps.appendLocal('run.error', { message: `未知 Skill：${skillId}` })
    return true
  }
  const expanded = expandSkillSlashPayload(skill, args, {
    location: `skill://${skill.manifest.id}@${skill.manifest.version}`,
    baseDir: `skill://${skill.manifest.id}`,
  })
  deps.enqueueTask(expanded)
  return true
}

export function createSlashCommandRunner(deps: SlashRunnerDeps) {
  async function runSlashCommand(name: string, body: string): Promise<boolean> {
    const command = resolveSlashCommand(name, deps.registry)
    if (!command) return false
    const args = body.trim()
    deps.appendLocal('user.task', { text: formatSlashUserText(command, body) })
    deps.setTask('')

    if (command.kind === 'expand' && command.source === 'skill') {
      return runSkillExpand(command, args, deps)
    }
    if (command.kind === 'handler') {
      return runBuiltinHandler(command, args, deps)
    }
    deps.appendLocal('run.error', { message: `未实现的命令类型：${command.name}` })
    return true
  }

  return { runSlashCommand }
}
