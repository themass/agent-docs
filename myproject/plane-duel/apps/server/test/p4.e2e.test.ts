/**
 * P4 端到端（真实 WebSocket + 假时钟，spec §廿二）：
 * - 真人门票局全链路：双方预付 → 成局 → 胜者固定奖励 +80、败者无，余额以 profile 为准
 * - 取消排队退款（服务端 dropQueue 路径）
 * - 掉线退款：关 socket 后重连，档案余额已回补
 * - v4 兼容：不带 ticket 的 queueJoin，queueStatus 不带 ticket 字段
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { createServer, type ServerHandle } from '../src/main'
import { wsClient, type WsClient } from './ws-client'

let fakeNow = 1_700_000_000_000
const fake = { now: (): number => fakeNow }
let srv: ServerHandle

const sleep = (ms = 0) => new Promise<void>((r) => setTimeout(r, ms))

/** 等待消息的同时推进假时钟：匹配成组、回合切换都挂在 tick 上 */
async function driven(c: WsClient, type: string, pred: (m: any) => boolean = () => true, maxTicks = 60): Promise<any> {
  const p = c.next(type, pred, 30_000)
  for (let i = 0; i < maxTicks; i++) {
    const r = await Promise.race([p.then((m) => ({ hit: m as any })), sleep(1).then(() => ({ hit: null }))])
    if (r.hit !== null) return r.hit
    fakeNow += 200
    srv.tick()
  }
  return p
}

async function authClient(playerId: string, nickname: string, token?: string): Promise<WsClient> {
  const c = wsClient(srv.port)
  await c.open()
  c.send({ type: 'auth', playerId, nickname, ...(token !== undefined ? { token } : {}) })
  await c.next('ready')
  return c
}

/** 两名新号以同一门票档实时匹配成局并摆放；返回双方与先手。登录礼 50 → 预付后 0 */
async function ticketMatchUp(idA: string, idB: string): Promise<{ a: WsClient; b: WsClient; first: string }> {
  const a = await authClient(idA, '甲')
  const b = await authClient(idB, '乙')
  a.send({ type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' })
  b.send({ type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' })
  for (const c of [a, b]) {
    const fee = await c.next('coinsChanged', (m) => m.reason === 'ticket-fee')
    expect(fee).toMatchObject({ delta: -50, balance: 0 })
  }
  await driven(a, 'tableState', (m) => m.table.kind === 'match')
  await driven(b, 'tableState', (m) => m.table.kind === 'match')
  a.send({ type: 'placePlane', planes: [{ row: 3, col: 7 }] })
  b.send({ type: 'placePlane', planes: [{ row: 6, col: 2 }] })
  const pc = await driven(a, 'phaseChanged', (m) => m.phase === 'playing')
  expect(pc.turn).toBeTruthy()
  return { a, b, first: pc.turn }
}

beforeAll(async () => {
  srv = await createServer({ port: 0, devMode: false, clock: fake, profileFile: null })
})
afterAll(() => srv.close())

describe('P4 端到端（真实 socket）', () => {
  it('真人门票局：胜者拿 80 固定奖励（profile 85），败者只有完成局 5；顺序 login→fee→game→win', async () => {
    const { a, b, first } = await ticketMatchUp('p4-e2e-win', 'p4-e2e-lose')
    const win = first === 'p4-e2e-win' ? a : b
    const lose = first === 'p4-e2e-win' ? b : a
    win.send({ type: 'fire', ...(first === 'p4-e2e-win' ? { row: 6, col: 2 } : { row: 3, col: 7 }) })

    const go = await driven(win, 'gameOver')
    expect(go.result.reason).toBe('head')

    const pw = await win.next('profile', (m) => m.profile.stats.scoringGames === 1)
    expect(pw.profile.coins).toBe(85) // 50−50+5+80；profile 是余额权威且最后推
    const winReasons = win.log.filter((m) => m.type === 'coinsChanged').map((m) => m.reason)
    expect(winReasons).toEqual(['login', 'ticket-fee', 'game', 'ticket-win'])

    const pl = await lose.next('profile', (m) => m.profile.stats.scoringGames === 1)
    expect(pl.profile.coins).toBe(5) // 50−50+5，没有门票奖励
    expect(lose.log.some((m) => m.reason === 'ticket-win')).toBe(false)

    a.close()
    b.close()
  }, 60_000)

  it('取消排队：门票原路退回（dropQueue 路径）', async () => {
    const c = await authClient('p4-e2e-leave', '甲')
    c.send({ type: 'queueJoin', capacity: 4, preset: 'standard', ticket: 'standard' })
    const fee = await c.next('coinsChanged', (m) => m.reason === 'ticket-fee')
    expect(fee).toMatchObject({ delta: -50, balance: 0 })
    c.send({ type: 'queueLeave' })
    const refund = await c.next('coinsChanged', (m) => m.reason === 'ticket-refund')
    expect(refund).toMatchObject({ delta: 50, balance: 50 })
    c.close()
  }, 60_000)

  it('排队中掉线：直接关 socket 也退款——重连后档案余额已回补', async () => {
    const c = await authClient('p4-e2e-drop', '甲')
    // 服务端签发的 token：重连必须带上（评审 C2 身份校验）
    const token = c.log.find((m) => m.type === 'ready').token
    c.send({ type: 'queueJoin', capacity: 4, preset: 'standard', ticket: 'standard' })
    await c.next('coinsChanged', (m) => m.reason === 'ticket-fee')
    c.close()
    await sleep(80) // 服务端 close 事件 → dropQueue → 退款入账（推给已断开的连接，只落档案）

    const c2 = await authClient('p4-e2e-drop', '甲', token)
    c2.send({ type: 'profileRequest' })
    const p = await c2.next('profile')
    expect(p.profile.coins).toBe(50)
    c2.close()
  }, 60_000)

  it('v4 兼容：不带 ticket 的 queueJoin → queueStatus 无 ticket 字段（老客户端深比较）', async () => {
    const c = await authClient('p4-e2e-v4', '甲')
    c.send({ type: 'queueJoin', capacity: 2, preset: 'standard' })
    const qs = await driven(c, 'queueStatus')
    expect(qs.capacity).toBe(2)
    expect('ticket' in qs).toBe(false)
    c.send({ type: 'queueLeave' })
    c.close()
  }, 60_000)
})
