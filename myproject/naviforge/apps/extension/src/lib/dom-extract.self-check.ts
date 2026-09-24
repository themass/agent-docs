import assert from 'node:assert/strict'

import { extractDomFromEntries } from './dom-extract.js'

type MockEl = Element & { _rect: { top: number; left: number; width: number; height: number }; _tag: string; _text: string; _href?: string }

function mockEl(
  tag: string,
  text: string,
  rect: { top: number; left?: number; width?: number; height?: number },
  href?: string
): MockEl {
  const box = { top: rect.top, left: rect.left ?? 0, width: rect.width ?? 200, height: rect.height ?? 40 }
  return {
    tagName: tag.toUpperCase(),
    _tag: tag,
    _text: text,
    _href: href,
    _rect: box,
    getAttribute(name: string) {
      if (name === 'href') return href ?? null
      return null
    },
    getBoundingClientRect() {
      const { top, left, width, height } = box
      return { top, left, width, height, bottom: top + height, right: left + width }
    },
    textContent: text,
    querySelector: () => null,
    closest: () => null,
    contains: () => false,
  } as unknown as MockEl
}

const entries = [
  { index: 1, element: mockEl('a', 'Demo Video 1', { top: 120 }, 'https://example.com/1') },
  { index: 2, element: mockEl('button', 'Go', { top: 40 }) },
  { index: 3, element: mockEl('a', 'Demo Video 2', { top: 220 }, 'https://example.com/2') },
]

const all = extractDomFromEntries(entries, { url: 'https://x', title: 't', kind: 'all' })
assert(all.links.length >= 2, 'links extracted')
assert(all.buttons.length >= 1, 'buttons extracted')

const feeds = extractDomFromEntries(entries, { url: 'https://x', title: 't', kind: 'feeds' })
assert(feeds.feeds.length >= 1, 'feed picks')

const bilibili = extractDomFromEntries(
  [
    { index: 1, element: mockEl('a', '真实视频标题', { top: 120 }, '/video/BV1H7M26dEEA') },
    { index: 2, element: mockEl('a', '活动链接', { top: 180 }, '/blackboard/event.html') },
  ],
  { url: 'https://www.bilibili.com/c/knowledge/', title: 'bilibili', kind: 'feeds' }
)
assert.deepEqual(bilibili.feeds.map((item) => item.title), ['真实视频标题'], 'Bilibili feeds use BV videos only')

console.log('dom-extract self-check ok')
