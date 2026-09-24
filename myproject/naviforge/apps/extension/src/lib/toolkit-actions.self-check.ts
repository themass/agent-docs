import assert from 'node:assert/strict'

import { buildExtractJsonl, describeSavedShot, flashCommandFeedback, googleTranslateUrl, isToolkitPageUrl, preferLiveWebTab, snapshotCurrentWebTab } from './toolkit-actions'

assert(!isToolkitPageUrl('chrome://settings'), 'chrome pages blocked')
assert(!isToolkitPageUrl('chrome-extension://abc/workspace.html'), 'extension pages blocked')
assert(!isToolkitPageUrl(undefined), 'missing url blocked')
assert(isToolkitPageUrl('https://www.bilibili.com'), 'https allowed')

assert.equal(
  preferLiveWebTab({ id: 2, url: 'https://github.com/x' }, { id: 1, url: 'https://old.example' }, [])?.id,
  2,
  'the page you are looking at wins over a stale pin'
)
assert.equal(
  preferLiveWebTab({ id: 9, url: 'chrome-extension://abc/options.html' }, { id: 1, url: 'https://old.example' }, [])?.id,
  1,
  'control center focused → fall back to pin'
)
assert.equal(
  preferLiveWebTab({ id: 9, url: 'chrome-extension://abc/options.html' }, undefined, [
    { id: 3, url: 'https://github.com/x' },
  ])?.id,
  3,
  'no pin → most recent web tab'
)

const translate = googleTranslateUrl('https://example.com/path?q=1')
assert(translate.includes('translate.google.com'), 'google translate host')
assert(translate.includes(encodeURIComponent('https://example.com/path?q=1')), 'page url encoded')

const jsonl = buildExtractJsonl([
  { title: 'A', url: 'https://a', fields: { views: '1k' } },
  { title: 'B' },
])
assert(jsonl.split('\n').length === 2, 'jsonl line count')
assert(JSON.parse(jsonl.split('\n')[0]!).views === '1k', 'fields merged')

assert.equal(typeof flashCommandFeedback, 'function', 'command feedback helper exported')
assert.equal(typeof snapshotCurrentWebTab, 'function', 'current page snapshot is exported')

const workspaceSave = describeSavedShot('shots/a.png', '/Users/me/NaviForge')
assert.equal(workspaceSave.title, '截图已保存')
assert.equal(workspaceSave.location, '/Users/me/NaviForge/shots/a.png')
assert.equal(workspaceSave.inDownloads, false)
assert.match(workspaceSave.hint, /打开工作台/)

const downloadSave = describeSavedShot('Downloads/NaviForge/shots/a.png', '/Users/me/NaviForge')
assert.equal(downloadSave.location, 'Downloads/NaviForge/shots/a.png')
assert.equal(downloadSave.inDownloads, true)
assert.match(downloadSave.hint, /下载目录/)

console.log('toolkit-actions self-check ok')
