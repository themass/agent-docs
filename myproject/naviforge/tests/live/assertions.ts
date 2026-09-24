export type LiveSiteCase = {
  id: string
  name: string
  url: string
  detailUrl: RegExp
  forbiddenTitle: RegExp
  expected: number
  waitMs?: number
}

export type LiveContentItem = {
  label?: string
  index?: number
  title: string
  url?: string
}

export type LiveViolation = {
  code:
    | 'count'
    | 'empty_title'
    | 'control_title'
    | 'snapshot_title'
    | 'invalid_url'
    | 'wrong_detail_url'
    | 'duplicate_url'
  message: string
}

const SNAPSHOT_TITLE = /^\[\d+\]\s*<[a-z][^>]*>.*\/>$/i
const ENVIRONMENT_BLOCK =
  /verify you are human|captcha|access denied|too many requests|rate limit|unusual traffic|人机验证|安全验证|访问过于频繁|请求过于频繁|地区限制|not available in your country/i

export function classifyEnvironmentBlock(text: string): 'ENV_BLOCKED' | undefined {
  return ENVIRONMENT_BLOCK.test(text) ? 'ENV_BLOCKED' : undefined
}

export function assessExtractedItems(
  items: LiveContentItem[],
  site: Pick<LiveSiteCase, 'detailUrl' | 'forbiddenTitle'>,
  expected: number
): LiveViolation[] {
  const violations: LiveViolation[] = []
  if (items.length !== expected) {
    violations.push({
      code: 'count',
      message: `expected ${expected} records, received ${items.length}`,
    })
  }

  const urls = new Set<string>()
  for (const [index, item] of items.entries()) {
    const title = item.title.replace(/\s+/g, ' ').trim()
    if (!title) {
      violations.push({ code: 'empty_title', message: `item ${index + 1} has no title` })
    } else {
      if (site.forbiddenTitle.test(title)) {
        violations.push({
          code: 'control_title',
          message: `item ${index + 1} uses control text as title: ${title}`,
        })
      }
      if (SNAPSHOT_TITLE.test(title)) {
        violations.push({
          code: 'snapshot_title',
          message: `item ${index + 1} leaked snapshot markup: ${title}`,
        })
      }
    }

    if (!item.url) {
      violations.push({ code: 'invalid_url', message: `item ${index + 1} has no URL` })
      continue
    }
    try {
      new URL(item.url)
    } catch {
      violations.push({ code: 'invalid_url', message: `item ${index + 1} URL is invalid` })
      continue
    }
    if (!site.detailUrl.test(item.url)) {
      violations.push({
        code: 'wrong_detail_url',
        message: `item ${index + 1} is not a detail URL: ${item.url}`,
      })
    }
    if (urls.has(item.url)) {
      violations.push({ code: 'duplicate_url', message: `duplicate URL: ${item.url}` })
    }
    urls.add(item.url)
  }
  return violations
}
