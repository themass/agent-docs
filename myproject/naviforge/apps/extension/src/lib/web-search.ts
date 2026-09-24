import type { SearchHit, SearchPlane } from '@naviforge/runtime'
import type { ToolResult } from '@naviforge/shared'

import {
  STORAGE,
  readWebSearchSettings,
  type WebSearchProvider,
} from './settings'

const BRAVE_SEARCH_URL = 'https://api.search.brave.com/res/v1/web/search'
const TAVILY_SEARCH_URL = 'https://api.tavily.com/search'
const MAX_RESULTS = 8
const DEFAULT_RESULTS = 5
const MAX_QUERY_CHARS = 400

function clampCount(n: number | undefined): number {
  if (n == null || !Number.isFinite(n)) return DEFAULT_RESULTS
  return Math.min(MAX_RESULTS, Math.max(1, Math.round(n)))
}

function providerLabel(provider: WebSearchProvider): string {
  return provider === 'tavily' ? 'Tavily' : 'Brave Search'
}

function hitsFrom(
  raw: unknown,
  n: number,
  snippetKey: 'description' | 'content'
): SearchHit[] {
  if (!Array.isArray(raw)) return []
  const hits: SearchHit[] = []
  for (const item of raw) {
    if (hits.length >= n) break
    if (!item || typeof item !== 'object') continue
    const row = item as Record<string, unknown>
    const url = typeof row.url === 'string' ? row.url.trim() : ''
    if (!url) continue
    const snippet = typeof row[snippetKey] === 'string' ? (row[snippetKey] as string).trim() : ''
    hits.push({
      title: typeof row.title === 'string' && row.title.trim() ? row.title.trim() : url,
      url,
      snippet,
    })
  }
  return hits
}

/** Parse Brave Search JSON into title/url/snippet hits. Network-free for self-check. */
export function parseBraveWebResults(body: unknown, n = DEFAULT_RESULTS): SearchHit[] {
  if (!body || typeof body !== 'object') return []
  const web = (body as { web?: { results?: unknown } }).web
  return hitsFrom(web?.results, n, 'description')
}

/** Parse Tavily Search JSON into title/url/snippet hits. Network-free for self-check. */
export function parseTavilyWebResults(body: unknown, n = DEFAULT_RESULTS): SearchHit[] {
  if (!body || typeof body !== 'object') return []
  return hitsFrom((body as { results?: unknown }).results, n, 'content')
}

async function jsonSearch(
  label: string,
  request: Promise<Response>,
  parse: (body: unknown) => SearchHit[]
): Promise<ToolResult<{ results: SearchHit[] }>> {
  try {
    const response = await request
    if (!response.ok) {
      return {
        ok: false,
        error: { code: 'search_failed', message: `${label} HTTP ${response.status}`, recoverable: true },
      }
    }
    const body: unknown = await response.json()
    return { ok: true, data: { results: parse(body) } }
  } catch (error) {
    return {
      ok: false,
      error: { code: 'search_failed', message: (error as Error).message, recoverable: true },
    }
  }
}

export function createWebSearchPlane(): SearchPlane {
  return {
    async search(query: string, n?: number): Promise<ToolResult<{ results: SearchHit[] }>> {
      const q = query.trim().slice(0, MAX_QUERY_CHARS)
      if (!q) {
        return {
          ok: false,
          error: { code: 'bad_args', message: 'query required', recoverable: true },
        }
      }
      const saved = await chrome.storage.local.get(STORAGE.webSearch)
      const settings = readWebSearchSettings(saved[STORAGE.webSearch])
      const apiKey =
        settings.provider === 'tavily' ? settings.tavilyApiKey.trim() : settings.braveApiKey.trim()
      if (!apiKey) {
        const name = providerLabel(settings.provider)
        return {
          ok: false,
          error: {
            code: 'no_search_key',
            message: `${name} API Key 未配置：设置 → 模型 → 网页搜索`,
            recoverable: false,
          },
        }
      }
      const count = clampCount(n)
      if (settings.provider === 'tavily') {
        return jsonSearch(
          'Tavily',
          fetch(TAVILY_SEARCH_URL, {
            method: 'POST',
            headers: {
              Accept: 'application/json',
              'Content-Type': 'application/json',
              Authorization: `Bearer ${apiKey}`,
            },
            body: JSON.stringify({ query: q, max_results: count }),
          }),
          (body) => parseTavilyWebResults(body, count)
        )
      }
      return jsonSearch(
        'Brave Search',
        fetch(`${BRAVE_SEARCH_URL}?q=${encodeURIComponent(q)}&count=${count}`, {
          headers: {
            Accept: 'application/json',
            'X-Subscription-Token': apiKey,
          },
        }),
        (body) => parseBraveWebResults(body, count)
      )
    },
  }
}
