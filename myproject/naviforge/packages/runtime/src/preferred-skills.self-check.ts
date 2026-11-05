import assert from 'node:assert/strict'

import { preferredSkillIdsForTask } from './preferred-skills.js'
import { createRuntimeState, reduceRuntimeState } from './runtime-state.js'
import { buildTaskContract } from './task-contract.js'

assert.deepEqual(preferredSkillIdsForTask('分析这个视频的 m3u8 播放地址'), ['media-harvest'])
assert.deepEqual(preferredSkillIdsForTask('帮我总结本页'), ['observe'])
assert.deepEqual(preferredSkillIdsForTask('对比两个 github 项目区别'), ['research'])
assert.ok(preferredSkillIdsForTask('生成 python 抓取脚本').includes('persist'))

const state = createRuntimeState(buildTaskContract('test'))
const marked = reduceRuntimeState(state, { type: 'progress', kind: 'state', replanRequired: true })
assert.equal(marked.progress.replanRequired, true)
const cleared = reduceRuntimeState(marked, {
  type: 'evidence',
  evidence: { kind: 'page', source: 'test', summary: 'ok', confidence: 1 },
})
assert.equal(cleared.progress.replanRequired, false)

console.log('preferred-skills.self-check ok')
