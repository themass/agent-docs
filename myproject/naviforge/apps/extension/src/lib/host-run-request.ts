import { preferredSkillIdsForTask, type LlmConfig } from '@naviforge/runtime'
import { formatSkillGuidance, routeSkills, type Skill } from '@naviforge/skill-runtime'
import { applyAgentCapabilityGates, DEFAULT_AGENT_CAPABILITY_GATES } from '@naviforge/shared'

import { DEFAULT_PRIVACY, DEFAULT_MAX_INPUT_TOKENS, normalizeMaxAgentSteps } from './settings'
import type { BackgroundRunRequest } from './run-supervisor-request'

export function buildHostPollRunRequest(opts: {
  hostTaskId: string
  instruction: string
  tabId: number
  llm: LlmConfig
  useNetwork: boolean
  privacy: typeof DEFAULT_PRIVACY
  skills: Skill[]
}): BackgroundRunRequest {
  const matched = routeSkills(opts.instruction, opts.skills, 1, {
    preferredSkillIds: preferredSkillIdsForTask(opts.instruction),
  })
  const gates = applyAgentCapabilityGates(DEFAULT_AGENT_CAPABILITY_GATES, {
    networkEnabled: opts.useNetwork,
    captureNetworkBodies: false,
    allowDomInject: opts.privacy.allowDomInject,
    allowNetworkIntercept: opts.privacy.allowNetworkIntercept && opts.useNetwork,
    visionEnabled: false,
  })
  // Soft skill guidance only — do not shrink allowedTools from a single route hit.
  return {
    id: crypto.randomUUID(),
    task: opts.instruction,
    taskId: opts.hostTaskId,
    tabId: opts.tabId,
    llm: opts.llm,
    skillGuidance: formatSkillGuidance(opts.skills, { hints: matched }) || undefined,
    allowedTools: undefined,
    hitlPolicy: 'balanced',
    rollbackUrlDrift: true,
    maxSteps: normalizeMaxAgentSteps(opts.privacy.maxAgentSteps),
    maxInputTokens: opts.privacy.maxInputTokens ?? DEFAULT_MAX_INPUT_TOKENS,
    ...gates,
  }
}
