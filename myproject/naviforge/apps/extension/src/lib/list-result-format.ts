/** One row from dom.extract_content / dom.mark_topn. */
export type ListResultItem = {
  label?: string
  index?: number
  title?: string
  url?: string
  author?: string
  views?: string
  duration?: string
  fields?: Record<string, string>
  offscreen?: boolean
}

function pickTitle(item: ListResultItem): string {
  const numeric = /^\d+[.,]?\d*(?:[万亿kKmM]\+?)?$/
  const candidates = [
    item.title,
    item.author,
    item.fields?.author,
    ...Object.values(item.fields ?? {}),
  ]
    .map((value) => value?.trim())
    .filter((value): value is string => Boolean(value))
  const titled = candidates.find((text) => text.length >= 4 && !numeric.test(text) && !/^\d{1,3}:\d{2}/.test(text))
  if (titled) return titled
  const short = candidates.find((text) => !numeric.test(text) && !/^\d{1,3}:\d{2}/.test(text))
  return short ?? item.title?.trim() ?? '(无标题)'
}

function pickStats(item: ListResultItem): string {
  const views = item.views ?? item.fields?.views
  const author = item.author ?? item.fields?.author
  const duration = item.duration ?? item.fields?.duration
  return [views ? `播放 ${views}` : '', author ? `UP ${author}` : '', duration].filter(Boolean).join(' · ')
}

/** One line for timeline cards; multi-line block for the results panel. */
export function formatListItem(item: ListResultItem, rank: number): { headline: string; detail: string } {
  const label = item.label ?? `TOP${rank}`
  const title = pickTitle(item)
  const stats = pickStats(item)
  const headline = `${label} · ${title}`
  const detail = [stats, item.url, item.offscreen ? '标记在视口外，点击可定位' : '']
    .filter(Boolean)
    .join('\n')
  return { headline, detail }
}

export function formatListBody(
  items: ListResultItem[],
  opts?: { shortfall?: string; missed?: string[]; offscreen?: string[] }
): string {
  const lines = items.map((item, index) => {
    const { headline, detail } = formatListItem(item, index + 1)
    return detail ? `${headline}\n   ${detail.replace(/\n/g, '\n   ')}` : headline
  })
  const notes = [
    opts?.shortfall ? `注意：${opts.shortfall}` : '',
    opts?.missed?.length ? `未能标记：${opts.missed.join('、')}` : '',
    opts?.offscreen?.length
      ? `视口外（滚动查看或点击定位）：${opts.offscreen.join('、')}`
      : '',
  ].filter(Boolean)
  return [...lines, ...notes].join('\n') || '(无结果)'
}
