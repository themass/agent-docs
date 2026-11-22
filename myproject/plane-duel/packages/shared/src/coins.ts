/**
 * 金币账本（spec §廿二）：纯函数与常量，服务端接线、客户端展示共用。
 *
 * 三条铁律（§18.4 法规红线）：
 * 1. 金币只在 玩家 ↔ 系统 之间流动，永不在玩家之间转移；
 * 2. 门票归系统回收，奖励是固定额，与对手付了多少无关；
 * 3. 每日净增封顶——金币产出受控，不能无限刷。
 */
import type { Capacity, PresetId } from './ruleset'

// ---------------------------------------------------------------- 门票档

export type TicketId = 'free' | 'standard' | 'advanced'

export const TICKET_IDS: readonly TicketId[] = ['free', 'standard', 'advanced']

export function isTicketId(v: unknown): v is TicketId {
  return typeof v === 'string' && (TICKET_IDS as readonly string[]).includes(v)
}

/** 门票与奖励都是固定额（系统定价，不是奖池） */
export const TICKETS: Readonly<Record<TicketId, { fee: number; reward: number }>> = {
  free: { fee: 0, reward: 0 },
  standard: { fee: 50, reward: 80 },
  advanced: { fee: 100, reward: 160 },
}

/** 队列键（匹配维度）：人数 × 档位 × 门票档 */
export type TicketQueueKey = { capacity: Capacity; preset: PresetId; ticket: TicketId }

// ---------------------------------------------------------------- 账本类型

export type CoinReason =
  | 'login' // 每日登录礼
  | 'game' // 完成对局
  | 'ticket-fee' // 门票（支出）
  | 'ticket-win' // 门票胜利奖励
  | 'ticket-refund' // 成局前退款（不受净增上限）
  | 'ad' // 激励广告（P4 mock）
  | 'season-grant' // 赛季段位奖励

export type CoinEntry = { id: string; at: number; delta: number; reason: CoinReason; ref?: string }

export type CoinsState = { balance: number; ledger: CoinEntry[] }

/** 当日计数器；day 翻转时整体换新（旧值作废） */
export type DailyState = {
  day: string
  loginDone: boolean
  gameGrants: number
  ticketPlays: number
  adGrants: number
  netGain: number
}

// ---------------------------------------------------------------- 常量（§廿二.2）

export const COIN = {
  LOGIN_GRANT: 50,
  GAME_GRANT: 5,
  DAILY_GAME_MAX: 20,
  DAILY_TICKET_MAX: 20,
  /** 每日净增封顶（支出为负数，会把净值拉回来） */
  NET_GAIN_MAX: 500,
  AD_GRANT: 30,
  AD_DAILY_MAX: 5,
  /** 明细保留条数；更早的折进 balance */
  LEDGER_MAX: 100,
} as const

/** 不受净增上限约束的 reason：退款是还回自己的钱；赛季发币 4 周一次，不是可刷产出 */
const NET_EXEMPT: ReadonlySet<CoinReason> = new Set(['ticket-refund', 'season-grant'])

// ---------------------------------------------------------------- 纯函数

/** 服务端本地日（00:00 翻转）的日期键 */
export function dayKey(now: number): string {
  const d = new Date(now)
  return `${d.getFullYear()}-${d.getMonth() + 1}-${d.getDate()}`
}

export function initialDaily(now: number): DailyState {
  return { day: dayKey(now), loginDone: false, gameGrants: 0, ticketPlays: 0, adGrants: 0, netGain: 0 }
}

/** 跨日自动翻转（纯函数，返回新对象或原对象） */
export function rollDaily(daily: DailyState, now: number): DailyState {
  return daily.day === dayKey(now) ? daily : initialDaily(now)
}

export type CoinOp = {
  reason: CoinReason
  /** 幂等键：reason:ref；同 id 重复调用是 no-op */
  id: string
  ref?: string
  at: number
  /** 期望变动：收入正、支出负 */
  delta: number
}

export type CoinResult = {
  coins: CoinsState
  daily: DailyState
  /** 实际入账（0 = 被幂等吞掉或被上限截成 0） */
  applied: number
  /** 有金额被净增上限截掉 */
  capped: boolean
  /** 余额不足以支出（调用方应拒绝本次操作，coins 原样返回） */
  insufficient: boolean
}

/**
 * 一笔账（§廿二.1/§廿二.2）：幂等 → 日计数 → 净增封顶 → 余额/明细更新。
 * 支出（delta < 0）不受净增上限，但余额不足时整体拒绝（insufficient）。
 */
export function applyCoin(coins: CoinsState, daily: DailyState, op: CoinOp): CoinResult {
  const d0 = rollDaily(daily, op.at)
  // 幂等：账本里已有同 id → 原样返回（applied 0）。
  // 上限截断后条目可能已折叠出明细，但余额路径同样只加一次——store 层另有 seen 集兜底。
  if (coins.ledger.some((e) => e.id === op.id)) return { coins, daily: d0, applied: 0, capped: false, insufficient: false }

  if (op.delta < 0 && coins.balance + op.delta < 0) {
    return { coins, daily: d0, applied: 0, capped: false, insufficient: true }
  }

  let delta = op.delta
  let capped = false
  if (delta > 0 && !NET_EXEMPT.has(op.reason)) {
    // 分 reason 日限（评审 #3）：完成对局 20 局/日——只进 daily 计数不检查等于没限
    if (op.reason === 'game' && d0.gameGrants >= COIN.DAILY_GAME_MAX) {
      return { coins, daily: d0, applied: 0, capped: true, insufficient: false }
    }
    const room = COIN.NET_GAIN_MAX - d0.netGain
    if (room <= 0) return { coins, daily: d0, applied: 0, capped: true, insufficient: false }
    if (delta > room) {
      delta = room
      capped = true
    }
  }

  const entry: CoinEntry = { id: op.id, at: op.at, delta, reason: op.reason, ...(op.ref !== undefined ? { ref: op.ref } : {}) }
  const ledger = [entry, ...coins.ledger].slice(0, COIN.LEDGER_MAX)
  const nextDaily: DailyState = {
    ...d0,
    netGain: NET_EXEMPT.has(op.reason) ? d0.netGain : d0.netGain + delta,
    ...(op.reason === 'login' ? { loginDone: true } : {}),
    ...(op.reason === 'game' ? { gameGrants: d0.gameGrants + 1 } : {}),
    ...(op.reason === 'ad' ? { adGrants: d0.adGrants + 1 } : {}),
  }
  return { coins: { balance: coins.balance + delta, ledger }, daily: nextDaily, applied: delta, capped, insufficient: false }
}

/** 门票消耗计数在真正开局时走这里（不是 applyCoin 的账目，是配额） */
export function canPlayTicket(daily: DailyState): boolean {
  return daily.ticketPlays < COIN.DAILY_TICKET_MAX
}

export function bumpTicketPlays(daily: DailyState, now: number): DailyState {
  const d0 = rollDaily(daily, now)
  return { ...d0, ticketPlays: d0.ticketPlays + 1 }
}

/** 赛季段位奖励：(tier+1)×50，元帅 400（§廿二.5） */
export function seasonGrant(tier: number): number {
  return (tier + 1) * 50
}

/** 大厅/账本页共用的展示标签 */
export const COIN_REASON_LABELS: Readonly<Record<CoinReason, string>> = {
  login: '每日登录',
  game: '完成对局',
  'ticket-fee': '门票',
  'ticket-win': '门票胜利',
  'ticket-refund': '门票退款',
  ad: '广告奖励',
  'season-grant': '赛季奖励',
}
