import assert from 'node:assert/strict'

import {
  cueAt,
  isZhLang,
  parseBilibiliJson,
  parseVttTime,
  parseWebVtt,
  parseYoutubeJson3,
  pickCaptionTrack,
  translateCues,
} from './video-subtitles'

assert.equal(parseVttTime('00:00:01.500'), 1.5)
assert.equal(parseVttTime('01:02.000'), 62)
assert.equal(isZhLang('zh-CN'), true)
assert.equal(isZhLang('en'), false)
assert.equal(isZhLang('ai-zh'), true)

const vtt = parseWebVtt(`WEBVTT

00:00:01.000 --> 00:00:03.000
Hello

00:00:03.000 --> 00:00:05.000
<c>World</c>
`)
assert.equal(vtt.length, 2)
assert.equal(vtt[0]?.text, 'Hello')
assert.equal(vtt[1]?.text, 'World')

const yt = parseYoutubeJson3({
  events: [
    { tStartMs: 1000, dDurationMs: 2000, segs: [{ utf8: 'Hello' }, { utf8: ' there' }] },
    { tStartMs: 4000 },
  ],
})
assert.equal(yt.length, 1)
assert.equal(yt[0]?.text, 'Hello there')
assert.equal(yt[0]?.start, 1)
assert.equal(yt[0]?.end, 3)

const bili = parseBilibiliJson(JSON.stringify({ body: [{ from: 1, to: 3, content: '你好' }] }))
assert.equal(bili[0]?.text, '你好')

const picked = pickCaptionTrack([
  { lang: 'zh-CN', label: '中文', url: 'https://z' },
  { lang: 'en', label: 'English', url: 'https://e' },
  { lang: 'en', label: 'English (auto)', kind: 'asr', url: 'https://a' },
])
assert.equal(picked?.url, 'https://e')

const overlay = [
  { start: 0, end: 1, text: 'a', translated: '甲' },
  { start: 2, end: 4, text: 'b', translated: '乙' },
]
assert.equal(cueAt(overlay, 0.5)?.translated, '甲')
assert.equal(cueAt(overlay, 1.5), null)
assert.equal(cueAt(overlay, 3)?.translated, '乙')

const passthrough = await translateCues([{ start: 0, end: 1, text: '已经是中文' }], 'zh-CN')
assert.equal(passthrough[0]?.translated, '已经是中文')

console.log('video-subtitles self-check ok')
