/**
 * 登录与本地 token（Vpn-Token）存取。
 *
 * 契约（后端并行开发中，按此实现）：
 *   POST ${defaultApiBase()}/login  Content-Type: application/json
 *   body {name, pwd} → JsonResult {errno, data: {token, name} | null, error}
 *   errno !== 0 或 HTTP 非 2xx 一律抛错（优先透出服务端 error 文案）。
 *
 * 成功后 token 写 localStorage 'plane-duel:vpnToken'（键与 WS 握手共用）；
 * 失败不动已有存储。getToken/clearToken 是该键的唯一出入口。
 *
 * 纯逻辑：只依赖全局 fetch/localStorage，vitest（node 环境）打桩即可测。
 * 注意：本模块被 net/socket.ts 引用（getVpnToken → getToken），http.ts 又引用
 * socket.ts；三方都只在函数体内互调，循环引用在 ESM 下安全。
 */

import { defaultApiBase } from './http'

export const VPN_TOKEN_KEY = 'plane-duel:vpnToken'

export type LoginResult = { token: string; name: string }

type JsonResult = { errno: number; data: LoginResult | null; error: string | null }

/** 本地 token；无则空串。 */
export function getToken(): string {
  return localStorage.getItem(VPN_TOKEN_KEY) ?? ''
}

/** 清掉本地 token（退出登录用；登录过期回登录页时刻意不清，成功登录才覆盖）。 */
export function clearToken(): void {
  localStorage.removeItem(VPN_TOKEN_KEY)
}

/** 登录成功即写入 localStorage 并返回 {token, name}；失败抛错（带服务端文案）。 */
export async function login(name: string, pwd: string): Promise<LoginResult> {
  const res = await fetch(`${defaultApiBase()}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, pwd }),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const body = (await res.json()) as JsonResult
  if (body.errno !== 0 || body.data === null) throw new Error(body.error ?? '登录失败')
  localStorage.setItem(VPN_TOKEN_KEY, body.data.token)
  return body.data
}
