/**
 * Hub P4 接线（spec §廿二）：登录礼、账本快照、广告 mock 限额、
 * 门票预付/退款/胜负奖励、完成对局发币。假时钟固定同一天。
 */
import { describe, it, expect } from 'vitest'
import { COIN } from '@plane-duel/shared'
import { mkHub } from './hub-helpers'

/** 打完一局 2 人匹配房：返回 { winSid, loseSid }（先手随机，按引擎判定） */
function playMatchDuel(h: ReturnType<typeof mkHub>) {
  h.auth('s1', 'alice')
  h.auth('s2', 'bob')
  h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
  h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard' })
  const code = h.tableOf('s1').roomCode
  h.send('s1', { type: 'placePlane', planes: [{ row: 3, col: 7 }] })
  h.send('s2', { type: 'placePlane', planes: [{ row: 6, col: 2 }] })
  const engine = h.hub.getTable(code)!.engine!
  const first = engine.view('alice').turn
  const [winSid, target] = first === 'alice' ? ['s1', { row: 6, col: 2 }] : ['s2', { row: 3, col: 7 }]
  h.send(winSid, { type: 'fire', ...target })
  return { winSid, loseSid: winSid === 's1' ? 's2' : 's1' }
}

describe('Hub P4：收入（§廿二.2/§廿二.4）', () => {
  it('auth 推登录礼 coinsChanged +50；同日重连不再发', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    const gift = h.recv('s1').find((m: any) => m.type === 'coinsChanged')
    expect(gift).toMatchObject({ delta: COIN.LOGIN_GRANT, reason: 'login', balance: 50 })
    // 同日第二次 auth（夹具会清空收件箱）：只该有新的 profile，登录礼不重复
    h.auth('s1', 'alice')
    expect(h.recv('s1').filter((m: any) => m.type === 'coinsChanged')).toHaveLength(0)
  })

  it('coinRequest 回余额 + 明细 + 当日计数', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.send('s1', { type: 'coinRequest' })
    const c = h.last('s1', 'coins')
    expect(c.balance).toBe(50)
    expect(c.ledger[0]).toMatchObject({ reason: 'login', delta: 50 })
    expect(c.daily).toMatchObject({ loginDone: true, gameGrants: 0 })
  })

  it('完成对局双方各 +5，进账本（reason=game）', () => {
    const h = mkHub()
    const { winSid, loseSid } = playMatchDuel(h)
    for (const sid of [winSid, loseSid]) {
      const g = h.recv(sid).find((m: any) => m.type === 'coinsChanged' && m.reason === 'game')
      expect(g).toMatchObject({ delta: COIN.GAME_GRANT, reason: 'game' })
    }
    // 登录 50 + 完成 5
    expect(h.last(winSid, 'profile').profile.coins).toBe(55)
  })

  it('广告 mock：+30/次，每日 5 次封顶后回 AD_LIMIT', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    for (let i = 0; i < COIN.AD_DAILY_MAX; i++) {
      h.send('s1', { type: 'adRewardRequest', slot: 'coins' })
    }
    expect(h.recv('s1').filter((m: any) => m.type === 'coinsChanged' && m.reason === 'ad')).toHaveLength(COIN.AD_DAILY_MAX)
    h.send('s1', { type: 'adRewardRequest', slot: 'coins' })
    expect(h.last('s1', 'error').code).toBe('AD_LIMIT')
    // 登录 50 + 广告 150；广告只推 coinsChanged，余额以档案为准要重发请求
    h.send('s1', { type: 'profileRequest' })
    expect(h.last('s1', 'profile').profile.coins).toBe(50 + COIN.AD_DAILY_MAX * COIN.AD_GRANT)
  })

  it('每日净增封顶 +500：净值满后广告 applied=0，不推 coinsChanged', () => {
    const h = mkHub()
    const store = h.hub.profileStore
    h.auth('s1', 'alice')
    // 用受上限约束的 reason 灌满当日净值（登录礼 50 已计入，再补 450 → 500）
    store.coin('alice', { reason: 'game', id: 'game:fill', at: 1_000_000, delta: 450 })
    h.send('s1', { type: 'adRewardRequest', slot: 'coins' })
    // 净值 500 已满 → 广告被封顶截为 0，不推账变
    expect(h.recv('s1').some((m: any) => m.type === 'coinsChanged' && m.reason === 'ad')).toBe(false)
    h.send('s1', { type: 'profileRequest' })
    expect(h.last('s1', 'profile').profile.coins).toBe(500)
  })
})

