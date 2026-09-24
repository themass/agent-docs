import { DEFAULT_HOST, STORAGE, type HostSettings } from './settings'

function safeHostUrl(value: string): string {
  const url = new URL(value)
  if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname)) {
    throw new Error('Host bridge must use local HTTP on 127.0.0.1 or localhost')
  }
  return url.href.replace(/\/$/, '')
}

async function hostJson<T>(host: HostSettings, path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${safeHostUrl(host.url)}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${host.token}`,
      ...(init?.body ? { 'Content-Type': 'application/json' } : {}),
      ...init?.headers,
    },
  })
  const body = (await response.json()) as { error?: string }
  if (!response.ok) throw new Error(body.error ?? `Host returned HTTP ${response.status}`)
  return body as T
}

function str(raw: Record<string, unknown>, ...keys: string[]): string | undefined {
  for (const key of keys) {
    const value = raw[key]
    if (typeof value === 'string' && value.trim()) return value.trim()
  }
  return undefined
}

function num(raw: Record<string, unknown>, ...keys: string[]): number | undefined {
  for (const key of keys) {
    const value = raw[key]
    if (typeof value === 'number' && Number.isFinite(value)) return value
    if (typeof value === 'string' && value.trim() && Number.isFinite(Number(value))) {
      return Number(value)
    }
  }
  return undefined
}

export type PublicIpInfo = {
  ip: string
  country?: string
  countryCode?: string
  region?: string
  regionCode?: string
  city?: string
  postalCode?: string
  continentCode?: string
  latitude?: number
  longitude?: number
  timezone?: string
  offset?: number
  isp?: string
  organization?: string
  asn?: string
  asnOrganization?: string
  raw: Record<string, unknown>
}

function parseGeo(raw: Record<string, unknown>): PublicIpInfo {
  const ip = str(raw, 'ip')
  if (!ip) throw new Error('IP lookup returned no ip')
  const asnNum = num(raw, 'asn')
  return {
    ip,
    country: str(raw, 'country'),
    countryCode: str(raw, 'country_code', 'countryCode'),
    region: str(raw, 'region', 'region_name'),
    regionCode: str(raw, 'region_code', 'regionCode'),
    city: str(raw, 'city'),
    postalCode: str(raw, 'postal_code', 'postalCode'),
    continentCode: str(raw, 'continent_code', 'continentCode'),
    latitude: num(raw, 'latitude'),
    longitude: num(raw, 'longitude'),
    timezone: str(raw, 'timezone'),
    offset: num(raw, 'offset'),
    isp: str(raw, 'isp'),
    organization: str(raw, 'organization', 'org'),
    asn: asnNum != null ? `AS${asnNum}` : str(raw, 'asn'),
    asnOrganization: str(raw, 'asn_organization', 'asnOrganization'),
    raw,
  }
}

/**
 * Public IP / geo via api.ip.sb.
 * Empty `query` → this machine's egress IP; otherwise look up that address.
 */
export async function lookupPublicIp(query = ''): Promise<PublicIpInfo> {
  const target = query.trim()
  const path = target ? `/${encodeURIComponent(target)}` : ''
  const response = await fetch(`https://api.ip.sb/geoip${path}`, { cache: 'no-store' })
  if (!response.ok) throw new Error(`IP lookup HTTP ${response.status}`)
  return parseGeo((await response.json()) as Record<string, unknown>)
}

export function formatPublicIp(info: PublicIpInfo): string {
  const location = [info.country, info.region, info.city].filter(Boolean).join(' / ')
  const coords =
    info.latitude != null && info.longitude != null
      ? `${info.latitude}, ${info.longitude}`
      : undefined
  const lines = [
    `IP: ${info.ip}`,
    location ? `位置: ${location}` : null,
    info.countryCode || info.continentCode
      ? `代码: ${[info.countryCode, info.regionCode, info.continentCode].filter(Boolean).join(' · ')}`
      : null,
    info.postalCode ? `邮编: ${info.postalCode}` : null,
    coords ? `坐标: ${coords}` : null,
    info.timezone
      ? `时区: ${info.timezone}${info.offset != null ? ` (UTC${info.offset >= 0 ? '+' : ''}${info.offset / 3600})` : ''}`
      : null,
    info.isp ? `ISP: ${info.isp}` : null,
    info.organization && info.organization !== info.isp ? `组织: ${info.organization}` : null,
    info.asn ? `ASN: ${info.asn}${info.asnOrganization ? ` · ${info.asnOrganization}` : ''}` : null,
  ]
  return lines.filter(Boolean).join('\n')
}

export type TracerouteResult = {
  target: string
  command: string
  lines: string[]
  timedOut?: boolean
}

/** Optional power-user path: system traceroute via local Host (not store-default). */
export async function runHostTraceroute(target: string, maxHops = 20): Promise<TracerouteResult> {
  const saved = await chrome.storage.local.get(STORAGE.host)
  const host = { ...DEFAULT_HOST, ...(saved[STORAGE.host] as Partial<HostSettings> | undefined) }
  if (!host.enabled || !host.token) {
    throw new Error('需要启用本地 Host（设置 → Host），才能运行 traceroute')
  }
  return hostJson<TracerouteResult>(host, '/net/traceroute', {
    method: 'POST',
    body: JSON.stringify({ target: target.trim(), maxHops }),
  })
}

export function formatTraceroute(result: TracerouteResult): string {
  const head = [`目标: ${result.target}`, `命令: ${result.command}`, result.timedOut ? '（已超时截断）' : '']
    .filter(Boolean)
    .join('\n')
  return `${head}\n\n${result.lines.join('\n')}`
}

/** OpenStreetMap marker URL (no API key). */
export function openStreetMapMarkerUrl(latitude: number, longitude: number, zoom = 11): string {
  return `https://www.openstreetmap.org/?mlat=${latitude}&mlon=${longitude}#map=${zoom}/${latitude}/${longitude}`
}

/** Static map image for a single pin (no Leaflet dependency). */
export function openStreetMapStaticUrl(
  latitude: number,
  longitude: number,
  zoom = 11,
  size = '560x240'
): string {
  return `https://staticmap.openstreetmap.de/staticmap.php?center=${latitude},${longitude}&zoom=${zoom}&size=${size}&maptype=mapnik&markers=${latitude},${longitude},lightblue1`
}
