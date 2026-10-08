import type { DomSnapshot } from '@naviforge/dom-plane'
import { parseIndexedSnapshotLines as parseIndexedLinesFromBlob } from '@naviforge/extract'

export type IndexedSnapshotLine = { index: number; title: string }

const NAV_NOISE =
  /^(登录|注册|sign|register|home|首页|热门|直播|安装|更多|未命名|\*{3}|axx\.|http|www\.)/i

function snapshotBlob(snap: Pick<DomSnapshot, 'header' | 'content' | 'footer'>): string {
  return [snap.header, snap.content, snap.footer].filter(Boolean).join('\n')
}

/** Parse `*[n] title` / `[n] title` rows from any snapshot (host-agnostic). */
export function parseIndexedSnapshotLines(
  snap: Pick<DomSnapshot, 'header' | 'content' | 'footer'>,
  limit = 24
): IndexedSnapshotLine[] {
  return parseIndexedLinesFromBlob(snapshotBlob(snap), limit)
}

export function isNavLikeFeedTitle(title: string): boolean {
  return title.length < 2 || NAV_NOISE.test(title) || /register|login|signin/i.test(title)
}