describe('Hub P4：门票对局（§廿二.3）', () => {
  it('余额不足：NOT_ENOUGH_COINS，不入队不扣钱', () => {
    const h = mkHub()
    h.auth('s1', 'alice') // 余额 50（登录礼）
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'advanced' }) // 门票 100
    expect(h.last('s1', 'error').code).toBe('NOT_ENOUGH_COINS')
    expect(h.last('s1', 'profile').profile.coins).toBe(50)
  })

  it('排队中途退出：门票全额退款', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.send('s1', { type: 'queueJoin', capacity: 4, preset: 'standard', ticket: 'standard' }) // 预付 50 → 0
    expect(h.last('s1', 'coinsChanged')).toMatchObject({ reason: 'ticket-fee', delta: -50, balance: 0 })
    h.send('s1', { type: 'queueLeave' })
    expect(h.last('s1', 'coinsChanged')).toMatchObject({ reason: 'ticket-refund', delta: 50, balance: 50 })
  })

  it('补位成局（有电脑）：退款，不发奖励', () => {
    const h = mkHub({ botFillMs: 30_000 })
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    h.send('s1', { type: 'queueJoin', capacity: 3, preset: 'standard', ticket: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 3, preset: 'standard', ticket: 'standard' })
    // 双方都付了票：50−50=0
    expect(h.last('s1', 'coinsChanged').balance).toBe(0)
    expect(h.last('s2', 'coinsChanged').balance).toBe(0)
    h.advance(31_000) // 补位倒计时到 → 2 真人 + 1 电脑成局
    for (const sid of ['s1', 's2']) {
      const last = h.last(sid, 'coinsChanged')
      expect(last).toMatchObject({ reason: 'ticket-refund', delta: 50, balance: 50 })
    }
  })

  it('纯真人满局：记桌上，首局胜者 +80 门票奖励，败者无；再来一局不重复收', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' })
    const code = h.tableOf('s1').roomCode
    h.send('s1', { type: 'placePlane', planes: [{ row: 3, col: 7 }] })
    h.send('s2', { type: 'placePlane', planes: [{ row: 6, col: 2 }] })
    const engine = h.hub.getTable(code)!.engine!
    const first = engine.view('alice').turn
    const [winSid, target] = first === 'alice' ? ['s1', { row: 6, col: 2 }] : ['s2', { row: 3, col: 7 }]
    h.send(winSid, { type: 'fire', ...target })

    // 胜者：票 50 扣掉后完成局 +5、门票奖励 +80 → 50−50+5+80 = 85
    expect(h.last(winSid, 'profile').profile.coins).toBe(85)
    const win = h.recv(winSid).filter((m: any) => m.type === 'coinsChanged').map((m: any) => m.reason)
    expect(win).toEqual(['login', 'ticket-fee', 'game', 'ticket-win'])
    // 败者：50−50+5 = 5，没有 ticket-win
    expect(h.last(winSid === 's1' ? 's2' : 's1', 'profile').profile.coins).toBe(5)
    const loseSid = winSid === 's1' ? 's2' : 's1'
    expect(h.recv(loseSid).some((m: any) => m.reason === 'ticket-win')).toBe(false)
  })

  it('日门票配额 20 场：第 21 次入队回 DAILY_TICKET_LIMIT', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    const store = h.hub.profileStore
    for (let i = 0; i < COIN.DAILY_TICKET_MAX; i++) store.countTicketPlay('alice', 1_000_000)
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' })
    expect(h.last('s1', 'error').code).toBe('DAILY_TICKET_LIMIT')
  })
})

