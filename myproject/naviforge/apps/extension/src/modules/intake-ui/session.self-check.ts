import assert from 'node:assert/strict'
import type { TraceRecord } from '@naviforge/session'

import { latestIntakeSession } from './session.js'

const base = {
  schema: 1 as const,
  channel: 'conversation' as const,
  at: 1,
}

const priorAnswer: TraceRecord = {
  ...base,
  id: 'ans-old',
  runId: 'run-a',
  type: 'intake.answer',
  payload: {
    round: 0,
    questions: [{ id: 'q1', prompt: 'old?', kind: 'text' }],
    answers: { _freeText: 'hello' },
  },
}

const newQuestion: TraceRecord = {
  ...base,
  id: 'q-new',
  at: 2,
  runId: 'run-b',
  type: 'intake.question',
  payload: {
    round: 0,
    questions: [{ id: 'task_type', prompt: '您希望完成什么任务？', kind: 'single', required: true }],
  },
}

assert.equal(
  latestIntakeSession([priorAnswer, newQuestion])?.questions[0]?.prompt,
  '您希望完成什么任务？',
  'prior run intake.answer must not satisfy a new run question'
)

const answered: TraceRecord = {
  ...base,
  id: 'ans-new',
  at: 3,
  runId: 'run-b',
  type: 'intake.answer',
  payload: {
    round: 0,
    questions: newQuestion.payload.questions,
    answers: { task_type: 'other' },
  },
}

assert.equal(latestIntakeSession([priorAnswer, newQuestion, answered]), null, 'same-run answer closes intake')

console.log('intake-ui session self-check ok')
