export type { TaskScope } from './task-scope.js'
export { resolveTaskScope } from './task-scope.js'
export type { AskUserDecision, HitlPolicyMode } from './hitl-policy.js'
export { evaluateAskUser } from './hitl-policy.js'
export { detectUrlDrift, isUrlMutatingTool, urlsEquivalentForScope } from './url-drift.js'
export { isLikelyNavigationClick, snapshotLineForIndex } from './navigation-guard.js'
export {
  SENSITIVE_TOOLS,
  hasRecentSensitiveApproval,
  sensitiveConfirmQuestion,
} from './sensitive-tools.js'
