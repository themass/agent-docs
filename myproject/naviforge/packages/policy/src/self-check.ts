import { resolveTaskScope } from './task-scope.js'
import { detectUrlDrift } from './url-drift.js'
import { evaluateAskUser } from './hitl-policy.js'
import {
  hasRecentSensitiveApproval,
  sensitiveConfirmQuestion,
  SENSITIVE_TOOLS,
} from './sensitive-tools.js'

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg)
}

const scope = resolveTaskScope('找出当前页面的top4')
assert(scope.navigation === 'forbidden', 'scope')
assert(!evaluateAskUser('navigate to 热门', scope).allow, 'hitl blocks nav question')
assert(evaluateAskUser('请完成验证码', scope).allow, 'hitl allows captcha on scoped task')
assert(evaluateAskUser('需要登录吗？', scope).allow, 'hitl allows clarification on scoped task')
assert(detectUrlDrift('https://a.com/1', 'https://a.com/2', scope).drifted, 'drift')
assert(SENSITIVE_TOOLS.has('dom_upload'), 'upload is sensitive')
assert(sensitiveConfirmQuestion('dom_upload', { filename: 'a.csv' })?.includes('a.csv'), 'upload question')
assert(
  hasRecentSensitiveApproval(['USER ANSWER: 确认上传']),
  'recent approval detected'
)
assert(
  resolveTaskScope('有没有同类型的项目').navigation === 'allowed',
  'similar-project ask allows navigation'
)

console.log('policy self-check ok')
