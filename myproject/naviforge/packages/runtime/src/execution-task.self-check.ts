import assert from 'node:assert/strict'

import { lockDeliverable, resolveDeliverable } from './deliverable.js'
import { shouldEnableNetworkPlane, taskRequiresNetworkPlane } from './execution-task.js'

const SCRIPT_ANCHOR =
  '分析这个网站的 视频列表，给我生成一个python 脚本，抓取每个分类下的第一页。\n页码可以定义多少页，默认值为1'

const DRIFT_SUMMARY = '分析当前页面中的视频，提取视频名称和源地址。'

assert.equal(resolveDeliverable(SCRIPT_ANCHOR), 'script')
assert.equal(lockDeliverable(SCRIPT_ANCHOR, DRIFT_SUMMARY), 'script')

assert.equal(taskRequiresNetworkPlane(SCRIPT_ANCHOR), true)
assert.equal(taskRequiresNetworkPlane('分析当前页面的视频的名称和源地址'), true)
assert.equal(taskRequiresNetworkPlane('总结本页 readme'), false)
assert.equal(taskRequiresNetworkPlane('继续'), false)
assert.equal(
  shouldEnableNetworkPlane('继续', '分析当前页面的视频的名称和源地址'),
  true,
  'continuation inherits session anchor for network plane'
)

console.log('execution-task self-check ok')
