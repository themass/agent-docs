import assert from 'node:assert/strict'

import { composeIntakeSystemPrompt, compileIntakeUserPrompt } from './prompt.js'
import {
  formatIntakeConstraints,
  normalizeClarificationQuestions,
  parseIntakeAnswerJson,
  shouldSkipIntake,
} from './protocol.js'

assert.equal(shouldSkipIntake('', 'auto'), true)
assert.equal(shouldSkipIntake('hello', 'auto'), false, 'auto enters intake; model judges')
assert.equal(shouldSkipIntake('总结当前页面', 'auto'), false)
assert.equal(shouldSkipIntake('anything', 'off'), true)
assert.equal(shouldSkipIntake('anything', 'always'), false)

assert.ok(composeIntakeSystemPrompt('KERNEL', 'auto').includes('智能判断'))
assert.ok(composeIntakeSystemPrompt('KERNEL', 'always').includes('必经确认'))

const questions = normalizeClarificationQuestions([
  {
    id: 'scope',
    prompt: '范围？',
    kind: 'single',
    options: [
      { id: 'page', label: '仅当前页' },
      { id: 'web', label: '全网搜索' },
    ],
  },
])
assert.equal(questions.length, 1)

const answers = parseIntakeAnswerJson('{"scope":"page"}')
assert.deepEqual(answers, { scope: 'page' })
const lines = formatIntakeConstraints(questions, answers!)
assert.ok(lines[0]?.includes('仅当前页'))

const intakeUser = compileIntakeUserPrompt('继续', [], {
  memory: 'GOAL: list August projects',
  conversation: 'user: https://github.com/foo\nerror: timeout',
})
assert.ok(intakeUser.includes('THREAD'), 'intake sees cross-run thread block')
assert.ok(intakeUser.includes('timeout'), 'intake thread includes prior error')

console.log('intake self-check ok')
