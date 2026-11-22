/**
 * 玩家档案（spec §21.1）：段位、MMR、战绩摘要按 playerId 持久化。
 *
 * ProfileStore 是接口；本文件提供内存实现与 JSON 文件实现（写盘防抖）。
 * Redis/Postgres 到 P5 部署期再换，接口不变。
 * 段位升降调用 shared 的纯函数（rank.ts），这里只做存储与统计接线。
 */

import { mkdirSync, readFileSync, renameSync, writeFileSync } from 'node:fs'
import { dirname } from 'node:path'
import {
  applyOutcome,
  initialRank,
  seasonNumber,
  resetSeason,
  applyCoin as applyCoinPure,
  initialDaily,
  rollDaily,
  seasonGrant,
  dayKey,
  COIN,
  bumpTicketPlays,
  canPlayTicket,
  type CoinOp,
  type CoinResult,
  type CoinsState,
  type DailyState,
  type Capacity,
  type GameSummary,
  type Mode,
  type PresetId,
  type ProfileView,
  type RankState,
} from '@plane-duel/shared'

export type Profile = {
  playerId: string
  nickname: string
  rank: RankState
  /** 写入时所在赛季；读取时若赛季已变则 resetSeason（spec §21.3） */
  season: number
  stats: {
    wins: number
    losses: number
    totalHits: number
    bestTier: number
    bestStars: number
    streak: number
    scoringGames: number
  }
  recent: GameSummary[]
  /** P3 预留：微信等第三方账号绑定（本期不接入，spec §21.1） */
  accounts: Partial<Record<'wechat', string>>
  lastSeenAt: number
  /** P4（spec §廿二.1）：余额 + 只增明细；余额是权威，明细可折叠 */
  coins: CoinsState
  /** 当日计数器（服务端本地日 00:00 翻转） */
  daily: DailyState
}

/** §21.4：recent 保留最近 20 条 */
export const RECENT_MAX = 20

export type ScoringInput = {
  /** 幂等键 tableId:gamesPlayed（§21.7） */
  id: string
  at: number
  mode: Mode
  preset: PresetId
  capacity: Capacity
  /** 最终名次（1 起）；1 = 胜 */
  rank: number
  hits: number
  /** 有电脑参与的局（练习/补位）：记战绩，不动段位（§21.2） */
  withBots: boolean
  /** 对手（或同桌基准）MMR：取同桌真人 MMR 均值，单人参照用自己的 */
  opponentMmr: number
}

export type ScoreResult = { profile: Profile; delta: number }

export type LeaderRow = { nickname: string; tier: number; stars: number; mmr: number; wins: number }

export interface ProfileStore {
  get(playerId: string, nickname: string, now: number): Profile
  /** 记录一局；计分段同时结算段位。幂等：同 id 重复调用返回原结果、不重复加星。 */
  record(playerId: string, input: ScoringInput): ScoreResult
  /** 改昵称同步进档案（榜单显示用） */
  setNickname(playerId: string, nickname: string): void
  view(playerId: string, nickname: string, now: number): ProfileView
  /** 段位榜：(tier, stars, mmr) 前 n；条目不含 playerId（§21.5） */
  leaderboard(n: number, now: number): { season: number; entries: LeaderRow[] }
  /** 跨季重置全部档案，返回受影响 playerId（tick 推送用，§21.3） */
  resetSeasonAll(now: number): string[]
  /** P4 一笔账（§廿二.1/§廿二.2）：日翻转 + 幂等 + 净增封顶 */
  coin(playerId: string, op: CoinOp): CoinResult & { profile: Profile }
  /** 登录礼（每日一次，§廿二.2） */
  loginGrant(playerId: string, now: number): CoinResult
  /** 门票日配额判定（§廿二.2） */
  canJoinTicket(playerId: string, now: number): boolean
  /** 真人门票局开局计数（补位退款不计） */
  countTicketPlay(playerId: string, now: number): void
  /** 账号绑定接口（§21.1 定义、本期不接真实登录） */
  bindAccount(playerId: string, provider: 'wechat', openId: string): void
}

function freshProfile(playerId: string, nickname: string, now: number, season: number): Profile {
  return {
    playerId,
    nickname,
    rank: initialRank(),
    season,
    stats: { wins: 0, losses: 0, totalHits: 0, bestTier: 0, bestStars: 0, streak: 0, scoringGames: 0 },
    recent: [],
    accounts: {},
    lastSeenAt: now,
    coins: { balance: 0, ledger: [] },
    daily: initialDaily(now),
  }
}

/** 内存实现（测试与 dev 默认）。 */
export class MemoryProfileStore implements ProfileStore {
  protected readonly profiles = new Map<string, Profile>()
  /** 幂等去重：playerId → 已处理的计分 id 集合（保留最近 64 个） */
  private readonly seen = new Map<string, Set<string>>()

