import { getCursorSessionToken } from './cursor-auth.js'

const API_BASE = 'https://api2.cursor.sh'
const WEB_BASE = 'https://cursor.com'

function authHeaders(token: string, json = true): Record<string, string> {
  const headers: Record<string, string> = {
    Cookie: `WorkosCursorSessionToken=${token}`,
    Origin: WEB_BASE,
    Accept: 'application/json',
  }
  if (json) {
    headers['Content-Type'] = 'application/json'
    headers['Connect-Protocol-Version'] = '1'
    headers.Authorization = `Bearer ${token}`
  }
  return headers
}

async function dashboardRpc<T>(
  path: string,
  token: string,
  body: unknown = {},
  signal?: AbortSignal
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: authHeaders(token),
    body: JSON.stringify(body),
    signal: signal ?? AbortSignal.timeout(25_000),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Cursor API ${res.status}${text ? `: ${text.slice(0, 160)}` : ''}`)
  }
  return (await res.json()) as T
}

async function webGet<T>(path: string, token: string, signal?: AbortSignal): Promise<T> {
  const res = await fetch(`${WEB_BASE}${path}`, {
    headers: authHeaders(token, false),
    signal: signal ?? AbortSignal.timeout(25_000),
  })
  if (!res.ok) {
    const text = await res.text().catch(() => '')
    throw new Error(`Cursor web ${res.status}${text ? `: ${text.slice(0, 120)}` : ''}`)
  }
  return (await res.json()) as T
}

export type CursorRawSnapshot = {
  periodUsage: unknown
  planInfo: unknown
  usageEvents: unknown
  stripeProfile: unknown
  usageSummary: unknown
}

export async function fetchCursorRawSnapshot(signal?: AbortSignal): Promise<CursorRawSnapshot> {
  const token = await getCursorSessionToken()
  if (!token) {
    throw new Error('未检测到 Cursor 登录：请在 Chrome 打开 cursor.com 并保持登录')
  }

  const usageSummary = await webGet<unknown>('/api/usage-summary', token, signal).catch(() => null)

  let periodUsage: unknown = null
  let planInfo: unknown = null
  try {
    periodUsage = await dashboardRpc<unknown>(
      '/aiserver.v1.DashboardService/GetCurrentPeriodUsage',
      token,
      {},
      signal
    )
    planInfo = await dashboardRpc<unknown>(
      '/aiserver.v1.DashboardService/GetPlanInfo',
      token,
      {},
      signal
    ).catch(() => null)
  } catch (error) {
    if (!usageSummary) throw error
  }

  let usageEvents: unknown = null
  const cycle = pickBillingCycle(periodUsage) ?? pickBillingCycleFromSummary(usageSummary)
  if (cycle) {
    usageEvents = await dashboardRpc<unknown>(
      '/aiserver.v1.DashboardService/GetAggregatedUsageEvents',
      token,
      { startDate: cycle.start, endDate: cycle.end },
      signal
    ).catch(() => null)
  }

  const stripeProfile = await webGet<unknown>('/api/auth/full_stripe_profile', token, signal).catch(
    () => webGet<unknown>('/auth/full_stripe_profile', token, signal).catch(() => null)
  )

  if (!periodUsage && !usageSummary) {
    throw new Error('Cursor 用量接口不可用（401/400），请确认已在浏览器登录 cursor.com')
  }

  return { periodUsage, planInfo, usageEvents, stripeProfile, usageSummary }
}

function pickBillingCycle(periodUsage: unknown): { start: string; end: string } | null {
  const plan = dig(periodUsage, ['planUsage']) ?? dig(periodUsage, ['PlanUsage'])
  const start =
    readString(plan, 'billingCycleStart') ?? readString(plan, 'billing_cycle_start')
  const end = readString(plan, 'billingCycleEnd') ?? readString(plan, 'billing_cycle_end')
  if (!start || !end) return null
  return { start, end }
}

function pickBillingCycleFromSummary(usageSummary: unknown): { start: string; end: string } | null {
  if (!usageSummary || typeof usageSummary !== 'object') return null
  const start = readString(usageSummary, 'billingCycleStart')
  const end = readString(usageSummary, 'billingCycleEnd')
  if (!start || !end) return null
  return { start, end }
}

function dig(obj: unknown, keys: string[]): unknown {
  let cur: unknown = obj
  for (const key of keys) {
    if (!cur || typeof cur !== 'object') return undefined
    cur = (cur as Record<string, unknown>)[key]
  }
  return cur
}

function readString(obj: unknown, key: string): string | undefined {
  if (!obj || typeof obj !== 'object') return undefined
  const v = (obj as Record<string, unknown>)[key]
  return typeof v === 'string' && v ? v : undefined
}
