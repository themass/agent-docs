import type { TaskScope } from './task-scope.js'

export type HitlPolicyMode = 'strict' | 'balanced' | 'permissive'

export type AskUserDecision = {
  allow: boolean
  reason: string
}

const NAVIGATION_QUESTION =
  /navigate|go to|open\b|跳转|前往|热门|排行榜|which page|哪一页|去哪个|要不要打开/i
const CLARIFICATION_QUESTION = /clarif|confirm|which\b|what do you mean|不确定|是否|要不要/i

const CAPTCHA_QUESTION =
  /captcha|验证码|人机|verify you are human|security check|滑动验证|点选/i

/** Configurable ask_user gate: scope + question topic. */
export function evaluateAskUser(
  question: string,
  scope: TaskScope,
  mode: HitlPolicyMode = 'balanced'
): AskUserDecision {
  if (mode === 'permissive') {
    return { allow: true, reason: '' }
  }
  const q = question.trim()
  // CAPTCHA / security checks always allowed — user must complete in browser.
  if (CAPTCHA_QUESTION.test(q)) {
    return { allow: true, reason: '' }
  }
  if (NAVIGATION_QUESTION.test(q) && scope.navigation === 'forbidden') {
    return {
      allow: false,
      reason: 'question requests navigation on a stay-on-page task — use steer instead',
    }
  }
  if (mode === 'strict' && CLARIFICATION_QUESTION.test(q)) {
    return {
      allow: false,
      reason: 'strict HITL mode blocks clarification questions — act or use steer',
    }
  }
  return { allow: true, reason: '' }
}
