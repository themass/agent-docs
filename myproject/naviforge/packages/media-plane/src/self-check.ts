import { mediaHintsFromUrls, parseM3u8Lines } from './hints.js'
import { resolveHlsPlaylist } from './hls.js'

function assert(cond: unknown, msg: string): asserts cond {
  if (!cond) throw new Error(msg)
}

const hints = mediaHintsFromUrls([{ url: 'https://x.com/a.m3u8' }])
assert(hints[0]?.kind === 'hls', 'hls hint')
const proxy = mediaHintsFromUrls([
  { url: 'https://lbjx9.com/?url=https://t0.97img.com/b1000671/a.m3u8', status: 200 },
])
assert(proxy[0]?.url.includes('97img.com') && proxy[0]?.kind === 'hls', 'proxy ?url= m3u8')
const lines = parseM3u8Lines('#EXTM3U\n/master.m3u8\n/seg.ts', 'https://cdn.example.com/')
assert(lines[0]?.includes('master.m3u8'), 'm3u8 parse')
const master = resolveHlsPlaylist(
  '#EXTM3U\n#EXT-X-STREAM-INF:\n720p.m3u8\n',
  'https://cdn.example.com/master.m3u8'
)
assert(master.kind === 'master' && master.variants[0]?.includes('720p.m3u8'), 'hls master parse')
const media = resolveHlsPlaylist(
  '#EXTM3U\n#EXTINF:10,\nseg-001.ts\n#EXTINF:10,\nseg-002.ts\n',
  'https://cdn.example.com/720p/index.m3u8'
)
assert(media.kind === 'media' && media.segments.length === 2, 'hls media segments')

console.log('media-plane self-check ok')