  constructor(private readonly now0: () => number = () => Date.now()) {}

  get(playerId: string, nickname: string, now: number): Profile {
    let p = this.profiles.get(playerId)
    if (p === undefined) {
      p = freshProfile(playerId, nickname, now, seasonNumber(now))
      this.profiles.set(playerId, p)
    }
    p.lastSeenAt = now
    if (nickname) p.nickname = nickname
    // 跨季懒重置（§21.3：读取时兜底；tick 里的主动重置负责推送）。
    // 懒路径同样发赛季奖励（评审 #4）：否则先被 get 摸到的在线玩家被 resetSeasonAll
    // 跳过，(tier+1)×50 无声蒸发。幂等键 season-grant:<赛季> 保证两路只发一次。
    const season = seasonNumber(now)
    if (p.season !== season) this.crossSeason(p, season, now)
    return p
  }

  /** 跨季处理：按上赛季段位发奖励，再降段、换季（§廿二.5；懒路径与 tick 共用） */
  private crossSeason(p: Profile, season: number, now: number): void {
    const grant = seasonGrant(p.rank.tier)
    p.rank = resetSeason(p.rank)
    p.season = season
    if (grant > 0) {
      this.coin(p.playerId, { reason: 'season-grant', id: `season-grant:${season}`, ref: String(season), at: now, delta: grant })
    }
  }

  record(playerId: string, input: ScoringInput): ScoreResult {
    const now = input.at
    const p = this.get(playerId, '', now)
    const seenFor = this.seen.get(playerId) ?? new Set<string>()
    if (seenFor.has(input.id)) {
      // 重放：报出本局原有的星数变化，不重复记账（§21.7）
      const original = p.recent.find((g) => g.id === input.id)
      return { profile: p, delta: original?.delta ?? 0 }
    }
    seenFor.add(input.id)
    if (seenFor.size > 64) {
      const first = seenFor.values().next().value as string
      seenFor.delete(first)
    }
    this.seen.set(playerId, seenFor)

    // 段位与星数只由计分局（无电脑）驱动；电脑局 delta 恒为 0
    const apply = input.withBots
      ? null
      : applyOutcome(p.rank, input.rank === 1 ? 'win' : 'loss', input.opponentMmr)
    const delta = apply?.delta ?? 0

    const summary: GameSummary = {
      id: input.id,
      at: now,
      mode: input.mode,
      preset: input.preset,
      capacity: input.capacity,
      rank: input.rank,
      withBots: input.withBots,
      win: input.rank === 1,
      hits: input.hits,
      delta,
    }
    p.recent = [summary, ...p.recent].slice(0, RECENT_MAX)
    p.stats.totalHits += input.hits
    if (apply !== null) {
      p.rank = apply.state
      p.stats.scoringGames += 1
      if (input.rank === 1) {
        p.stats.wins += 1
        p.stats.streak += 1
      } else {
        p.stats.losses += 1
        p.stats.streak = 0
      }
      if (p.rank.tier > p.stats.bestTier || (p.rank.tier === p.stats.bestTier && p.rank.stars > p.stats.bestStars)) {
        p.stats.bestTier = p.rank.tier
        p.stats.bestStars = p.rank.stars
      }
    }
    this.dirty(p)
    return { profile: p, delta }
  }

  setNickname(playerId: string, nickname: string): void {
    const p = this.profiles.get(playerId)
    if (p !== undefined && p.nickname !== nickname) {
      p.nickname = nickname
      this.dirty(p)
    }
  }

  view(playerId: string, nickname: string, now: number): ProfileView {
    const p = this.get(playerId, nickname, now)
    return {
      nickname: p.nickname,
      rank: { tier: p.rank.tier, stars: p.rank.stars, lossStreak: p.rank.lossStreak },
      season: p.season,
      stats: { ...p.stats },
      recent: p.recent.slice(0, RECENT_MAX),
      coins: p.coins.balance,
    }
  }

  /**
   * P4 一笔账（spec §廿二.1/§廿二.2）：日翻转 + 幂等 + 净增封顶，全在纯函数里。
   * 账本与档案同库落盘；调用方负责把结果推给本人。
   */
  coin(playerId: string, op: CoinOp): CoinResult & { profile: Profile } {
    const p = this.get(playerId, '', op.at)
    // 日翻转要在读旧值前先做（旧天的计数不能带进新天）
    if (p.daily.day !== dayKey(op.at)) p.daily = initialDaily(op.at)
    const r = applyCoinPure(p.coins, p.daily, op)
    p.coins = r.coins
    p.daily = r.daily
    if (r.applied !== 0) this.dirty(p)
    return { ...r, profile: p }
  }

