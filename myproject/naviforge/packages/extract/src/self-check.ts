import { extractPageList } from './index.js'

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg)
}

const items = extractPageList({
  snapshotContent: '[1] link "Video A"\n[2] link "Video B"\n[3] button "Go"',
  mediaHints: [{ url: 'https://cdn/x.m3u8', kind: 'hls' }],
})
assert(items.length >= 2 && items[0].mediaUrls.length === 1, 'extract merge')

console.log('extract self-check ok')
