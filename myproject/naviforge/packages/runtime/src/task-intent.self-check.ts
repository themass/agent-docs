import assert from 'node:assert/strict'

import { intentGuidanceNotes, intentPreflightSkill, resolveTaskIntent } from './task-intent.js'

assert.equal(resolveTaskIntent('帮我下载这个文档'), 'page_download')
assert.equal(resolveTaskIntent('分析这个视频的 m3u8 播放地址'), 'media_extract')
assert.equal(intentPreflightSkill('media_extract'), 'media-extract')
assert.equal(resolveTaskIntent('破解页面加密'), 'denied')
assert.ok(intentGuidanceNotes('page_download').some((line) => line.includes('dom_click')))
assert.equal(intentPreflightSkill('page_download'), 'document-download')

console.log('task-intent self-check ok')
