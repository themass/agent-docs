import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { clearToken, getToken, login, VPN_TOKEN_KEY } from '../src/net/auth'

/** node 环境无 location：defaultApiBase() 走浏览器同源策略 → /vvv/api/game/v1 */
const LOGIN_URL = '/vvv/api/game/v1/login'

const stubLocalStorage = () => {
  const store = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  })
}

const jsonRes = (body: unknown, ok = true, status = 200) => ({
  ok,
  status,
  json: async () => body,
})

describe('登录接口（auth.ts）', () => {
  beforeEach(() => {
    stubLocalStorage()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('成功：POST base+/login，body {name,pwd}，token 写 localStorage 并返回 data', async () => {
    const fetchMock = vi.fn(
      async (_url: string, _init?: { method?: string; headers?: Record<string, string>; body?: string }) =>
        jsonRes({ errno: 0, data: { token: 'TKN-1', name: '小明' }, error: null }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const r = await login(' 小明 ', 'pw123')

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe(LOGIN_URL)
    expect(init).toMatchObject({ method: 'POST', headers: { 'Content-Type': 'application/json' } })
    expect(JSON.parse(init!.body!)).toEqual({ name: ' 小明 ', pwd: 'pw123' })
    expect(r).toEqual({ token: 'TKN-1', name: '小明' })
    expect(localStorage.getItem(VPN_TOKEN_KEY)).toBe('TKN-1')
    expect(getToken()).toBe('TKN-1')
  })

  it('errno!==0：抛服务端 error 文案，且不写 localStorage', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes({ errno: 1002, data: null, error: '账号或密码错误' })))
    await expect(login('a', 'b')).rejects.toThrow('账号或密码错误')
    expect(getToken()).toBe('')
  })

  it('errno!==0 且无 error 文案：回退固定文案', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes({ errno: 1, data: null, error: null })))
    await expect(login('a', 'b')).rejects.toThrow('登录失败')
  })

  it('errno===0 但 data 为 null：同样视为失败', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes({ errno: 0, data: null, error: null })))
    await expect(login('a', 'b')).rejects.toThrow('登录失败')
  })

  it('HTTP 非 2xx：抛 HTTP <status>', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes({ errno: 0, data: null, error: null }, false, 502)))
    await expect(login('a', 'b')).rejects.toThrow('HTTP 502')
    expect(getToken()).toBe('')
  })

  it('失败不覆盖已有 token；clearToken 清空', async () => {
    localStorage.setItem(VPN_TOKEN_KEY, 'OLD')
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes({ errno: 401, data: null, error: '密码错误' })))
    await expect(login('a', 'b')).rejects.toThrow('密码错误')
    expect(getToken()).toBe('OLD') // 登录失败期间保留旧值，过期回登录页不提前清
    clearToken()
    expect(getToken()).toBe('')
  })
})
