import assert from 'node:assert/strict'

import {
  coordinateRecovery,
  evaluateCompletion,
  needsNetworkCollaboration,
  NETWORK_COLLABORATION_QUESTION,
} from './completion-coordinator.js'
import { buildTaskContract } from './task-contract.js'
import { createRuntimeState, reduceRuntimeState } from './runtime-state.js'
import { evaluateEvidence } from './evaluator.js'

const mediaContract = buildTaskContract('抓取当前网页首页视频的名称和原地址')
assert.equal(mediaContract.capabilities.network, 'required')

const blocked = evaluateCompletion({
  deliverable: 'media',
  taskContract: mediaContract,
  evidence: [],
  scriptSaved: false,
  subtaskEvidenceReady: false,
  systemDoneResult: '播放源：https://cdn.example.test/fake.m3u8',
})
assert.equal(blocked.allow, false)
if (!blocked.allow) {
  assert.equal(blocked.code, 'deliverable_verify')
  assert.equal(blocked.recovery.strategy, 'reobserve_and_replan')
}

let state = createRuntimeState(mediaContract)
state = reduceRuntimeState(state, {
  type: 'evidence',
  evidence: {
    kind: 'page',
    source: 'page_state',
    summary: 'media list',
    confidence: 0.9,
  },
})
state = reduceRuntimeState(state, {
  type: 'evidence',
  evidence: {
    kind: 'dom',
    source: 'media_title',
    summary: 'demo title',
    confidence: 0.9,
  },
})
state = reduceRuntimeState(state, {
  type: 'evidence',
  evidence: {
    kind: 'network',
    source: 'network_media',
    summary: 'https://cdn.example.test/master.m3u8',
    confidence: 0.95,
  },
})
const evaluation = evaluateEvidence(mediaContract, state.evidence.records)
assert.equal(evaluation.status, 'complete', `missing: ${evaluation.missing.join(', ')}`)

const permitted = evaluateCompletion({
  deliverable: 'media',
  taskContract: mediaContract,
  evidence: state.evidence.records,
  scriptSaved: false,
  subtaskEvidenceReady: false,
  systemDoneResult: 'ok',
})
assert.equal(permitted.allow, true)

const scriptBlocked = evaluateCompletion({
  deliverable: 'script',
  taskContract: buildTaskContract('生成 python 脚本抓取分类'),
  evidence: [],
  scriptSaved: false,
  subtaskEvidenceReady: false,
  systemDoneResult: 'done',
})
assert.equal(scriptBlocked.allow, false)

assert.equal(
  needsNetworkCollaboration({ networkRequired: true, networkUnavailable: true }),
  true
)
const collab = coordinateRecovery({
  evaluation: { status: 'needs_recovery', missing: ['media_url'], evidence: [] },
  replanRequired: false,
  networkRequired: true,
  networkUnavailable: true,
})
assert.equal(collab?.strategy, 'ask_user')
assert.match(collab?.diagnostic ?? '', /Network/)
assert.match(NETWORK_COLLABORATION_QUESTION, /debugger/)

console.log('completion-coordinator.self-check ok')
