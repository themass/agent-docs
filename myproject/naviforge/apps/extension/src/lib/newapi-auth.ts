import { STORAGE } from './settings'

/** Deployed NewAPI portal (login + plugin API). HTTP — HTTPS uses a self-signed cert that extension fetch rejects. */
export const NEWAPI_PORTAL_BASE = 'http://gpt.sspacee.com'

/** Chat/OCR API base derived from the portal origin (never trust bootstrap HTTPS when portal is HTTP). */
export function managedApiBaseUrl(portalBase: string): string {
  const base = normalizePortalBase(portalBase).replace(/\/$/, '')
  return `${base}/v1`
}

/** ponytail: downgrade known self-signed HTTPS portal to HTTP so MV3 fetch works. */
export function normalizePortalBase(url: string): string {
  const trimmed = url.trim().replace(/\/$/, '')
  if (/^https:\/\/gpt\.sspacee\.com$/i.test(trimmed)) {
    return 'http://gpt.sspacee.com'
  }
  return trimmed || NEWAPI_PORTAL_BASE
}

export const MANAGED_CHAT_PROFILE_ID = 'mp_newapi_managed_chat'
export const MANAGED_OCR_PROFILE_ID = 'mp_newapi_managed_ocr'

/** Re-fetch bootstrap if older than this (ms). */
export const NEWAPI_SYNC_MAX_AGE_MS = 6 * 60 * 60 * 1000

export type NewApiAuthMode = 'manual' | 'managed'

export type NewApiUser = {
  id: string
  email?: string
  displayName?: string
  quotaUsd?: number
}

export type NewApiAuthState = {
  mode: NewApiAuthMode
  portalBase: string
  accessToken?: string
  refreshToken?: string
  expiresAt?: number
  user?: NewApiUser
  lastSyncAt?: number
  lastSyncError?: string
}

export type NewApiCallbackTokens = {
  accessToken: string
  refreshToken?: string
  expiresInSec?: number
}

export type PluginBootstrap = {
  user: NewApiUser
  apiKey: string
  baseURL: string
  chatModel: string
  ocrModel: string
  chatProfileName?: string
  ocrProfileName?: string
}

const DEFAULT_STATE: NewApiAuthState = {
  mode: 'manual',
  portalBase: NEWAPI_PORTAL_BASE,
}

export function normalizeNewApiAuthState(value: unknown): NewApiAuthState {
  if (!value || typeof value !== 'object') return { ...DEFAULT_STATE }
  const raw = value as Partial<NewApiAuthState>
  const mode: NewApiAuthMode = raw.mode === 'managed' ? 'managed' : 'manual'
  return {
    mode,
    portalBase:
      typeof raw.portalBase === 'string' && raw.portalBase.trim()
        ? normalizePortalBase(raw.portalBase)
        : NEWAPI_PORTAL_BASE,
    accessToken: typeof raw.accessToken === 'string' ? raw.accessToken : undefined,
    refreshToken: typeof raw.refreshToken === 'string' ? raw.refreshToken : undefined,
    expiresAt: typeof raw.expiresAt === 'number' ? raw.expiresAt : undefined,
    user:
      raw.user && typeof raw.user === 'object' && typeof (raw.user as NewApiUser).id === 'string'
        ? (raw.user as NewApiUser)
        : undefined,
    lastSyncAt: typeof raw.lastSyncAt === 'number' ? raw.lastSyncAt : undefined,
    lastSyncError: typeof raw.lastSyncError === 'string' ? raw.lastSyncError : undefined,
  }
}

export async function loadNewApiAuth(): Promise<NewApiAuthState> {
  const saved = await chrome.storage.local.get(STORAGE.newapiAuth)
  return normalizeNewApiAuthState(saved[STORAGE.newapiAuth])
}

export async function saveNewApiAuth(state: NewApiAuthState): Promise<void> {
  await chrome.storage.local.set({ [STORAGE.newapiAuth]: normalizeNewApiAuthState(state) })
}

export function isNewApiLoggedIn(state: NewApiAuthState): boolean {
  if (state.mode !== 'managed') return true
  // ponytail: keep session while access_token exists; clear only on bootstrap 401
  return Boolean(state.accessToken?.trim())
}

export function shouldSyncBootstrap(state: NewApiAuthState, opts?: { apiKeyEmpty?: boolean; force?: boolean }): boolean {
  if (state.mode !== 'managed') return false
  if (!isNewApiLoggedIn(state)) return false
  if (opts?.force) return true
  if (opts?.apiKeyEmpty) return true
  if (!state.lastSyncAt) return true
  return Date.now() - state.lastSyncAt > NEWAPI_SYNC_MAX_AGE_MS
}

