import assert from 'node:assert/strict'

import {
  inferJsonSchema,
  shouldCaptureSniffEvent,
  sniffApiKey,
  urlMatchesOrigin,
} from './sniff-ingest'

assert(sniffApiKey('GET', 'https://api.example.com/videos/123?page=2') === 'GET api.example.com/videos/{id}')
assert(urlMatchesOrigin('https://www.bilibili.com/x', 'bilibili.com'))
assert(urlMatchesOrigin('https://www.bilibili.com/x', 'www.bilibili.com'))
assert(!urlMatchesOrigin('https://other.com/x', 'bilibili.com'))

const schema = inferJsonSchema(JSON.stringify({ title: 'a', count: 3, tags: [] }))
const properties = schema?.properties as Record<string, string> | undefined
assert(properties?.title === 'string')
assert(properties?.count === 'number')
assert(properties?.tags === 'array')

assert(
  shouldCaptureSniffEvent(
    { id: '1', method: 'GET', url: 'https://api.bilibili.com/x', ts: 0, mimeType: 'application/json' },
    'bilibili.com'
  )
)
assert(
  !shouldCaptureSniffEvent(
    { id: '2', method: 'GET', url: 'https://api.bilibili.com/x', ts: 0, mimeType: 'image/png' },
    'bilibili.com'
  )
)

console.log('sniff-ingest self-check ok')
