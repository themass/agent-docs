/**
 * P3 档案存储单测（spec §21.1/§21.4/§21.7）：升降星接线、幂等、榜单、赛季、JSON 落盘。
 */
import { describe, it, expect } from 'vitest'
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { INITIAL_MMR, SEASON_EPOCH_MS, SEASON_MS, starCap } from '@plane-duel/shared'
import { JsonFileProfileStore, MemoryProfileStore, type ScoringInput } from '../src/profile'

const T0 = SEASON_EPOCH_MS + 1000 // 第 1 赛季内
const input = (over: Partial<ScoringInput> = {}): ScoringInput => ({
  id: 'tbl:0',
  at: T0,
  mode: 'duel',
  preset: 'standard',
  capacity: 2,
  rank: 1,
  hits: 7,
  withBots: false,
  opponentMmr: INITIAL_MMR,
  ...over,
})

describe('MemoryProfileStore：段位接线（§21.2）', () => {
  it('首胜 +1 星并落档案；stats.wins/scoringGames 同步', () => {
    const s = new MemoryProfileStore()
    const r = s.record('p1', input())
    expect(r.delta).toBe(1)
    expect(r.profile.rank.tier).toBe(0)
    expect(r.profile.rank.stars).toBe(1)
    expect(r.profile.stats).toMatchObject({ wins: 1, losses: 0, scoringGames: 1, totalHits: 7, streak: 1 })
  })

  it('三连胜升到新兵', () => {
    const s = new MemoryProfileStore()
    s.record('p1', input({ id: 'a:0' }))
    s.record('p1', input({ id: 'a:1' }))
    const r = s.record('p1', input({ id: 'a:2' }))
    expect(r.profile.rank.tier).toBe(1)
    expect(r.profile.rank.stars).toBe(0)
    expect(r.profile.stats.bestTier).toBe(1)
  })

  it('电脑局只记战绩：delta=0、不动星数、不进 scoringGames', () => {
    const s = new MemoryProfileStore()
    s.record('p1', input({ withBots: true }))
    const r = s.record('p1', input({ id: 'b:0', withBots: true, rank: 2 }))
    expect(r.delta).toBe(0)
    expect(r.profile.rank.stars).toBe(0)
    expect(r.profile.stats).toMatchObject({ scoringGames: 0, totalHits: 14 })
    // 电脑局仍进 recent，并带 withBots 标记
    expect(r.profile.recent[0]).toMatchObject({ id: 'b:0', withBots: true, win: false })
  })

  it('连败计数与垫底保护接线：第 2 败列兵 0 星不再跌，第 3 败保星并清零计数', () => {
    const s = new MemoryProfileStore()
    s.record('p1', input({ id: 'c:0' })) // 1 星
    const l1 = s.record('p1', input({ id: 'c:1', rank: 2 })) // 0 星，连败 1
    expect(l1.delta).toBe(-1)
    const l2 = s.record('p1', input({ id: 'c:2', rank: 2 })) // 列兵垫底保护
    expect(l2.delta).toBe(0)
    expect(l2.profile.rank.lossStreak).toBe(2)
    const l3 = s.record('p1', input({ id: 'c:3', rank: 2 })) // 第 3 败：保星、计数清零
    expect(l3.delta).toBe(0)
    expect(l3.profile.rank.lossStreak).toBe(0)
  })

  it('MMR 随胜负走 Elo：胜升负降，对手越强胜场加分越多', () => {
    const s = new MemoryProfileStore()
    const winWeak = s.record('p1', input({ opponentMmr: INITIAL_MMR - 400 }))
    expect(winWeak.profile.rank.mmr).toBeGreaterThan(INITIAL_MMR)
    const winStrong = s.record('p2', input({ opponentMmr: INITIAL_MMR + 400 }))
    expect(winStrong.profile.rank.mmr - INITIAL_MMR).toBeGreaterThan(winWeak.profile.rank.mmr - INITIAL_MMR)
    const loss = s.record('p3', input({ rank: 2 }))
    expect(loss.profile.rank.mmr).toBeLessThan(INITIAL_MMR)
  })
})

describe('MemoryProfileStore：幂等（§21.7）', () => {
  it('同 id 重放返回原 delta，不重复加星/记账', () => {
    const s = new MemoryProfileStore()
    const first = s.record('p1', input())
    const replay = s.record('p1', input())
    expect(replay.delta).toBe(first.delta)
    expect(replay.profile.rank.stars).toBe(1)
    expect(replay.profile.stats.wins).toBe(1)
    expect(replay.profile.recent).toHaveLength(1)
  })
})

