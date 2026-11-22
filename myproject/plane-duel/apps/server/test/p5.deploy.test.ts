/**
 * P5 部署加固（spec §廿三）：优雅停机退款（Hub.shutdown）、/healthz 探活、close 不再挂死。
 */
import { unlinkSync } from 'node:fs'
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { createServer, type ServerHandle } from '../src/main'
import { mkHub } from './hub-helpers'
import { wsClient } from './ws-client'

describe('Hub.shutdown 停机退款（§廿三.1.1）', () => {
  it('排队中已付门票：shutdown 原路退回', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.send('s1', { type: 'queueJoin', capacity: 4, preset: 'standard', ticket: 'standard' })
    expect(h.last('s1', 'coinsChanged').balance).toBe(0) // 登录 50 − 票 50
    h.hub.shutdown()
    const refund = h.recv('s1').filter((m: any) => m.type === 'coinsChanged').at(-1) as any
    expect(refund).toMatchObject({ reason: 'ticket-refund', delta: 50, balance: 50 })
    expect(h.hub.profileStore.get('alice', 'alice', 1_000_000).coins.balance).toBe(50)
  })

  it('已记桌未开打：按入座名单全额退', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' })
    // 成局即记桌（settleQueueIntoTable），首局还没打
    expect(h.hub.profileStore.get('alice', 'alice', 1_000_000).coins.balance).toBe(0)
    h.hub.shutdown()
    for (const id of ['alice', 'bob']) {
      expect(h.hub.profileStore.get(id, id, 1_000_000).coins.balance).toBe(50)
    }
  })

  it('幂等：shutdown 重复调用不双退', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.send('s1', { type: 'queueJoin', capacity: 4, preset: 'standard', ticket: 'standard' })
    h.hub.shutdown()
    h.hub.shutdown()
    expect(h.hub.profileStore.get('alice', 'alice', 1_000_000).coins.balance).toBe(50)
    const refunds = h.recv('s1').filter((m: any) => m.reason === 'ticket-refund')
    expect(refunds).toHaveLength(1)
  })

  it('免费场排队不受影响：无退款也无报错', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    h.hub.shutdown() // 不应抛
    expect(h.hub.profileStore.get('alice', 'alice', 1_000_000).coins.balance).toBe(50)
  })
})

describe('服务进程：/healthz 与优雅 close（§廿三.1.2）', () => {
  let srv: ServerHandle
  beforeAll(async () => {
    srv = await createServer({ port: 0, devMode: false, profileFile: null })
  })
  afterAll(() => srv.close())

  it('GET /healthz → 200 ok；其它路径 404', async () => {
    const r = await fetch(`http://127.0.0.1:${srv.port}/healthz`)
    expect(r.status).toBe(200)
    expect(await r.text()).toBe('ok')
    const r404 = await fetch(`http://127.0.0.1:${srv.port}/anything`)
    expect(r404.status).toBe(404)
  })

  it('close()：带活连接也能在 2 秒内完成（主动断连，不等排空）', async () => {
    const srv2 = await createServer({ port: 0, devMode: false, profileFile: null })
    const c = wsClient(srv2.port)
    await c.open()
    c.send({ type: 'auth', playerId: 'p5-close', nickname: '甲' })
    await c.next('ready')
    // 旧实现：wss.close 等半开连接排空会挂到 Docker 超时；新实现先 1001 断开全部
    const t0 = Date.now()
    const raced = await Promise.race([
      srv2.close().then(() => 'done' as const),
      new Promise<'hang'>((r) => setTimeout(() => r('hang'), 2_000)),
    ])
    expect(raced).toBe('done')
    expect(Date.now() - t0).toBeLessThan(2_000)
  }, 10_000)
})

describe('档案写盘回环（评审 P5 #3：头条验收目标要有自动化）', () => {
  it('登录礼 → close() → 重新装载：余额从磁盘回来（重启不丢金币）', async () => {
    const file = `/tmp/p5-roundtrip-${Date.now()}.json`
    const srv = await createServer({ port: 0, devMode: false, profileFile: file })
    const c = wsClient(srv.port)
    await c.open()
    c.send({ type: 'auth', playerId: 'p5-rt', nickname: '甲' })
    await c.next('ready')
    await srv.close() // 优雅停机：close 末尾 flush（评审 #1 时序）
    // 全新进程语义：另开一个服务读同一文件
    const srv2 = await createServer({ port: 0, devMode: false, profileFile: file })
    const c2 = wsClient(srv2.port)
    await c2.open()
    c2.send({ type: 'auth', playerId: 'p5-rt', nickname: '甲' })
    const p = await c2.next('profile')
    expect(p.profile.coins).toBe(50) // 登录礼从磁盘恢复，且同日幂等不重发
    await srv2.close()
    c.close()
    unlinkSync(file)
  }, 15_000)
})
