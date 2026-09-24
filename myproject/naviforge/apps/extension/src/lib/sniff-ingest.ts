import type { NetworkEvent } from '@naviforge/network-plane'

/** Normalize URL path for API grouping (strip query, collapse numeric segments). */
export function sniffApiKey(method: string, url: string): string {
  try {
    const u = new URL(url)
    const path = u.pathname
      .replace(/\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, '/{uuid}')
      .replace(/\/\d+/g, '/{id}')
    return `${method.toUpperCase()} ${u.host}${path}`
  } catch {
    return `${method.toUpperCase()} ${url.split('?')[0]}`
  }
}

export function urlMatchesOrigin(url: string, origin: string): boolean {
  const needle = origin.trim().toLowerCase()
  if (!needle) return true
  try {
    const u = new URL(url)
    if (needle.includes('://')) {
      return url.toLowerCase().startsWith(needle)
    }
    return u.hostname === needle || u.hostname.endsWith(`.${needle}`)
  } catch {
    return url.toLowerCase().includes(needle)
  }
}

export function inferJsonSchema(text: string): Record<string, unknown> | undefined {
  try {
    let value: unknown = JSON.parse(text)
    if (Array.isArray(value)) value = value[0]
    if (!value || typeof value !== 'object') return undefined
    const properties: Record<string, string> = {}
    for (const [key, val] of Object.entries(value as Record<string, unknown>)) {
      if (val === null) properties[key] = 'null'
      else if (Array.isArray(val)) properties[key] = 'array'
      else properties[key] = typeof val
    }
    return { type: 'object', properties }
  } catch {
    return undefined
  }
}

export function shouldCaptureSniffEvent(event: NetworkEvent, origin: string): boolean {
  if (!event.url || event.url.startsWith('chrome-extension://')) return false
  if (!/^https?:/i.test(event.url)) return false
  const mime = event.mimeType ?? ''
  if (/image|font|video|audio|octet-stream/i.test(mime)) return false
  if (!urlMatchesOrigin(event.url, origin)) return false
  return true
}

export type SniffIngestInput = {
  method: string
  url: string
  status?: number
  mimeType?: string
  resBody?: string
  ts: number
  eventId: string
}

export function displayUrlFromKey(key: string): string {
  const space = key.indexOf(' ')
  return space >= 0 ? key.slice(space + 1) : key
}
