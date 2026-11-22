/** 段位纯函数（spec §21.2）：升降星、保星、晋级、Elo、赛季、分桶 */
import { describe, it, expect } from 'vitest'
import {
  INITIAL_MMR,
  MMR_BUCKET,
  SEASON_EPOCH_MS,
  SEASON_MS,
  TIER_MARSHAL,
  applyOutcome,
  eloDelta,
  eloExpected,
  initialRank,
  matchRelaxGate,
  mmrBucket,
  resetSeason,
  seasonNumber,
  starCap,
  tierLabel,
} from '../src'

describe('段位表', () => {
  it('列兵/新兵 3 星，其余（含准将）5 星，元帅无上限', () => {
    expect([0, 1, 2, 3, 4, 5, 6].map(starCap)).toEqual([3, 3, 5, 5, 5, 5, 5])
    expect(starCap(TIER_MARSHAL)).toBe(Infinity)
    expect(tierLabel(0)).toBe('列兵')
    expect(tierLabel(TIER_MARSHAL)).toBe('元帅')
  })
})

describe('applyOutcome 星数', () => {
  const r = (tier: number, stars: number, lossStreak = 0) => ({ tier, stars, mmr: INITIAL_MMR, lossStreak })

  it('胜 +1 星；星满晋级且新段 0 星', () => {
    expect(applyOutcome(r(0, 0), 'win', 1200).state).toMatchObject({ tier: 0, stars: 1, lossStreak: 0 })
    expect(applyOutcome(r(0, 2), 'win', 1200).state).toMatchObject({ tier: 1, stars: 0 })
    expect(applyOutcome(r(5, 4), 'win', 1200).state).toMatchObject({ tier: 6, stars: 0 })
  })
  it('元帅胜只加星不晋级', () => {
    expect(applyOutcome(r(TIER_MARSHAL, 9), 'win', 1200).state).toMatchObject({ tier: TIER_MARSHAL, stars: 10 })
  })
  it('负 −1 星；0 星降到上一级满星', () => {
    expect(applyOutcome(r(3, 2), 'loss', 1200).state).toMatchObject({ tier: 3, stars: 1, lossStreak: 1 })
    expect(applyOutcome(r(3, 0), 'loss', 1200).state).toMatchObject({ tier: 2, stars: starCap(2) - 1 })
  })
  it('列兵 0 星不跌（垫底保护）', () => {
    expect(applyOutcome(r(0, 0), 'loss', 1200).state).toMatchObject({ tier: 0, stars: 0 })
  })
  it('晋级局（星满）失败不降级：星数下跌永不跨段，跌段只发生在 0 星且非保星', () => {
    // 星满状态输棋 → 星 -1、段位不动
    expect(applyOutcome(r(2, 4), 'loss', 1200).state).toMatchObject({ tier: 2, stars: 3 })
  })
  it('保星局：连败第 3 场不扣星，计数器清零；之后再连败 3 场再保一次', () => {
    let s = r(2, 1)
    s = applyOutcome(s, 'loss', 1200).state // 1→0, streak 1
    expect(s).toMatchObject({ stars: 0, lossStreak: 1 })
    s = applyOutcome(s, 'loss', 1200).state // 0 星不跌段？会跌——先验证跌段
    expect(s.tier).toBe(1)
    expect(s.lossStreak).toBe(2)
    const before = { ...s }
    const after = applyOutcome(s, 'loss', 1200).state // 第 3 败：保星
    expect(after).toMatchObject({ tier: before.tier, stars: before.stars, lossStreak: 0 })
  })
  it('胜场清零连败计数', () => {
    expect(applyOutcome(r(2, 2, 2), 'win', 1200).state.lossStreak).toBe(0)
  })
  it('delta 与实际星序变化一致（元帅按星数）', () => {
    for (const s of [r(0, 0), r(0, 2), r(3, 0), r(TIER_MARSHAL, 5)]) {
      expect(applyOutcome(s, 'win', 1200).delta).toBe(1)
      const l = applyOutcome(s, 'loss', 1200)
      expect([-1, 0]).toContain(l.delta)
    }
  })
})

