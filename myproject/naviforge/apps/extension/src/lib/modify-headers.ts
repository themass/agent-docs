/** Persistent request-header injection + optional CORS response headers via DNR. */

import { STORAGE } from './settings'

export type HeaderKv = { key: string; value: string }

export type ModifyHeadersSettings = {
  enabled: boolean
  /** Inject Access-Control-Allow-* on responses (best-effort; browsers may still block credentialed CORS). */
  cors: boolean
  headers: HeaderKv[]
}

export const DEFAULT_MODIFY_HEADERS: ModifyHeadersSettings = {
  enabled: false,
  cors: false,
  headers: [{ key: '', value: '' }],
}

/** Dynamic rule id band reserved for this feature. */
const RULE_REQUEST = 9101
const RULE_CORS = 9102
const RULE_IDS = [RULE_REQUEST, RULE_CORS]

const RESOURCE_TYPES = [
  'main_frame',
  'sub_frame',
  'stylesheet',
  'script',
  'image',
  'font',
  'object',
  'xmlhttprequest',
  'ping',
  'csp_report',
  'media',
  'websocket',
  'other',
] as unknown as chrome.declarativeNetRequest.ResourceType[]

export function normalizeModifyHeaders(raw: unknown): ModifyHeadersSettings {
  if (!raw || typeof raw !== 'object') return { ...DEFAULT_MODIFY_HEADERS, headers: [{ key: '', value: '' }] }
  const value = raw as Partial<ModifyHeadersSettings>
  const headers = Array.isArray(value.headers)
    ? value.headers
        .filter((item): item is HeaderKv => Boolean(item && typeof item === 'object'))
        .map((item) => ({ key: String(item.key ?? ''), value: String(item.value ?? '') }))
    : [{ key: '', value: '' }]
  return {
    enabled: value.enabled === true,
    cors: value.cors === true,
    headers: headers.length ? headers : [{ key: '', value: '' }],
  }
}

export function buildModifyHeaderRules(
  settings: ModifyHeadersSettings
): chrome.declarativeNetRequest.Rule[] {
  if (!settings.enabled) return []
  const rules: chrome.declarativeNetRequest.Rule[] = []
  const requestHeaders = settings.headers
    .map((item) => ({ header: item.key.trim(), value: item.value }))
    .filter((item) => item.header.length > 0)
    .map(
      (item): chrome.declarativeNetRequest.ModifyHeaderInfo => ({
        header: item.header,
        operation: 'set',
        value: item.value,
      })
    )
  if (requestHeaders.length) {
    rules.push({
      id: RULE_REQUEST,
      priority: 1,
      action: { type: 'modifyHeaders', requestHeaders },
      condition: { urlFilter: '|http', resourceTypes: RESOURCE_TYPES },
    })
  }
  if (settings.cors) {
    rules.push({
      id: RULE_CORS,
      priority: 1,
      action: {
        type: 'modifyHeaders',
        responseHeaders: [
          { header: 'Access-Control-Allow-Origin', operation: 'set', value: '*' },
          { header: 'Access-Control-Allow-Methods', operation: 'set', value: '*' },
          { header: 'Access-Control-Allow-Headers', operation: 'set', value: '*' },
          { header: 'Access-Control-Expose-Headers', operation: 'set', value: '*' },
        ],
      },
      condition: { urlFilter: '|http', resourceTypes: RESOURCE_TYPES },
    })
  }
  return rules
}

export async function applyModifyHeaderRules(settings: ModifyHeadersSettings): Promise<void> {
  await chrome.declarativeNetRequest.updateDynamicRules({
    removeRuleIds: RULE_IDS,
    addRules: buildModifyHeaderRules(settings),
  })
}

/** Persist to storage + disk workspace + apply DNR rules (disabled by default). */
export async function persistModifyHeadersSettings(
  settings: ModifyHeadersSettings
): Promise<ModifyHeadersSettings> {
  const normalized = normalizeModifyHeaders(settings)
  await chrome.storage.local.set({ [STORAGE.modifyHeaders]: normalized })
  try {
    const { persistDiskSettings } = await import('./disk-config')
    await persistDiskSettings({ headers: normalized })
  } catch {
    /* ponytail: disk mirror optional when helper is down */
  }
  await applyModifyHeaderRules(normalized)
  return normalized
}
