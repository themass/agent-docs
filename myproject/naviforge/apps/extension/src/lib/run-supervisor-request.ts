import type { LlmConfig } from '@naviforge/runtime'
import type { AgentCapabilityGates } from '@naviforge/shared'
import type { QueuedTask, ThreadContext } from '@naviforge/runtime'

export type BackgroundRunRequest = Pick<
  AgentCapabilityGates,
  'networkEnabled' | 'captureNetworkBodies' | 'allowDomInject' | 'allowNetworkIntercept' | 'visionEnabled'
> & {
  id: ReturnType<typeof crypto.randomUUID>
  sessionId?: string
  task: string
  taskId?: string
  tabId: number
  llm: LlmConfig
  skills?: string[]
  skillRegistry?: Array<{
    id: string
    version: string
    description: string
    instructions: string
    tools?: string[]
    files?: string[]
  }>
  skillGuidance?: string
  threadContext?: ThreadContext
  allowedTools?: string[]
  maxSteps: number
  sameFailureLimit?: number
  runTimeoutMs?: number
  runTokenBudget?: number
  maxInputTokens?: number
  intakeMode?: 'off' | 'auto' | 'always'
  hitlPolicy: 'strict' | 'balanced' | 'permissive'
  rollbackUrlDrift: boolean
  imageDataUrl?: string
  imageLabel?: string
  vision?: boolean
  followUpQueue?: QueuedTask[]
}

export function isValidBackgroundRunRequest(request: unknown): request is BackgroundRunRequest {
  if (!request || typeof request !== 'object') return false
  const r = request as Record<string, unknown>
  const llm = r.llm
  return (
    typeof r.id === 'string' &&
    typeof r.task === 'string' &&
    r.task.length > 0 &&
    typeof r.tabId === 'number' &&
    typeof llm === 'object' &&
    llm !== null
  )
}
