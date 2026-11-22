/**
 * Hub P3 接线（spec §21.2/§21.4/§21.6/§21.7）：auth 推档案、profileRequest/rankListRequest、
 * 计分局判定与幂等、赛季跨季推送。全部走假时钟，无真实 socket。
 * 有电脑局打到自然结束的完整计分路径由 p3.e2e.test.ts 覆盖。
 */
import { describe, it, expect } from 'vitest'
import { INITIAL_MMR, SEASON_EPOCH_MS, SEASON_MS } from '@plane-duel/shared'
import { BOT_FILL_AFTER_MS } from '../src/matchmaking'
import { MemoryProfileStore } from '../src/profile'
import { mkHub } from './hub-helpers'

/**
 * 打完一局 2 人匹配房（无电脑）：排队成桌 → 摆放 → 先手打掉对方机头。
 * 先手由随机决定，所以胜负按引擎实际 turn 判定，返回两人的会话与档案归属。
 */
function playMatchDuel(h: ReturnType<typeof mkHub>) {
  h.auth('s1', 'alice')
  h.auth('s2', 'bob')
  h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
  h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard' })
  const code = h.tableOf('s1').roomCode
  h.send('s1', { type: 'placePlane', planes: [{ row: 3, col: 7 }] })
  h.send('s2', { type: 'placePlane', planes: [{ row: 6, col: 2 }] })
  const engine = h.hub.getTable(code)!.engine!
  const first = engine.view('alice').turn // 'alice' | 'bob'
  const [winSid, target] = first === 'alice' ? ['s1', { row: 6, col: 2 }] : ['s2', { row: 3, col: 7 }]
  h.send(winSid, { type: 'fire', ...target })
  const loseSid = winSid === 's1' ? 's2' : 's1'
  return { code, winSid, loseSid }
}

describe('Hub P3：档案推送与请求', () => {
  it('auth 之后立刻收到 profile（匿名档案自动创建，§21.9）', () => {
    const h = mkHub()
    h.auth('s1', 'alice', undefined, '小爱')
    const p = h.last('s1', 'profile')
    expect(p).toBeDefined()
    expect(p.profile).toMatchObject({
      nickname: '小爱',
      rank: { tier: 0, stars: 0, lossStreak: 0 },
      season: 1,
      stats: { wins: 0, losses: 0, scoringGames: 0 },
    })
    expect(p.profile.recent).toEqual([])
  })

  it('profileRequest 回最新档案', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    const before = h.recv('s1').filter((m: any) => m.type === 'profile').length
    h.send('s1', { type: 'profileRequest' })
    const after = h.recv('s1').filter((m: any) => m.type === 'profile').length
    expect(after).toBe(before + 1)
    expect(h.last('s1', 'profile').profile.nickname).toBe('玩家')
  })

  it('rankListRequest：无计分局返回空榜（带赛季号），不报错', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.send('s1', { type: 'rankListRequest' })
    expect(h.last('s1', 'rankList')).toMatchObject({ season: 1, entries: [] })
  })

  it('rankListRequest：计分局之后两人都上榜；条目含 pos/nickname/tier/stars/wins，不含 playerId', () => {
    const h = mkHub()
    const { winSid } = playMatchDuel(h)
    h.send('s1', { type: 'rankListRequest' })
    const rl = h.last('s1', 'rankList')
    expect(rl.entries).toHaveLength(2)
    const rows = rl.entries as any[]
    expect(rows.map((e) => e.pos)).toEqual([1, 2])
    // 胜者 1 星在前
    expect(rows[0]).toMatchObject({ tier: 0, stars: 1, wins: 1 })
    expect(rows.every((e) => !('playerId' in e) && !('roomCode' in e))).toBe(true)
    expect(winSid).toBeTruthy()
  })

  it('setNickname 同步进档案（榜单昵称跟着改）', () => {
    const h = mkHub()
    playMatchDuel(h)
    h.send('s1', { type: 'setNickname', nickname: '大鹰' })
    expect(h.last('s1', 'profile').profile.nickname).toBe('大鹰')
    h.send('s1', { type: 'rankListRequest' })
    expect((h.last('s1', 'rankList').entries as any[]).some((e) => e.nickname === '大鹰')).toBe(true)
  })
})

