/**
 * 金币账本纯函数单测（spec §廿二）：幂等、净增封顶、余额拒绝、日翻转、门票定价。
 */
import { describe, it, expect } from 'vitest'
import {
  applyCoin,
  bumpTicketPlays,
  canPlayTicket,
  COIN,
  dayKey,
  initialDaily,
  rollDaily,
  seasonGrant,
  TICKETS,
  type CoinsState,
  type DailyState,
} from '../src/coins'

const T0 = Date.UTC(2026, 10, 20, 12, 0, 0) // 同一天内的固定时刻
const empty = (): CoinsState => ({ balance: 0, ledger: [] })
const daily = (): DailyState => initialDaily(T0)

describe('applyCoin 基础', () => {
  it('收入加余额并写明细；id 进账本', () => {
    const r = applyCoin(empty(), daily(), { reason: 'login', id: 'login:d1', ref: 'd1', at: T0, delta: COIN.LOGIN_GRANT })
    expect(r.applied).toBe(50)
    expect(r.coins.balance).toBe(50)
    expect(r.coins.ledger[0]).toMatchObject({ id: 'login:d1', delta: 50, reason: 'login' })
  })

  it('同 id 重放是 no-op（幂等，§廿二.1）', () => {
    const a = applyCoin(empty(), daily(), { reason: 'game', id: 'game:t:1', at: T0, delta: 5 })
    const b = applyCoin(a.coins, a.daily, { reason: 'game', id: 'game:t:1', at: T0, delta: 5 })
    expect(b.applied).toBe(0)
    expect(b.coins.balance).toBe(5)
    expect(b.coins.ledger).toHaveLength(1)
  })

  it('余额不足以支出：整体拒绝并带 insufficient', () => {
    const r = applyCoin({ balance: 30, ledger: [] }, daily(), { reason: 'ticket-fee', id: 'fee:1', at: T0, delta: -50 })
    expect(r.insufficient).toBe(true)
    expect(r.coins.balance).toBe(30)
    expect(r.coins.ledger).toHaveLength(0)
  })

  it('明细新在前，超过 LEDGER_MAX 折掉最旧（余额保留，§廿二.1）', () => {
    let c = empty()
    let d = daily()
    for (let i = 0; i < COIN.LEDGER_MAX + 5; i++) {
      // 用两种 NET_EXEMPT reason：既不受净增封顶，也不受分 reason 日限（评审 #3 后 game 有 20/日）
      const r = applyCoin(c, d, { reason: 'season-grant', id: `grant:${i}`, at: T0, delta: 1 })
      c = r.coins
      d = r.daily
      const r2 = applyCoin(c, d, { reason: 'ticket-refund', id: `refund:${i}`, at: T0, delta: 1 })
      c = r2.coins
      d = r2.daily
    }
    expect(c.ledger).toHaveLength(COIN.LEDGER_MAX)
    expect(c.ledger[0]!.id).toBe('refund:104') // 最新在前
    expect(c.balance).toBe(2 * (COIN.LEDGER_MAX + 5)) // 折叠不丢余额（每轮 grant+refund 各 1）
  })
})