describe('MemoryProfileStore：战绩与统计（§21.4）', () => {
  it('recent 保留最近 20 条、新在前', () => {
    const s = new MemoryProfileStore()
    for (let i = 0; i < 25; i++) s.record('p1', input({ id: `x:${i}`, hits: i }))
    const p = s.get('p1', '', T0)
    expect(p.recent).toHaveLength(20)
    expect(p.recent[0]!.id).toBe('x:24')
    expect(p.recent[19]!.id).toBe('x:5')
    expect(p.stats.totalHits).toBe((0 + 24) * 25 / 2) // 全部 25 局都计入命中
  })

  it('连胜：胜+1 负清零', () => {
    const s = new MemoryProfileStore()
    s.record('p1', input({ id: 'w:0' }))
    s.record('p1', input({ id: 'w:1' }))
    expect(s.get('p1', '', T0).stats.streak).toBe(2)
    s.record('p1', input({ id: 'w:2', rank: 2 }))
    expect(s.get('p1', '', T0).stats.streak).toBe(0)
  })
})

describe('MemoryProfileStore：排行榜（§21.5）', () => {
  it('按 (tier, stars, mmr, wins) 排序；无计分局的玩家不上榜；条目不含 playerId', () => {
    const s = new MemoryProfileStore()
    // u1：三胜 → 新兵 0 星；u2：两胜 → 列兵 2 星；u3：从没计分局
    s.get('u1', '强子', T0)
    s.record('u1', input({ id: 'r:0' }))
    s.record('u1', input({ id: 'r:1', opponentMmr: INITIAL_MMR - 500 })) // mmr 高
    s.record('u1', input({ id: 'r:2' }))
    s.get('u2', '小美', T0)
    s.record('u2', input({ id: 'q:0' }))
    s.record('u2', input({ id: 'q:1' }))
    const { season, entries } = s.leaderboard(50, T0)
    expect(season).toBe(1)
    expect(entries.map((e) => e.nickname)).toEqual(['强子', '小美']) // 段位在前的排前面
    expect(entries[0]!.tier).toBe(1)
    expect(entries[1]!.tier).toBe(0)
    expect(entries.some((e) => 'playerId' in (e as object))).toBe(false)
    // 无计分局者（从没 record）不在列：u3 只被 get 过
    s.get('u3', '观众', T0)
    expect(s.leaderboard(50, T0).entries).toHaveLength(2)
  })
})

describe('MemoryProfileStore：赛季（§21.3）', () => {
  it('resetSeasonAll 跨季降 1 级并返回受影响者；同季二次调用为空', () => {
    const s = new MemoryProfileStore()
    s.record('p1', input({ id: 'a:0' }))
    s.record('p1', input({ id: 'a:1' }))
    s.record('p1', input({ id: 'a:2' })) // 升到新兵 0 星
    const next = SEASON_EPOCH_MS + SEASON_MS + 10
    const touched = s.resetSeasonAll(next)
    expect(touched).toEqual(['p1'])
    const p = s.get('p1', '', next)
    expect(p.rank.tier).toBe(0)
    expect(p.rank.stars).toBe(starCap(0) - 1)
    expect(p.season).toBe(2)
    expect(s.resetSeasonAll(next)).toEqual([])
  })
})

describe('JsonFileProfileStore（§21.1）', () => {
  const dir = mkdtempSync(join(tmpdir(), 'pd-profile-'))
  const file = join(dir, 'sub', 'profiles.json')

  it('flush 落盘，新实例读回段位与战绩', () => {
    const s1 = new JsonFileProfileStore(file)
    s1.record('p1', input())
    s1.record('p1', input({ id: 'b:0', rank: 2, hits: 3 }))
    s1.flush()
    const raw = JSON.parse(readFileSync(file, 'utf8'))
    expect(Object.keys(raw)).toEqual(['p1'])

    const s2 = new JsonFileProfileStore(file)
    const p = s2.get('p1', '', T0)
    expect(p.rank).toMatchObject({ tier: 0, stars: 0 })
    expect(p.stats).toMatchObject({ wins: 1, losses: 1, totalHits: 10 })
    expect(p.recent.map((g) => g.id)).toEqual(['b:0', 'tbl:0'])
  })

  it('文件损坏不炸：空档启动', () => {
    const bad = join(dir, 'bad.json')
    rmSync(bad, { force: true })
    writeFileSync(bad, '{not json')
    const s = new JsonFileProfileStore(bad)
    expect(s.leaderboard(50, T0).entries).toEqual([])
  })

  it('dirty 防抖：窗口内多次改动合并，flush 前文件保持旧内容', async () => {
    const f2 = join(dir, 'debounce.json')
    const s = new JsonFileProfileStore(f2)
    s.record('p1', input())
    s.flush() // 建立初始文件
    s.record('p1', input({ id: 'c:1' })) // 进入防抖窗口
    const mid = JSON.parse(readFileSync(f2, 'utf8'))
    expect(mid.p1.stats.wins).toBe(1) // 还没落盘
    s.flush() // 强制刷
    const after = JSON.parse(readFileSync(f2, 'utf8'))
    expect(after.p1.stats.wins).toBe(2)
  })
})