  /** 登录礼（每日一次）：auth 时调；applied>0 时调用方要推 coinsChanged（§廿二.2） */
  loginGrant(playerId: string, now: number): CoinResult {
    const p = this.get(playerId, '', now)
    const day = dayKey(now)
    if (p.daily.day === day && p.daily.loginDone) {
      return { coins: p.coins, daily: p.daily, applied: 0, capped: false, insufficient: false }
    }
    return this.coin(playerId, { reason: 'login', id: `login:${day}`, ref: day, at: now, delta: COIN.LOGIN_GRANT })
  }

  /** 门票日配额（§廿二.2：20 场/日）；只读判定，跨日自动翻转 */
  canJoinTicket(playerId: string, now: number): boolean {
    return canPlayTicket(rollDaily(this.get(playerId, '', now).daily, now))
  }

  /** 真人门票局开局计数（补位局退款不计数，不走这里） */
  countTicketPlay(playerId: string, now: number): void {
    const p = this.get(playerId, '', now)
    p.daily = bumpTicketPlays(p.daily, now)
    this.dirty(p)
  }

  leaderboard(n: number, now: number): { season: number; entries: LeaderRow[] } {
    const rows = [...this.profiles.values()]
      .filter((p) => p.stats.scoringGames > 0)
      .sort(
        (a, b) =>
          b.rank.tier - a.rank.tier ||
          b.rank.stars - a.rank.stars ||
          b.rank.mmr - a.rank.mmr ||
          b.stats.wins - a.stats.wins,
      )
      .slice(0, n)
      .map((p) => ({ nickname: p.nickname, tier: p.rank.tier, stars: p.rank.stars, mmr: p.rank.mmr, wins: p.stats.wins }))
    return { season: seasonNumber(now), entries: rows }
  }

  resetSeasonAll(now: number): string[] {
    const season = seasonNumber(now)
    const touched: string[] = []
    for (const p of this.profiles.values()) {
      if (p.season === season) continue
      // 与懒路径共用 crossSeason：先按上赛季段位发币，再降级（§廿二.5、评审 #4）
      this.crossSeason(p, season, now)
      touched.push(p.playerId)
      this.dirty(p)
    }
    return touched
  }

  bindAccount(playerId: string, provider: 'wechat', openId: string): void {
    const p = this.profiles.get(playerId)
    if (p === undefined) return
    p.accounts[provider] = openId
    this.dirty(p)
  }

  /** 子类覆写：落盘点 */
  protected dirty(_p: Profile): void {}
}

/**
 * JSON 文件实现（spec §21.1）：写盘防抖 5 秒，窗口内的多次改动合并成一次写；
 * flush() 供进程退出路径强制落盘。单进程部署（P3–P4）够用。
 */
export class JsonFileProfileStore extends MemoryProfileStore {
  private timer: ReturnType<typeof setTimeout> | null = null

  constructor(private readonly path: string, private readonly now0Or?: () => number) {
    super(now0Or)
    try {
      const raw = readFileSync(path, 'utf8')
      const data = JSON.parse(raw) as Record<string, Profile>
      // P3 旧档没有 coins/daily 字段：读到就补默认值（P4 迁移，§廿二）
      const now0 = (now0Or ?? Date.now)()
      for (const [id, p] of Object.entries(data)) {
        if (p.coins === undefined) p.coins = { balance: 0, ledger: [] }
        if (p.daily === undefined) p.daily = initialDaily(now0)
        this.profiles.set(id, p)
      }
    } catch (err) {
      // 文件不存在或损坏：从空档开始（P3 无找回机制，§21.1）。
      // 损坏（存在但解析失败）必须留痕——否则全员档案无声归零无从排查。
      if ((err as NodeJS.ErrnoException)?.code !== 'ENOENT') {
        console.error(`[profile] 档案文件损坏，从空档开始: ${path}`, err)
      }
    }
  }

  protected override dirty(_p: Profile): void {
    if (this.timer !== null) return
    this.timer = setTimeout(() => {
      this.timer = null
      this.flush()
    }, 5_000)
    this.timer.unref?.()
  }

  flush(): void {
    if (this.timer !== null) {
      clearTimeout(this.timer)
      this.timer = null
    }
    const out: Record<string, Profile> = {}
    for (const [id, p] of this.profiles) out[id] = p
    // 写盘失败（卷权限、磁盘满）不能崩服务（评审 P5 #4）：运行期它发生在防抖 setTimeout
    // 回调里，未捕获异常会带走整个进程——宁可丢这一段盘并留痕，也不能让对局服务因 I/O 挂掉
    try {
      mkdirSync(dirname(this.path), { recursive: true })
      // 同步写：进程退出路径也走这里，不能丢。
      // 先写临时文件再原子改名：断电/kill 不会留下半截 JSON（评审 #4）
      const tmp = `${this.path}.tmp`
      writeFileSync(tmp, JSON.stringify(out))
      renameSync(tmp, this.path)
    } catch (err) {
      console.error(`[profile] 档案写盘失败（本窗口改动未落盘）: ${this.path}`, err)
    }
  }
}