describe('每日上限（§廿二.2）', () => {
  it('净增 +500 封顶：超出部分不发并 capped=true', () => {
    let c = empty()
    let d = daily()
    const r = applyCoin(c, d, { reason: 'login', id: 'a', at: T0, delta: 480 })
    c = r.coins
    d = r.daily
    const r2 = applyCoin(c, d, { reason: 'game', id: 'b', at: T0, delta: 50 })
    expect(r2.applied).toBe(20) // 只剩 500−480 的空间
    expect(r2.capped).toBe(true)
    expect(r2.coins.balance).toBe(500)
    const r3 = applyCoin(r2.coins, r2.daily, { reason: 'game', id: 'c', at: T0, delta: 5 })
    expect(r3.applied).toBe(0)
    expect(r3.capped).toBe(true)
  })

  it('退款豁免净增上限：还回自己的钱不算产出', () => {
    let d = daily()
    let c = empty()
    const a = applyCoin(c, d, { reason: 'login', id: 'a', at: T0, delta: 500 })
    c = a.coins
    d = a.daily
    const r = applyCoin(c, d, { reason: 'ticket-refund', id: 'refund:x', at: T0, delta: 100 })
    expect(r.applied).toBe(100)
    expect(r.coins.balance).toBe(600)
    expect(r.daily.netGain).toBe(500) // 净值不涨
  })

  it('支出把净值拉回：负 delta 直接进 netGain', () => {
    const a = applyCoin({ balance: 500, ledger: [] }, daily(), { reason: 'login', id: 'a', at: T0, delta: 500 })
    const r = applyCoin(a.coins, a.daily, { reason: 'ticket-fee', id: 'fee:1', at: T0, delta: -100 })
    expect(r.daily.netGain).toBe(400)
    // 拉回之后又能赚
    const r2 = applyCoin(r.coins, r.daily, { reason: 'game', id: 'g1', at: T0, delta: 50 })
    expect(r2.applied).toBe(50)
  })

  it('日计数：login 置位、game/ad 计数', () => {
    const a = applyCoin(empty(), daily(), { reason: 'login', id: 'l', at: T0, delta: 50 })
    expect(a.daily.loginDone).toBe(true)
    const b = applyCoin(a.coins, a.daily, { reason: 'ad', id: 'ad:1', at: T0, delta: 30 })
    expect(b.daily.adGrants).toBe(1)
    const c = applyCoin(b.coins, b.daily, { reason: 'game', id: 'g:1', at: T0, delta: 5 })
    expect(c.daily.gameGrants).toBe(1)
  })
})

describe('日翻转与门票', () => {
  it('dayKey 跨 00:00 翻转；rollDaily 换新计数器', () => {
    const noon = Date.UTC(2026, 10, 20, 12)
    const next = Date.UTC(2026, 10, 21, 0, 0, 1)
    expect(dayKey(noon)).not.toBe(dayKey(next))
    const used = applyCoin(empty(), initialDaily(noon), { reason: 'login', id: 'l', at: noon, delta: 50 }).daily
    expect(used.loginDone).toBe(true)
    const rolled = rollDaily(used, next)
    expect(rolled.day).toBe(dayKey(next))
    expect(rolled.loginDone).toBe(false)
    expect(rolled.netGain).toBe(0)
  })

  it('门票配额：20 场封顶', () => {
    let d = daily()
    for (let i = 0; i < COIN.DAILY_TICKET_MAX; i++) d = bumpTicketPlays(d, T0)
    expect(canPlayTicket(d)).toBe(false)
  })

  it('门票定价与奖励（§廿二.3：固定额）', () => {
    expect(TICKETS.free).toEqual({ fee: 0, reward: 0 })
    expect(TICKETS.standard.reward).toBeGreaterThan(TICKETS.standard.fee)
    expect(TICKETS.advanced.fee).toBe(100)
  })

  it('赛季发币：(tier+1)×50，元帅 400', () => {
    expect(seasonGrant(0)).toBe(50)
    expect(seasonGrant(7)).toBe(400)
  })
})

describe('applyCoin 分 reason 日限（评审 #3，§廿二.2）', () => {
  it('完成对局 20 局/日封顶：第 21 局 applied=0 且 capped', () => {
    let coins = empty()
    let d = daily()
    for (let i = 0; i < COIN.DAILY_GAME_MAX; i++) {
      const r = applyCoin(coins, d, { reason: 'game', id: `game:${i}`, at: T0, delta: COIN.GAME_GRANT })
      expect(r.applied).toBe(COIN.GAME_GRANT)
      coins = r.coins
      d = r.daily
    }
    expect(d.gameGrants).toBe(COIN.DAILY_GAME_MAX)
    const over = applyCoin(coins, d, { reason: 'game', id: 'game:21', at: T0, delta: COIN.GAME_GRANT })
    expect(over.applied).toBe(0)
    expect(over.capped).toBe(true)
    expect(over.coins.balance).toBe(coins.balance)
    // 其它 reason 不受 game 日限影响（净值还充裕）
    const ad = applyCoin(coins, d, { reason: 'ad', id: 'ad:1', at: T0, delta: COIN.AD_GRANT })
    expect(ad.applied).toBe(COIN.AD_GRANT)
  })
})