export function authCallbackUrl(): string {
  const id = chrome.runtime?.id?.trim()
  if (!id || id === 'invalid') {
    throw new Error('扩展未就绪，请在侧栏或设置页重试，或重新加载扩展')
  }
  // HTTPS chromiumapp.org — required for portal → extension OAuth (chrome-extension:// is blocked from web)
  return `https://${id}.chromiumapp.org/auth-callback`
}

export function assertValidAuthCallbackUrl(url: string): void {
  try {
    const id = chrome.runtime?.id?.trim()
    const parsed = new URL(url)
    if (
      parsed.protocol === 'https:' &&
      id &&
      parsed.hostname === `${id}.chromiumapp.org`
    ) {
      return
    }
    throw new Error('invalid callback')
  } catch {
    throw new Error('无法生成扩展回调地址，请重新加载 NaviForge 扩展后再登录')
  }
}

export function buildNewApiLoginUrl(state?: Pick<NewApiAuthState, 'portalBase'>): string {
  const base = (state?.portalBase ?? NEWAPI_PORTAL_BASE).replace(/\/$/, '')
  const id = chrome.runtime?.id?.trim()
  if (!id || id === 'invalid') {
    throw new Error('扩展未就绪，请重新加载扩展')
  }
  assertValidAuthCallbackUrl(authCallbackUrl())
  const stateNonce = `${Date.now().toString(36)}_${Math.random().toString(36).slice(2, 8)}`
  // Short URL: extension_id reconstructs redirect_uri on portal (launchWebAuthFlow may strip long query)
  return `${base}/plugin/connect?extension_id=${encodeURIComponent(id)}&client=naviforge-extension&state=${stateNonce}`
}

export function parseNewApiCallbackTokens(href: string): NewApiCallbackTokens | null {
  const url = new URL(href)
  const query = url.searchParams
  const hash = new URLSearchParams(url.hash.startsWith('#') ? url.hash.slice(1) : url.hash)
  const accessToken =
    query.get('token') ??
    query.get('access_token') ??
    hash.get('access_token') ??
    hash.get('token')
  if (!accessToken?.trim()) return null
  const refreshToken = query.get('refresh_token') ?? hash.get('refresh_token') ?? query.get('refresh') ?? undefined
  const expiresRaw = query.get('expires_in') ?? hash.get('expires_in')
  const expiresInSec = expiresRaw ? Number(expiresRaw) : undefined
  return {
    accessToken: accessToken.trim(),
    refreshToken: refreshToken?.trim() || undefined,
    expiresInSec: Number.isFinite(expiresInSec) ? expiresInSec : undefined,
  }
}

export async function setNewApiMode(mode: NewApiAuthMode): Promise<NewApiAuthState> {
  const current = await loadNewApiAuth()
  const next: NewApiAuthState = { ...current, mode }
  if (mode === 'manual') {
    next.lastSyncError = undefined
  }
  await saveNewApiAuth(next)
  return next
}

export async function completeNewApiLogin(tokens: NewApiCallbackTokens): Promise<NewApiAuthState> {
  const current = await loadNewApiAuth()
  const expiresAt =
    tokens.expiresInSec && tokens.expiresInSec > 0
      ? Date.now() + tokens.expiresInSec * 1000
      : Date.now() + 365 * 24 * 60 * 60 * 1000
  const next: NewApiAuthState = {
    ...current,
    mode: 'managed',
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken ?? current.refreshToken,
    expiresAt,
    lastSyncError: undefined,
  }
  await saveNewApiAuth(next)
  return next
}

export async function logoutNewApi(): Promise<NewApiAuthState> {
  const next: NewApiAuthState = {
    mode: 'managed',
    portalBase: NEWAPI_PORTAL_BASE,
  }
  await saveNewApiAuth(next)
  return next
}

export async function finishNewApiOAuthRedirect(redirectUrl: string): Promise<NewApiAuthState> {
  const tokens = parseNewApiCallbackTokens(redirectUrl)
  if (!tokens) {
    throw new Error('登录回调缺少 token，请重试')
  }
  await completeNewApiLogin(tokens)
  const { syncManagedProfilesFromNewApi } = await import('./newapi-sync')
  const sync = await syncManagedProfilesFromNewApi({ force: true })
  if (!sync.ok) {
    throw new Error(
      sync.error?.includes('fetch') || sync.error?.includes('HTTP')
        ? `已登录，但拉取默认 Key/模型失败：${sync.error}`
        : sync.error ?? '同步失败'
    )
  }
  void chrome.runtime.sendMessage({ type: 'NEWAPI_AUTH_DONE' }).catch(() => {})
  await chrome.storage.local.remove(STORAGE.newapiPendingAuth)
  return loadNewApiAuth()
}

