/** Shared run limits for UI requests and runtime agent loop. */
export type AgentRunLimits = {
  maxSteps: number
  sameFailureLimit?: number
  runTimeoutMs?: number
  runTokenBudget?: number
  maxInputTokens?: number
}

export const DEFAULT_AGENT_RUN_LIMITS: AgentRunLimits = {
  maxSteps: 40,
  sameFailureLimit: 3,
  runTimeoutMs: 0,
  runTokenBudget: 0,
  maxInputTokens: 120_000,
}
