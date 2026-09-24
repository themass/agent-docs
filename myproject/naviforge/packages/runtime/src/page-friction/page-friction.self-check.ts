import assert from 'node:assert/strict'

import { classifyTextFriction, parsePageFrictionPayload } from './detect.js'
import { frictionHitlQuestion, frictionGuidanceNotes, shouldAutoHitl } from './policy.js'
import { resetPageThrottleForTests } from './throttle.js'

const sample = parsePageFrictionPayload({
  url: 'https://x.test/login',
  title: 'Login',
  kinds: ['login', 'captcha'],
  blocking: true,
  cookieBanner: false,
})
assert.ok(sample?.kinds.includes('login'))
assert.ok(shouldAutoHitl(sample!))
assert.ok(frictionHitlQuestion(sample!)?.includes('验证'))

const textKinds = classifyTextFriction('Too many requests — rate limit 429')
assert.ok(textKinds.includes('rate_limit'))

const wenkuMarketing = classifyTextFriction('开通VIP 享海量文档 单篇下载 最低仅需¥2.00')
assert.ok(wenkuMarketing.includes('paywall'))
assert.ok(!wenkuMarketing.includes('login'))

const wenkuHard = classifyTextFriction('请登录后下载本文档')
assert.ok(wenkuHard.includes('paywall'))

const notes = frictionGuidanceNotes(sample!)
assert.ok(notes.some((n) => n.includes('system_captcha_wait')))

resetPageThrottleForTests()

console.log('page-friction self-check ok')