describe('Hub P3：计分局判定（§21.2）', () => {
  it('匹配 2 人无电脑：胜者 +1 星；败者列兵 0 星垫底保护 delta=0（连败计数照走），双方收到 rankChanged 与新 profile', () => {
    const h = mkHub()
    const { winSid, loseSid } = playMatchDuel(h)
    expect(h.last(winSid, 'rankChanged')).toMatchObject({ delta: 1, rank: { tier: 0, stars: 1 }, reason: 'scoring' })
    // 新号首败：列兵 0 星不跌（rank.ts 垫底保护），但仍是计分局——计数与统计都走
    expect(h.last(loseSid, 'rankChanged')).toMatchObject({ delta: 0, rank: { tier: 0, stars: 0, lossStreak: 1 }, reason: 'scoring' })
    expect(h.last(winSid, 'profile').profile.stats).toMatchObject({ wins: 1, losses: 0, scoringGames: 1 })
    expect(h.last(loseSid, 'profile').profile.stats).toMatchObject({ wins: 0, losses: 1, scoringGames: 1 })
    // 战绩进 recent：胜局 win=true
    expect(h.last(winSid, 'profile').profile.recent[0]).toMatchObject({ win: true, mode: 'duel', preset: 'standard' })
  })

  it('对局中途离开的真人：不计分也不记战绩（P3 首版口径）', () => {
    const h = mkHub({ botFillMs: BOT_FILL_AFTER_MS })
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    h.send('s1', { type: 'queueJoin', capacity: 4, preset: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 4, preset: 'standard' })
    h.advance(45_000) // 补位成桌：2 真人 + 2 电脑
    expect(h.tableOf('s1').seats.filter((s: any) => s?.bot)).toHaveLength(2)
    h.send('s1', { type: 'leaveRoom' })
    h.send('s2', { type: 'leaveRoom' })
    expect(h.recv('s1').some((m: any) => m.type === 'rankChanged')).toBe(false)
    expect(h.recv('s2').some((m: any) => m.type === 'rankChanged')).toBe(false)
    // 档案停在 auth 时的样子：离开者不记账
    expect(h.last('s1', 'profile').profile.stats).toMatchObject({ scoringGames: 0, totalHits: 0 })
    expect(h.last('s1', 'profile').profile.recent).toEqual([])
  })

  it('练习局提前退出：不推 rankChanged、不记战绩；好友房完全不进档案', () => {
    const h = mkHub()
    h.auth('s1', 'solo')
    h.send('s1', { type: 'createPractice', capacity: 2, preset: 'beginner' })
    h.send('s1', { type: 'leaveRoom' }) // 判电脑胜、桌子随关
    expect(h.recv('s1').some((m: any) => m.type === 'rankChanged')).toBe(false)
    expect(h.last('s1', 'profile').profile.recent).toEqual([])

    const h2 = mkHub()
    const { code } = h2.startDuel()
    h2.finishDuel(code)
    expect(h2.recv('s1').some((m: any) => m.type === 'rankChanged')).toBe(false)
    expect(h2.recv('s2').some((m: any) => m.type === 'rankChanged')).toBe(false)
    // profile 只有 auth 时那一份空档案
    expect(h2.recv('s1').filter((m: any) => m.type === 'profile')).toHaveLength(1)
    expect(h2.last('s1', 'profile').profile.stats.scoringGames).toBe(0)
  })

  it('gameOver 重放不加星：store 按 tableId:gamesPlayed 幂等（§21.7）', () => {
    const store = new MemoryProfileStore(() => 1_000_000)
    const h = mkHub({ profiles: store })
    const { winSid } = playMatchDuel(h)
    // 先手由随机源决定：按实际胜者取档案（winSid 与 playerId 的对应见 auth 调用顺序）
    const winnerId = winSid === 's1' ? 'alice' : 'bob'
    const p0 = store.get(winnerId, '', 1_000_000)
    expect(p0.recent).toHaveLength(1)
    const again = store.record(winnerId, {
      id: p0.recent[0]!.id,
      at: 1_000_000,
      mode: 'duel',
      preset: 'standard',
      capacity: 2,
      rank: 1,
      hits: 1,
      withBots: false,
      opponentMmr: INITIAL_MMR,
    })
    expect(again.delta).toBe(1) // 报本局原有的变化
    const p1 = store.get(winnerId, '', 1_000_000)
    expect(p1.rank.stars).toBe(p0.rank.stars) // 但不再加
    expect(p1.stats.wins).toBe(1)
    expect(p1.recent).toHaveLength(1)
  })
})

describe('Hub P3：赛季跨季（§21.3）', () => {
  it('tick 跨季：在线者收到 rankChanged(season-reset) 与新 profile；列兵段位保持', () => {
    const h = mkHub()
    playMatchDuel(h) // 有人 +1 星
    // 假时钟起于 1_000_000（钳在第 1 赛季）；直接跨到第 2 赛季起点之后
    h.advance(SEASON_EPOCH_MS + SEASON_MS + 1 - 1_000_000)
    const rc = [...h.recv('s1')].reverse().find((m: any) => m.type === 'rankChanged') as any
    expect(rc).toBeDefined()
    expect(rc.reason).toBe('season-reset')
    expect(rc.delta).toBe(0)
    expect(rc.rank.tier).toBe(0) // 列兵：赛季重置保持段位与星数（spec §21.3）
    expect(h.last('s1', 'profile').profile.season).toBe(2)
    // 再 tick 不重复重置
    const before = h.recv('s1').filter((m: any) => m.type === 'rankChanged').length
    h.advance(1000)
    expect(h.recv('s1').filter((m: any) => m.type === 'rankChanged').length).toBe(before)
  })
})
