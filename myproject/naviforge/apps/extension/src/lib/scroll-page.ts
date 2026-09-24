/** Whether the window viewport is at (or past) the document bottom. */
export function pageAtBottom(scrollY: number, innerHeight: number, scrollHeight: number): boolean {
  return scrollY + innerHeight >= scrollHeight - 4
}

/** Pick the largest overflow scroll container (GitHub main column, etc.). */
export function pickLargestScrollable(
  candidates: Array<{ scrollHeight: number; clientHeight: number; clientWidth: number; overflowY: string }>
): number {
  let best = -1
  let bestArea = 0
  for (let i = 0; i < candidates.length; i++) {
    const el = candidates[i]!
    if (!/(auto|scroll|overlay)/i.test(el.overflowY)) continue
    if (el.scrollHeight <= el.clientHeight + 8) continue
    const area = el.clientWidth * el.clientHeight
    if (area > bestArea) {
      bestArea = area
      best = i
    }
  }
  return best
}
