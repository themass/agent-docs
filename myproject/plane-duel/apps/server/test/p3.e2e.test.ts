/**
 * P3 端到端（真实 WebSocket + 假时钟，spec §21）：
 * - 实时匹配无电脑成局：双方收到 profile + rankChanged，段位榜走真实链路
 * - 败方对局中离开（match 桌即关桌清座）：胜者计分不丢——
 *   座位快照竞态（afterEngine 里 close() 先清座，Hub 后读到空数组）的回归测试
 * - 跨赛季 tick：在线者收到 rankChanged(season-reset)，且不重复
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest'
import { SEASON_EPOCH_MS, SEASON_MS } from '@plane-duel/shared'
import { createServer, type ServerHandle } from '../src/main'
import { wsClient, type WsClient } from './ws-client'

let fakeNow = 1_700_000_000_000 // 钳在第 1 赛季（SEASON_EPOCH_MS 之前）
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

async function authClient(playerId: string, nickname: string): Promise<WsClient> {
  const c = wsClient(srv.port)
  await c.open()
  c.send({ type: 'auth', playerId, nickname })
  await c.next('ready')
  return c
}

/** 两名新号实时匹配成局（同 MMR 桶 → 即时配对）并摆放；返回双方与先手 */
async function matchUp(idA: string, idB: string): Promise<{ a: WsClient; b: WsClient; first: string }> {
  const a = await authClient(idA, '甲')
  const b = await authClient(idB, '乙')
  a.send({ type: 'queueJoin', capacity: 2, preset: 'standard' })
  b.send({ type: 'queueJoin', capacity: 2, preset: 'standard' })
  // 成桌靠 tick：等双方各拿到 match 桌快照
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

describe('P3 端到端（真实 socket）', () => {
  it('实时匹配无电脑打完一局：胜者 +1 星、败者垫底保护，双方都收到 profile 与 rankChanged；段位榜两人上榜', async () => {
    const { a, b, first } = await matchUp('p3-e2e-win', 'p3-e2e-lose')
    const win = first === 'p3-e2e-win' ? a : b
    const lose = first === 'p3-e2e-win' ? b : a
    // 先手直打对方机头（各自棋盘，坐标已知）
    win.send({ type: 'fire', ...(first === 'p3-e2e-win' ? { row: 6, col: 2 } : { row: 3, col: 7 }) })

    const go = await driven(win, 'gameOver')
    expect(go.result.reason).toBe('head')

    const rcW = await win.next('rankChanged')
    expect(rcW).toMatchObject({ delta: 1, reason: 'scoring', rank: { tier: 0, stars: 1 } })
    // auth 时推过一份空档案：按内容取局后那份
    const pw = await win.next('profile', (m) => m.profile.stats.scoringGames === 1)
    expect(pw.profile.stats).toMatchObject({ wins: 1, losses: 0, scoringGames: 1 })
    expect(pw.profile.recent[0]).toMatchObject({ win: true, mode: 'duel' })

    const rcL = await lose.next('rankChanged')
    expect(rcL).toMatchObject({ delta: 0, reason: 'scoring', rank: { tier: 0, stars: 0, lossStreak: 1 } })
    const pl = await lose.next('profile', (m) => m.profile.stats.scoringGames === 1)
    expect(pl.profile.stats).toMatchObject({ wins: 0, losses: 1, scoringGames: 1 })
    expect(pl.profile.recent[0]).toMatchObject({ win: false })

    win.send({ type: 'rankListRequest' })
    const rl = await win.next('rankList')
    expect(rl.season).toBe(1)
    expect(rl.entries).toHaveLength(2)
    expect(rl.entries[0]).toMatchObject({ pos: 1, tier: 0, stars: 1, wins: 1 })
    expect(JSON.stringify(rl.entries)).not.toContain('p3-e2e') // 条目不含 playerId

    a.close()
    b.close()
  }, 60_000)

  it('败方对局中离开 → 关桌清座，胜者仍收到 +1 星（座位快照竞态回归）', async () => {
    const { a, b, first } = await matchUp('p3-e2e-keep', 'p3-e2e-bail')
    const win = first === 'p3-e2e-keep' ? a : b
    const bail = first === 'p3-e2e-keep' ? b : a
    // 不打了：中途离开判对方胜。match 桌有人离开会立刻关桌清空座位——
    // 计分必须用 afterEngine 时刻的真人快照，否则胜者一分都拿不到（浏览器实测抓到过）
    bail.send({ type: 'leaveRoom' })

    const go = await driven(win, 'gameOver')
    expect(go.result.reason).toBe('forfeit')
    const rc = await win.next('rankChanged')
    expect(rc).toMatchObject({ delta: 1, reason: 'scoring', rank: { tier: 0, stars: 1 } })
    const pw = await win.next('profile', (m) => m.profile.stats.scoringGames === 1)
    expect(pw.profile.stats).toMatchObject({ wins: 1, scoringGames: 1 })

    // 离开者不计分也不记战绩（P3 首版口径）
    await sleep(50)
    expect(bail.log.some((m) => m.type === 'rankChanged')).toBe(false)
    // 关桌告别消息照发
    expect(win.log.some((m) => m.type === 'roomClosed')).toBe(true)

    a.close()
    b.close()
  }, 60_000)

  it('跨赛季 tick：在线者收到 rankChanged(season-reset) delta 0；再 tick 不重复', async () => {
    const { a, b } = await matchUp('p3-e2e-sea1', 'p3-e2e-sea2')
    // 直接跨到第 2 赛季起点之后
    fakeNow = SEASON_EPOCH_MS + SEASON_MS + 1
    srv.tick()
    const rc = await driven(a, 'rankChanged', (m) => m.reason === 'season-reset')
    expect(rc).toMatchObject({ delta: 0, reason: 'season-reset', rank: { tier: 0 } })
    const pw = await a.next('profile', (m) => m.profile.season === 2)
    expect(pw.profile.season).toBe(2)
    expect(b.log.some((m) => m.type === 'rankChanged' && m.reason === 'season-reset')).toBe(true)

    fakeNow += 1000
    srv.tick()
    await sleep(50)
    const after = a.log.filter((m) => m.type === 'rankChanged' && m.reason === 'season-reset').length
    expect(after).toBe(1) // 不重复重置

    a.close()
    b.close()
  }, 60_000)
})
