import type { DomSnapshot } from '@naviforge/dom-plane'

import { compactSnapshotForPrompt, filterSnapshotLinesByIndex, isFullPageSnapshotHeader, snapshotPromptBudget, snapshotTruncationHint } from './compact.js'
import { formatMediaHints, mediaHintsFromUrls } from '@naviforge/media-plane'
import { formatPageSignalsForPrompt, minePageSignals } from './page-signals.js'

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg)
}

const snap: DomSnapshot = {
  revision: 1,
  url: 'http://localhost/test',
  title: 'Test',
  header: 'header',
  content: Array.from({ length: 100 }, (_, index) => `[${index}] link "Item ${index}"`).join('\n'),
  footer: 'footer',
}

assert(compactSnapshotForPrompt(snap).content.includes('more lines'), 'compact truncates')
assert(
  compactSnapshotForPrompt({ ...snap, header: 'Interactive (full page):' }).content.includes('dom_read'),
  'full page compact hints dom_read'
)
assert(isFullPageSnapshotHeader('(full page):'), 'detect full page header')
assert(snapshotTruncationHint('x').includes('scroll'), 'viewport hint')
assert(
  compactSnapshotForPrompt({ ...snap, mode: 'compact' }).content.split('\n').length <= 42,
  'compact mode uses a tighter line budget'
)
assert(
  compactSnapshotForPrompt({ ...snap, mode: 'full' }).content.includes('[90]'),
  'full mode keeps more snapshot lines'
)
assert(
  filterSnapshotLinesByIndex('[1]<a>A\n[2]<a>B\nkeep', new Set([2])) === '[2]<a>B\nkeep',
  'viewport filter keeps visible indexes'
)
assert(snapshotPromptBudget('full').maxLines === 200, 'full budget')
const hints = mediaHintsFromUrls([
  { url: 'https://cdn.example.com/master.m3u8', status: 200 },
  { url: 'https://cdn.example.com/seg-001.ts', status: 200 },
  { url: 'https://cdn.example.com/page.html', status: 200 },
])
assert(hints.length === 2 && hints[0].kind === 'hls', 'media hints')
assert(formatMediaHints(hints).includes('hls'), 'format media')

const avdtScript = `window.$avdt = {"c":"jingpin","uid":57666,"hls":"2026\\/08\\/18\\/c09814591bd9e90cb1f139504365ca3d\\/index.m3u8?t=1787359708&m=RfqxG3hgkZXi3td8VI675g","vid":241643,"likes":3,"dislikes":0,"favorites":1,"cdns":["cdn22.jiuse3.cloud"],"countDown":20}`
const mined = minePageSignals({
  url: 'https://rfd0i4.jstv800.com/vod/view/SxCI',
  title: 'test',
  inlineScripts: [avdtScript],
  externalScriptSrcs: [],
  meta: [],
  resources: [],
})
assert(
  mined.signals.some((s) => s.resolvedUrl?.includes('cdn22.jiuse3.cloud') && s.resolvedUrl.includes('.m3u8')),
  'inline $avdt hls resolves with cdn'
)
assert(formatPageSignalsForPrompt(mined).includes('PAGE SIGNALS'), 'format page signals')

const mahuaScript = `var player_aaaa={"flag":"play","encrypt":0,"url":"https:\\/\\/t0.97img.com\\/b1000671\\/a.m3u8","from":"mahua","id":"331448"}`
const playerPage = minePageSignals({
  url: 'https://www.17188.cc/index.php/vod/play/id/331448/sid/1/nid/1.html',
  title: 'play',
  inlineScripts: [mahuaScript],
  externalScriptSrcs: [],
  meta: [],
  resources: [],
}, {
  networkUrls: ['https://lbjx9.com/?url=https://t0.97img.com/b1000671/a.m3u8'],
})
assert(
  playerPage.signals.some((s) => s.label === 'playback' && s.resolvedUrl?.includes('a.m3u8')),
  'player_aaaa url resolves to playback'
)
assert(
  playerPage.signals.some((s) => s.resolvedUrl?.includes('t0.97img.com/b1000671/a.m3u8')),
  'network proxy ?url= resolves'
)

console.log('observe self-check ok')
