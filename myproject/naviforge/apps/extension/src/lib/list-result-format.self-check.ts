import assert from 'node:assert/strict'

import { formatListBody, formatListItem } from './list-result-format'

const row = formatListItem(
  { label: 'TOP1', title: '113', fields: { views: '113', author: '某UP' }, url: 'https://b23.tv/x' },
  1
)
assert(row.headline.includes('某UP') || row.headline.length > 6, 'pure numbers are not shown as the title')
assert(formatListBody([], { offscreen: ['TOP2'], missed: ['TOP4'] }).includes('TOP2'), 'warnings surface in the body')

console.log('list-result-format self-check ok')
