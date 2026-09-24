import type { DomSnapshot } from '@naviforge/dom-plane'

/** Site chrome / navigation labels that must not be clicked on current-page tasks. */
const NAV_CHROME_LABEL =
  /热门|排行榜|首页|番剧|popular|trending|\bhot\b|logo|首页|navigate|go to|登录|sign in/i

export function snapshotLineForIndex(content: string, index: number): string | undefined {
  const match = new RegExp(`^\\[${index}\\][^\\n]*`, 'm').exec(content)
  return match?.[0]
}

/** True when clicking this indexed element is likely to leave the current page scope. */
export function isLikelyNavigationClick(snap: DomSnapshot, index: number): boolean {
  const line = snapshotLineForIndex(snap.content, index)
  if (!line) return false
  if (NAV_CHROME_LABEL.test(line)) return true
  return /\blink\b/i.test(line) && NAV_CHROME_LABEL.test(line)
}
