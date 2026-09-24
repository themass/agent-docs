import assert from 'node:assert/strict'

import { friendlyCaptureError, slicePlan, type PageMetrics } from './capture-full-page.js'

const metrics: PageMetrics = {
  scrollY: 0,
  innerHeight: 720,
  innerWidth: 1280,
  scrollHeight: 2000,
  devicePixelRatio: 1,
}

const plan = slicePlan(metrics, 80)
assert.ok(plan.length >= 3, 'tall page needs multiple slices')
assert.equal(plan[0], 0)
assert.ok(plan.at(-1)! >= metrics.scrollHeight - metrics.innerHeight)

assert.equal(
  friendlyCaptureError('This request exceeds the MAX_CAPTURE_VISIBLE_TAB_CALLS_PER_SECOND quota.'),
  '截图太快被浏览器拦住了，请等一秒再试'
)
assert.match(friendlyCaptureError('The activeTab permission is not in effect'), /前台/)
assert.match(friendlyCaptureError('The tab is not visible'), /前台/)
assert.match(friendlyCaptureError('No tab with id: 9'), /关掉/)
assert.equal(friendlyCaptureError('tab not found'), 'tab not found')

console.log('capture-full-page self-check ok')
