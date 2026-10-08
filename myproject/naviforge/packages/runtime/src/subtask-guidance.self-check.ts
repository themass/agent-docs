import assert from 'node:assert/strict'

import { briefFromSubtask, MAX_PARALLEL_SUBTASKS, normalizeSpawnBriefs } from './subtask-guidance.js'

assert.equal(MAX_PARALLEL_SUBTASKS, 3)

const structured = normalizeSpawnBriefs({
  subtasks: [
    {
      title: 'Product 101',
      prompt: 'Extract name, price; return JSON {name,price}.',
      urls: ['https://shop.example/p/101'],
      mode: 'tab',
    },
  ],
})
assert.ok(!('error' in structured))
assert.ok(structured.briefs[0]?.includes('tabs action=open'))
assert.ok(structured.briefs[0]?.includes('Product 101'))

const legacy = normalizeSpawnBriefs({ briefs: ['fetch_text https://a.com/x; system_done'] })
assert.ok(!('error' in legacy))

const tooMany = normalizeSpawnBriefs({ subtasks: [{ title: 'a', prompt: 'p' }, { title: 'b', prompt: 'p' }, { title: 'c', prompt: 'p' }, { title: 'd', prompt: 'p' }] })
assert.ok('error' in tooMany)

const fetchBrief = briefFromSubtask({
  title: 'Docs',
  prompt: 'Return title per URL.',
  urls: ['https://docs.example/a', 'https://docs.example/b'],
  mode: 'fetch',
})
assert.ok(fetchBrief.includes('fetch_text'))

console.log('subtask-guidance self-check ok')
