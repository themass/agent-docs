import assert from 'node:assert/strict'

import {
  classifyPageState,
  extractIndexedMediaCards,
  enrichItemsWithSnapshotFeed,
  formatPageState,
  looksLikeLoginUrl,
  shouldSkipLoginLinkRead,
} from './page-state.js'

assert.equal(looksLikeLoginUrl('https://axx.example/login'), true)
assert.equal(looksLikeLoginUrl('https://axx.example/home'), false)

const login = classifyPageState({
  url: 'https://axx.example/login',
  title: '登录',
  login: true,
  blocking: true,
  items: [{ title: '忘记密码', url: 'https://axx.example/forget' }],
})
assert.equal(login.role, 'login')
assert.equal(login.blocked, true)
assert.equal(login.items.length, 0)
assert.match(formatPageState(login), /PAGE STATE:/)
assert.match(formatPageState(login), /role: login/)
assert.match(formatPageState(login), /login wall/)

const list = classifyPageState({
  url: 'https://axx.example/home',
  title: 'home',
  login: false,
  blocking: false,
  items: [
    { title: 'a', url: 'https://axx.example/v/1' },
    { title: 'b', url: 'https://axx.example/v/2' },
    { title: 'c', url: 'https://axx.example/v/3' },
  ],
})
assert.equal(list.role, 'list')
assert.equal(list.items.length, 3)

const spaSnap = {
  header: '',
  content: '*[12] 第一集\n*[13] 第二集\n',
  footer: '',
}
const spaItems = enrichItemsWithSnapshotFeed([], spaSnap)
assert.ok(spaItems.length >= 2)
const spaState = classifyPageState({
  url: 'https://example.test/x',
  title: 'x',
  login: false,
  blocking: false,
  items: spaItems,
})
assert.equal(spaState.role, 'list')
assert.match(formatPageState(spaState), /feed_clicks:/)

const mediaCards = extractIndexedMediaCards({
  header: '',
  content: [
    '*[23]<img />',
    '*[24]<img />',
    'HD',
    '0:28:55',
    '首页视频标题：从零实现一个浏览器 Agent',
    '站点官方 · 17.0万次观看',
    '*[25]<img />',
  ].join('\n'),
  footer: '',
})
assert.equal(mediaCards[0]?.clickIndex, 24)
assert.match(mediaCards[0]?.title ?? '', /浏览器 Agent/)

assert.equal(
  shouldSkipLoginLinkRead({
    tool: 'dom_read',
    args: { mode: 'dom', kind: 'links' },
    page: login,
    snapUrl: login.url,
  }),
  true
)
assert.equal(
  shouldSkipLoginLinkRead({
    tool: 'dom_read',
    args: { mode: 'body' },
    page: login,
    snapUrl: login.url,
  }),
  false
)
assert.equal(
  shouldSkipLoginLinkRead({
    tool: 'dom_navigate',
    args: { mode: 'dom' },
    page: login,
    snapUrl: login.url,
  }),
  false
)

console.log('page-state.self-check ok')