function launchWebAuthFlow(url: string): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!chrome.identity?.launchWebAuthFlow) {
      reject(new Error('当前环境不支持 identity 登录'))
      return
    }
    chrome.identity.launchWebAuthFlow({ url, interactive: true }, (redirectUrl) => {
      const err = chrome.runtime.lastError?.message
      if (err) {
        reject(new Error(err.includes('canceled') ? '登录已取消' : err))
        return
      }
      if (!redirectUrl) {
        reject(new Error('登录已取消'))
        return
      }
      resolve(redirectUrl)
    })
  })
}

export async function startNewApiLogin(): Promise<NewApiAuthState> {
  const auth = await loadNewApiAuth()
  if (auth.mode !== 'managed') {
    await saveNewApiAuth({ ...auth, mode: 'managed' })
  }
  const callback = authCallbackUrl()
  assertValidAuthCallbackUrl(callback)
  const url = buildNewApiLoginUrl(auth)
  await chrome.storage.local.set({
    [STORAGE.newapiPendingAuth]: { callback, startedAt: Date.now() },
  })
  const redirectUrl = await launchWebAuthFlow(url)
  return finishNewApiOAuthRedirect(redirectUrl)
}

export async function fetchPluginBootstrap(
  auth: NewApiAuthState
): Promise<{ ok: true; data: PluginBootstrap } | { ok: false; status: number; error: string }> {
  const token = auth.accessToken?.trim()
  if (!token) return { ok: false, status: 401, error: 'not logged in' }
  const base = auth.portalBase.replace(/\/$/, '')
  let response: Response
  try {
    response = await fetch(`${base}/api/plugin/bootstrap`, {
      method: 'GET',
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/json',
      },
    })
  } catch (error) {
    return { ok: false, status: 0, error: (error as Error).message || 'network error' }
  }
  if (response.status === 401) {
    return { ok: false, status: 401, error: 'session expired' }
  }
  if (!response.ok) {
    const text = await response.text().catch(() => '')
    return { ok: false, status: response.status, error: text.slice(0, 200) || `HTTP ${response.status}` }
  }
  let data: unknown
  try {
    data = await response.json()
  } catch {
    return { ok: false, status: response.status, error: 'invalid JSON' }
  }
  const parsed = parseBootstrapPayload(data)
  if (!parsed) return { ok: false, status: response.status, error: 'bootstrap schema mismatch' }
  parsed.baseURL = managedApiBaseUrl(auth.portalBase)
  return { ok: true, data: parsed }
}

function parseBootstrapPayload(value: unknown): PluginBootstrap | null {
  if (!value || typeof value !== 'object') return null
  const raw = value as Record<string, unknown>
  const userRaw = raw.user
  if (!userRaw || typeof userRaw !== 'object' || typeof (userRaw as NewApiUser).id !== 'string') return null
  const apiKey = typeof raw.apiKey === 'string' ? raw.apiKey.trim() : ''
  const baseURL = typeof raw.baseURL === 'string' ? raw.baseURL.trim() : ''
  const chatModel = typeof raw.chatModel === 'string' ? raw.chatModel.trim() : ''
  const ocrModel = typeof raw.ocrModel === 'string' ? raw.ocrModel.trim() : ''
  if (!apiKey || !baseURL || !chatModel || !ocrModel) return null
  return {
    user: userRaw as NewApiUser,
    apiKey,
    baseURL,
    chatModel,
    ocrModel,
    chatProfileName: typeof raw.chatProfileName === 'string' ? raw.chatProfileName : undefined,
    ocrProfileName: typeof raw.ocrProfileName === 'string' ? raw.ocrProfileName : undefined,
  }
}

export async function markBootstrapSync(auth: Partial<NewApiAuthState>): Promise<void> {
  const current = await loadNewApiAuth()
  await saveNewApiAuth({
    ...current,
    ...auth,
    lastSyncAt: Date.now(),
    lastSyncError: auth.lastSyncError,
  })
}

export async function clearNewApiSession(): Promise<void> {
  const current = await loadNewApiAuth()
  await saveNewApiAuth({
    ...current,
    accessToken: undefined,
    refreshToken: undefined,
    expiresAt: undefined,
    user: undefined,
    lastSyncError: 'session expired',
  })
}
