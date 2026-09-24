import type { LlmConfig, QueuedTask } from '@naviforge/runtime'
import type { Skill } from '@naviforge/skill-runtime'

import { mergeInstalledSkills } from '../lib/settings'
import { BUNDLED_SKILLS } from '../skills/catalog'
import { createAgentStarter, type AgentStarterDeps } from './workspace-run'

/** Agent run policy + queue bridge — keeps workspace-composition thinner. */
export type WorkspaceRunWireDeps = Omit<AgentStarterDeps, 'enabledSkills'> & {
  customSkills: Skill[]
  disabledSkills: string[]
}

export function createWorkspaceRunWire(deps: WorkspaceRunWireDeps): (taskItem: QueuedTask) => Promise<void> {
  const enabledSkills = mergeInstalledSkills(BUNDLED_SKILLS, deps.customSkills).filter(
    (skill) => !deps.disabledSkills.includes(skill.manifest.id)
  )
  return createAgentStarter({ ...deps, enabledSkills }).startRun
}

export type { LlmConfig }
