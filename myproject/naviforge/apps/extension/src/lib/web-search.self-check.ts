import assert from 'node:assert/strict'

import { readWebSearchSettings } from './settings'
import { parseBraveWebResults, parseTavilyWebResults } from './web-search'

assert.deepEqual(parseBraveWebResults(null), [])
assert.deepEqual(parseBraveWebResults({}), [])
assert.deepEqual(
  parseBraveWebResults({
    web: {
      results: [
        { title: 'NaviForge', url: 'https://example.com/a', description: 'browser agent' },
        { title: 'Skip', url: '  ', description: 'no url' },
        { url: 'https://example.com/b' },
      ],
    },
  }),
  [
    { title: 'NaviForge', url: 'https://example.com/a', snippet: 'browser agent' },
    { title: 'https://example.com/b', url: 'https://example.com/b', snippet: '' },
  ]
)
assert.equal(
  parseBraveWebResults(
    {
      web: {
        results: [
          { title: '1', url: 'https://a' },
          { title: '2', url: 'https://b' },
          { title: '3', url: 'https://c' },
        ],
      },
    },
    2
  ).length,
  2
)

assert.deepEqual(parseTavilyWebResults(null), [])
assert.deepEqual(
  parseTavilyWebResults({
    results: [
      { title: 'Tavily', url: 'https://example.com/t', content: 'ai search' },
      { title: 'Skip', url: '  ', content: 'no url' },
      { url: 'https://example.com/u' },
    ],
  }),
  [
    { title: 'Tavily', url: 'https://example.com/t', snippet: 'ai search' },
    { title: 'https://example.com/u', url: 'https://example.com/u', snippet: '' },
  ]
)

assert.deepEqual(readWebSearchSettings(undefined), {
  provider: 'brave',
  braveApiKey: '',
  tavilyApiKey: '',
})
assert.deepEqual(readWebSearchSettings({ apiKey: 'legacy-brave' }), {
  provider: 'brave',
  braveApiKey: 'legacy-brave',
  tavilyApiKey: '',
})
assert.deepEqual(
  readWebSearchSettings({
    provider: 'tavily',
    braveApiKey: 'b',
    tavilyApiKey: 't',
  }),
  { provider: 'tavily', braveApiKey: 'b', tavilyApiKey: 't' }
)

console.log('web-search self-check ok')
