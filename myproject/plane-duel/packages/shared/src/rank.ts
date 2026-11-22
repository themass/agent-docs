/**
 * 段位系统（spec §21.2）：星制 + 隐藏 MMR 双轨，纯函数。
 *
 * 服务端只存 RankState 并接线；升降星、Elo、赛季重置全部在这里，可单测。
 * MMR 从不下发给客户端（星数是显示壳，匹配按 MMR）。
 */

export const TIERS: readonly string[] = ['列兵', '新兵', '少尉', '上尉', '少校', '上校', '准将', '元帅']
export const TIER_MARSHAL = 7 // 元帅无星数上限，按星数排名
const STAR_CAPS: readonly number[] = [3, 3, 5, 5, 5, 5, 5, 5] // 下标 = tier；元帅的值不用

/** 该段位的星数上限（stars ∈ [0, cap)；元帅 Infinity） */
export function starCap(tier: number): number {
  return tier >= TIER_MARSHAL ? Infinity : STAR_CAPS[tier] ?? 5
}

export function tierLabel(tier: number): string {
  return TIERS[Math.max(0, Math.min(TIER_MARSHAL, tier))]!
}

export type RankState = { tier: number; stars: number; mmr: number; lossStreak: number }

export const INITIAL_MMR = 1200

export function initialRank(): RankState {
  return { tier: 0, stars: 0, mmr: INITIAL_MMR, lossStreak: 0 }
}

// ---------------------------------------------------------------- Elo

export const ELO_K = 32

/** 期望胜率（标准 Elo 公式） */
export function eloExpected(mmr: number, opponentMmr: number): number {
  return 1 / (1 + 10 ** ((opponentMmr - mmr) / 400))
}

/** K=32 的 Elo 增量，四舍五入 */
export function eloDelta(mmr: number, opponentMmr: number, score: 0 | 1): number {
  return Math.round(ELO_K * (score - eloExpected(mmr, opponentMmr)))
}

// ---------------------------------------------------------------- 升降星

export type Outcome = 'win' | 'loss'
export type RankApply = { state: RankState; delta: number }

/**
 * 一局计分局的星数结算：
 * - 胜：+1 星；星满晋级、新段 0 星；元帅无上限
 * - 负：−1 星；0 星降一级并落到满星；列兵 0 星不跌（垫底保护）
 * - 晋级局失败不降级：降段只会发生在 0 星时，星数下跌本身永不跨段
 * - 保星局：连败满 3 场的那一败不扣星，计数器随后清零（每 3 连败保一次）
 *
 * MMR 同步按对手 MMR 走 Elo（列兵局给初始分对手当基准；对手 MMR 由服务端传入）。
 */
export function applyOutcome(prev: RankState, outcome: Outcome, opponentMmr: number): RankApply {
  if (outcome === 'win') {
    const state: RankState = {
      tier: prev.tier,
      stars: prev.stars,
      mmr: prev.mmr + eloDelta(prev.mmr, opponentMmr, 1),
      lossStreak: 0,
    }
    if (prev.tier >= TIER_MARSHAL) state.stars = prev.stars + 1
    else if (prev.stars + 1 >= starCap(prev.tier)) {
      state.tier = prev.tier + 1
      state.stars = 0
      // 升段同向微调（spec §21.2）：段位是 MMR 的显示壳，晋级说明被低估，MMR 补 40
      state.mmr += 40
    } else state.stars = prev.stars + 1
    return { state, delta: 1 }
  }

  const mmr = prev.mmr + eloDelta(prev.mmr, opponentMmr, 0)
  const lossStreak = prev.lossStreak + 1
  // 保星局：连败到第 3 场不扣星，计数器清零（之后每 3 连败再保一次）
  if (lossStreak >= 3) return { state: { tier: prev.tier, stars: prev.stars, mmr, lossStreak: 0 }, delta: 0 }

  if (prev.stars > 0) return { state: { tier: prev.tier, stars: prev.stars - 1, mmr, lossStreak }, delta: -1 }
  if (prev.tier === 0) return { state: { tier: 0, stars: 0, mmr, lossStreak }, delta: 0 }
  return { state: { tier: prev.tier - 1, stars: starCap(prev.tier - 1) - 1, mmr, lossStreak }, delta: -1 }
}

// ---------------------------------------------------------------- 赛季

/** 第 1 赛季起点（UTC，避开本地时区歧义） */
export const SEASON_EPOCH_MS = Date.UTC(2026, 10, 23)
export const SEASON_MS = 4 * 7 * 24 * 3600 * 1000 // 4 周

export function seasonNumber(now: number): number {
  return Math.max(1, 1 + Math.floor((now - SEASON_EPOCH_MS) / SEASON_MS))
}

/**
 * 新赛季：降 1 级、满星起步（元帅降到准将满星）。
 * 已在最低段（列兵）：段位星数都保持原样——0 段没有"降 1 级"，也白送满星。
 * MMR 保留（匹配质量连续），连败清零。
 */
export function resetSeason(prev: RankState): RankState {
  if (prev.tier === 0) return { ...prev, lossStreak: 0 }
  const tier = prev.tier - 1
  return { tier, stars: starCap(tier) - 1, mmr: prev.mmr, lossStreak: 0 }
}

// ---------------------------------------------------------------- 匹配分桶

/** MMR 分桶（spec §21.2 ±120）：同桶优先相遇 */
export const MMR_BUCKET = 120
/** 等待超过这个时长后放开相邻桶 */
export const MATCH_RELAX_MS = 15_000

export function mmrBucket(mmr: number): number {
  return Math.round(mmr / MMR_BUCKET)
}

/**
 * 匹配放行判定：同桶立即放行；跨桶按桶距逐级放宽——每多隔一桶多等一份
 * MATCH_RELAX_MS（相邻 15s、隔两桶 30s、隔三桶 45s…）。
 * 早期把远桶判成"永不放行"，满员且不兼容的队列会既不成组也不补位，
 * 所有人饿死在队里；放宽封顶改为随时长线性升级，保证一定能配上。
 */
export function matchRelaxGate(mmrA: number, mmrB: number, waitedMs: number): boolean {
  const gap = Math.abs(mmrBucket(mmrA) - mmrBucket(mmrB))
  if (gap === 0) return true
  return waitedMs >= MATCH_RELAX_MS * gap
}
