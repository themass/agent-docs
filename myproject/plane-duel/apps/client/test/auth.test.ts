import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  clearToken,
  findpass,
  getToken,
  login,
  register,
  resetpass,
  VPN_TOKEN_KEY,
} from '../src/net/auth'

/** node 环境无 location：defaultApiBase() 走浏览器同源策略 → /vvv/api/game/v1 */
const LOGIN_URL = '/vvv/api/game/v1/login'
const REGISTER_URL = '/vvv/api/game/v1/register'
const FINDPASS_URL = '/vvv/api/game/v1/findpass'
const RESETPASS_URL = '/vvv/api/game/v1/resetpass'

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

describe('注册/找回密码接口（auth.ts）', () => {
  beforeEach(() => {
    stubLocalStorage()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('register 成功：POST base+/register 带 {name,pwd,rePwd,email}，随后自动 login 写入 token', async () => {
    const fetchMock = vi.fn(
      async (url: string, _init?: { method?: string; headers?: Record<string, string>; body?: string }) =>
        url === REGISTER_URL
          ? jsonRes({ errno: 0, data: null, error: null })
          : jsonRes({ errno: 0, data: { token: 'TKN-NEW', name: '小红' }, error: null }),
    )
    vi.stubGlobal('fetch', fetchMock)

    const r = await register('小红', 'pw123', 'pw123', '')

    expect(fetchMock).toHaveBeenCalledTimes(2)
    const [regUrl, regInit] = fetchMock.mock.calls[0]!
    expect(regUrl).toBe(REGISTER_URL)
    expect(regInit).toMatchObject({ method: 'POST', headers: { 'Content-Type': 'application/json' } })
    expect(JSON.parse(regInit!.body!)).toEqual({ name: '小红', pwd: 'pw123', rePwd: 'pw123', email: '' })
    // 链式登录：第二次请求必须是 login，body 同注册凭据
    const [loginUrl, loginInit] = fetchMock.mock.calls[1]!
    expect(loginUrl).toBe(LOGIN_URL)
    expect(JSON.parse(loginInit!.body!)).toEqual({ name: '小红', pwd: 'pw123' })
    expect(r).toEqual({ token: 'TKN-NEW', name: '小红' })
    expect(getToken()).toBe('TKN-NEW')
  })

  it('register 带邮箱：email 原样透传', async () => {
    const fetchMock = vi.fn(
      async (url: string, _init?: { body?: string }) =>
        url === REGISTER_URL
          ? jsonRes({ errno: 0, data: null, error: null })
          : jsonRes({ errno: 0, data: { token: 'T', name: 'n' }, error: null }),
    )
    vi.stubGlobal('fetch', fetchMock)
    await register('n', 'p', 'p', 'a@b.com')
    expect(JSON.parse(fetchMock.mock.calls[0]![1]!.body!).email).toBe('a@b.com')
  })

  it('register 失败（如"用户名已存在"）：透出服务端文案，且不再发起 login', async () => {
    const fetchMock = vi.fn(
      async () => jsonRes({ errno: 1003, data: null, error: '用户名已存在' }),
    )
    vi.stubGlobal('fetch', fetchMock)
    await expect(register('dup', 'p', 'p', '')).rejects.toThrow('用户名已存在')
    expect(fetchMock).toHaveBeenCalledTimes(1) // 注册失败即停，不尝试登录
    expect(getToken()).toBe('')
  })

  it('register HTTP 非 2xx：抛 HTTP <status>', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes({ errno: 0, data: null, error: null }, false, 503)))
    await expect(register('a', 'b', 'b', '')).rejects.toThrow('HTTP 503')
    expect(getToken()).toBe('')
  })

  it('findpass 成功：POST base+/findpass 只带 {email}', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: { body?: string }) => jsonRes({ errno: 0, data: null, error: null }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(findpass('a@b.com')).resolves.toBeUndefined()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe(FINDPASS_URL)
    expect(init).toMatchObject({ method: 'POST', headers: { 'Content-Type': 'application/json' } })
    expect(JSON.parse(init!.body!)).toEqual({ email: 'a@b.com' })
  })

  it('findpass 失败：透出服务端文案', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes({ errno: 1, data: null, error: '发送太频繁，请稍后再试' })))
    await expect(findpass('a@b.com')).rejects.toThrow('发送太频繁，请稍后再试')
  })

  it('resetpass 成功：POST base+/resetpass 带 {email,code,pwd,rePwd}', async () => {
    const fetchMock = vi.fn(async (_url: string, _init?: { body?: string }) => jsonRes({ errno: 0, data: null, error: null }))
    vi.stubGlobal('fetch', fetchMock)
    await expect(resetpass('a@b.com', '123456', 'npw', 'npw')).resolves.toBeUndefined()
    const [url, init] = fetchMock.mock.calls[0]!
    expect(url).toBe(RESETPASS_URL)
    expect(init).toMatchObject({ method: 'POST', headers: { 'Content-Type': 'application/json' } })
    expect(JSON.parse(init!.body!)).toEqual({ email: 'a@b.com', code: '123456', pwd: 'npw', rePwd: 'npw' })
  })

  it('resetpass 失败（如"验证码已过期"）：透出服务端文案', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => jsonRes({ errno: 2, data: null, error: '验证码已过期，请重新获取' })))
    await expect(resetpass('a@b.com', '123456', 'npw', 'npw')).rejects.toThrow('验证码已过期，请重新获取')
  })

  it('errno!==0 且无 error 文案：回各自兜底中文', async () => {
    const fail = vi.fn(async () => jsonRes({ errno: 1, data: null, error: null }))
    vi.stubGlobal('fetch', fail)
    await expect(register('a', 'b', 'b', '')).rejects.toThrow('注册失败，请稍后再试')
    await expect(findpass('a@b.com')).rejects.toThrow('发送失败，请稍后再试')
    await expect(resetpass('a@b.com', '1', 'p', 'p')).rejects.toThrow('重置失败，请稍后再试')
  })
})