describe('Elo', () => {
  it('同分期望 0.5；高打低赢分少、输分多', () => {
    expect(eloExpected(1200, 1200)).toBeCloseTo(0.5)
    expect(eloDelta(1400, 1200, 1)).toBeLessThan(16)
    expect(eloDelta(1400, 1200, 0)).toBeLessThan(-16)
    expect(eloDelta(1200, 1400, 1)).toBeGreaterThan(16)
  })
  it('applyOutcome 同步更新 mmr', () => {
    const a = applyOutcome(initialRank(), 'win', 1400)
    expect(a.state.mmr).toBeGreaterThan(INITIAL_MMR)
    expect(a.state.mmr - INITIAL_MMR).toBe(eloDelta(INITIAL_MMR, 1400, 1))
  })
  it('晋级局：Elo 之外同向微调 +40（spec §21.2 显示壳修正）', () => {
    // 列兵 2 星（cap 3）取胜 → 升新兵 0 星
    const r = applyOutcome({ tier: 0, stars: 2, mmr: INITIAL_MMR, lossStreak: 0 }, 'win', INITIAL_MMR)
    expect(r.state.tier).toBe(1)
    expect(r.state.stars).toBe(0)
    expect(r.state.mmr).toBe(INITIAL_MMR + eloDelta(INITIAL_MMR, INITIAL_MMR, 1) + 40)
    // 非晋级胜不加 40
    const p = applyOutcome({ tier: 0, stars: 0, mmr: INITIAL_MMR, lossStreak: 0 }, 'win', INITIAL_MMR)
    expect(p.state.mmr).toBe(INITIAL_MMR + eloDelta(INITIAL_MMR, INITIAL_MMR, 1))
  })
})

describe('赛季', () => {
  it('epoch 当刻是第 1 季，满 4 周进第 2 季', () => {
    expect(seasonNumber(SEASON_EPOCH_MS)).toBe(1)
    expect(seasonNumber(SEASON_EPOCH_MS + SEASON_MS - 1)).toBe(1)
    expect(seasonNumber(SEASON_EPOCH_MS + SEASON_MS)).toBe(2)
  })
  it('resetSeason：降 1 级满星，元帅降到准将满星；MMR 保留、连败清零', () => {
    expect(resetSeason({ tier: 3, stars: 2, mmr: 1337, lossStreak: 2 })).toEqual({
      tier: 2, stars: starCap(2) - 1, mmr: 1337, lossStreak: 0,
    })
    expect(resetSeason({ tier: TIER_MARSHAL, stars: 42, mmr: 2000, lossStreak: 1 })).toEqual({
      tier: TIER_MARSHAL - 1, stars: starCap(TIER_MARSHAL - 1) - 1, mmr: 2000, lossStreak: 0,
    })
    expect(resetSeason(initialRank())).toEqual(initialRank())
  })
})

describe('MMR 分桶', () => {
  it('120 宽；matchRelaxGate：同桶不限时，跨桶按桶距逐级放宽（gap×15s），不再永不放行', () => {
    expect(mmrBucket(1200)).toBe(mmrBucket(1250))
    expect(mmrBucket(1200)).not.toBe(mmrBucket(1500))
    expect(matchRelaxGate(1200, 1250, 14_000)).toBe(true) // 同桶不限时
    expect(matchRelaxGate(1200, 1310, 14_000)).toBe(false) // 相邻桶未超时
    expect(matchRelaxGate(1200, 1310, 16_000)).toBe(true) // 相邻桶已放宽
    // 隔多桶随时长升级放行：1200(桶10) vs 1600(桶13) gap=3 → 等满 3×15s 放行；
    // 闸门必须随等待升级，否则满员不兼容队列饿死
    expect(matchRelaxGate(1200, 1600, 44_999)).toBe(false)
    expect(matchRelaxGate(1200, 1600, 45_000)).toBe(true)
  })
})