describe('评审回归（整枝 #1/#2/#6）', () => {
  it('同一毫秒内换门票档 standard→advanced：每笔各扣各退，退出后净值不变', () => {
    const h = mkHub() // 假时钟固定 now=1_000_000：两条消息同一毫秒
    const store = h.hub.profileStore
    h.auth('s1', 'alice') // 50
    store.coin('alice', { reason: 'game', id: 'game:fill', at: 1_000_000, delta: 150 }) // →200
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' }) // −50 → 150
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'advanced' }) // 退+50、扣−100 → 100
    h.send('s1', { type: 'queueLeave' }) // 按高级场退 +100 → 200
    const reasons = h.recv('s1').filter((m: any) => m.type === 'coinsChanged').map((m: any) => m.reason)
    expect(reasons).toEqual(['login', 'ticket-fee', 'ticket-refund', 'ticket-fee', 'ticket-refund'])
    h.send('s1', { type: 'profileRequest' })
    expect(h.last('s1', 'profile').profile.coins).toBe(200) // 老代码此处 300：幂等键吞费 + 高档白退
  })

  it('门票桌中途流局（首局对局中离席判负）：胜者照拿固定奖励，门票不重复退', () => {
    // 实测：匹配桌入座即开打，离席走判负 gameOver → scoreTable 结算门票。
    // sync() 里的关桌退款是防御网（评审 #2）：现网路径都先经 scoreTable，
    // 这里锁住正确行为——结算恰好一次，不出现双退/双发。
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard', ticket: 'standard' })
    h.send('s1', { type: 'leaveRoom' }) // 摆放阶段离席 → 判负
    // 胜者 s2：50−50+5+80=85；账变恰好 login/fee/game/win 四条，无退款
    const s2 = h.recv('s2').filter((m: any) => m.type === 'coinsChanged').map((m: any) => m.reason)
    expect(s2).toEqual(['login', 'ticket-fee', 'game', 'ticket-win'])
    // 败者 s1（离席方）：P3 口径中途离开不进快照——不计分也不发完成局金币，
    // 只损失门票（50−50），无 ticket-refund、无 ticket-win
    const s1 = h.recv('s1').filter((m: any) => m.type === 'coinsChanged').map((m: any) => m.reason)
    expect(s1).toEqual(['login', 'ticket-fee'])
  })

  it('完成对局日限（纯函数封顶）：gameGrants 满 20 后完成局不再推 coinsChanged', () => {
    const h = mkHub()
    const store = h.hub.profileStore
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    for (let i = 0; i < COIN.DAILY_GAME_MAX; i++) {
      store.coin('alice', { reason: 'game', id: `game:seed:${i}`, at: 1_000_000, delta: 1 })
    }
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    const code = h.tableOf('s1').roomCode
    h.send('s1', { type: 'placePlane', planes: [{ row: 3, col: 7 }] })
    h.send('s2', { type: 'placePlane', planes: [{ row: 6, col: 2 }] })
    const engine = h.hub.getTable(code)!.engine!
    const first = engine.view('alice').turn
    const winSid = first === 'alice' ? 's1' : 's2'
    h.send(winSid, { type: 'fire', ...(first === 'alice' ? { row: 6, col: 2 } : { row: 3, col: 7 }) })
    // alice 日限已满：没有 reason=game 的账变；余额 = 登录 50 + 种子 20
    expect(h.recv('s1').some((m: any) => m.type === 'coinsChanged' && m.reason === 'game')).toBe(false)
    h.send('s1', { type: 'profileRequest' })
    expect(h.last('s1', 'profile').profile.coins).toBe(70)
    // bob 未满：正常 +5
    const g = h.recv('s2').find((m: any) => m.type === 'coinsChanged' && m.reason === 'game')
    expect(g).toMatchObject({ delta: COIN.GAME_GRANT })
  })
})
