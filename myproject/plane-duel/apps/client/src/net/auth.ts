/**
 * 登录/注册/找回密码与本地 token（Vpn-Token）存取。
 *
 * 契约（后端并行开发中，按此实现）——全部 POST + Content-Type: application/json，
 * 统一返回 JsonResult {errno, data, error}；HTTP 非 2xx 或 errno !== 0 一律抛错
 * （优先透出服务端 error 中文文案，无文案则兜底中文）：
 *   POST ${defaultApiBase()}/login      body {name, pwd}         → data {token, name}
 *   POST ${defaultApiBase()}/register   body {name, pwd, rePwd, email} → data 不限（email 可空串）
 *   POST ${defaultApiBase()}/findpass   body {email}             → 成功即 errno 0
 *   POST ${defaultApiBase()}/resetpass  body {email, code, pwd, rePwd}  → 成功即 errno 0
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

/** 非登录接口（register/findpass/resetpass）的返回：只关心 errno/error，data 不限。 */
type EmptyResult = { errno: number; data: unknown; error: string | null }

/** POST JSON 并透出服务端错误：HTTP 非 2xx 抛 HTTP <status>；errno!==0 抛 error 文案（无则 fallback）。 */
async function postJson(url: string, payload: object, fallback: string): Promise<EmptyResult> {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const body = (await res.json()) as EmptyResult
  if (body.errno !== 0) throw new Error(body.error ?? fallback)
  return body
}

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

/**
 * 注册新账号；email 可空串（找回密码用，注册时可不填）。
 * 成功后自动 login(name, pwd) 直接进游戏（体验闭环）；注册本身失败（如"用户名已存在"）
 * 透出服务端文案，不会发起登录请求。
 */
export async function register(name: string, pwd: string, rePwd: string, email: string): Promise<LoginResult> {
  await postJson(`${defaultApiBase()}/register`, { name, pwd, rePwd, email }, '注册失败，请稍后再试')
  return login(name, pwd)
}

/**
 * 找回密码 step1：向邮箱发送验证码。
 * 服务端刻意不区分"邮箱是否绑定账号"（防枚举），errno===0 即按固定语义提示即可。
 */
export async function findpass(email: string): Promise<void> {
  await postJson(`${defaultApiBase()}/findpass`, { email }, '发送失败，请稍后再试')
}

/** 找回密码 step2：验证码 + 新密码；失败（如"验证码已过期，请重新获取"）透出服务端文案。 */
export async function resetpass(email: string, code: string, pwd: string, rePwd: string): Promise<void> {
  await postJson(`${defaultApiBase()}/resetpass`, { email, code, pwd, rePwd }, '重置失败，请稍后再试')
}
