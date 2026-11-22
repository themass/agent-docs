import { describe, it, expect } from 'vitest'
import type { ClientMessage, GamePhase, GameResult, GameView, Mode, RuleSet } from '@plane-duel/shared'
import { Table, FRIEND_SEAT_GRACE_MS } from '../src/table'
import type { TableOptions } from '../src/table'
import type { BotBrainLike } from '../src/bot/driver'
import type { Engine, EngineOptions, Outbound } from '../src/engine'

const rules: RuleSet = { boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false }

class FakeEngine implements Engine {
  mode: Mode = 'melee'
  phase: GamePhase = 'placing'
  result: GameResult | null = null
  calls: { playerId: string; msg: ClientMessage; now: number }[] = []
  tickCalls: number[] = []
  /** 覆盖 handle 的返回值；默认回一条 planeAccepted 给调用者 */
  handleOutput: ((playerId: string) => Outbound[]) | null = null
  tickOutput: Outbound[] = []
  constructor(readonly opts: EngineOptions) {}
  handle(playerId: string, msg: ClientMessage, now: number): Outbound[] {
    this.calls.push({ playerId, msg, now })
    if (this.handleOutput) return this.handleOutput(playerId)
    return [{ to: playerId, msg: { type: 'planeAccepted', planes: [] } }]
  }
  tick(now: number): Outbound[] {
    this.tickCalls.push(now)
    return this.tickOutput
  }
  setConnected(): Outbound[] {
    return []
  }
  view(playerId: string): GameView {
    return {
      mode: this.mode,
      phase: this.phase,
      deadlineAt: null,
      turn: null,
      round: null,
      you: {
        planes: [],
        planesDestroyed: 0,
        alive: true,
        shots: [],
        incoming: [],
        submitted: false,
        pendingShot: null,
      },
      others: this.opts.playerIds
        .filter((id) => id !== playerId)
        .map((id) => ({
          playerId: id, connected: true, alive: true, planesDestroyed: 0, submitted: false,
        })),
    }
  }
  finish(): void {
    this.phase = 'finished'
    this.result = {
      reason: 'lastStanding',
      ranking: this.opts.playerIds.map((id, i) => ({
        playerId: id, rank: i + 1, eliminatedRound: null, hits: 0,
      })),
    }
  }
}

/** 记录收到的视图与规则，回一条固定的动作。 */
class FakeBot implements BotBrainLike {
  calls: { view: GameView; rules: RuleSet; now: number }[] = []
  next: ClientMessage | null = { type: 'fire', row: 2, col: 3 }
  constructor(readonly playerId: string, readonly difficulty: string) {}
  poll(view: GameView, rules: RuleSet, now: number): ClientMessage | null {
    this.calls.push({ view, rules, now })
    return this.next
  }
}

function make(over: Partial<TableOptions> = {}) {
  const engines: FakeEngine[] = []
  const bots: FakeBot[] = []
  const table = new Table({
    roomCode: '123456',
    kind: 'practice',
    capacity: 3,
    rules,
    now: 0,
    engineFactory: (o) => {
      const e = new FakeEngine(o)
      engines.push(e)
      return e
    },
    botFactory: (playerId, difficulty) => {
      const b = new FakeBot(playerId, difficulty)
      bots.push(b)
      return b
    },
    ...over,
  })
  return { table, engines, bots, last: () => engines[engines.length - 1]! }
}

const botIds = (t: Table) => t.members.filter((id) => id.startsWith('bot:'))
const errorOf = (out: Outbound[]) => {
  const m = out[0]?.msg
  return m && m.type === 'error' ? m.code : null
}

describe('Table 的电脑座位', () => {
  it('练习桌：真人入座 + addBot 补满 → 自动开局；电脑座位 bot=true、ready=true', () => {
    const { table: t, last } = make({ capacity: 3 })
    t.join('human', '我', 0)
    expect(t.engine).toBeNull()
    expect(t.phase).toBe('waiting')
    t.addBot('beginner', 0)
    expect(t.engine).toBeNull()
    t.addBot('beginner', 0)
    expect(t.engine).not.toBeNull()
    expect(t.phase).toBe('inGame')

    const seats = t.view().seats
    expect(seats.map((s) => s!.playerId)).toEqual(['human', 'bot:123456:1:1', 'bot:123456:2:2'])
    expect(seats.map((s) => s!.bot)).toEqual([false, true, true])
    expect(seats.map((s) => s!.nickname)).toEqual(['我', '电脑2', '电脑3'])
    expect(seats.map((s) => s!.connected)).toEqual([true, true, true])
    // 开局清空准备后电脑立即恢复已准备
    expect(seats.map((s) => s!.ready)).toEqual([false, true, true])
    // 引擎以座位顺序拿到全部 playerId（含电脑）
    expect(last().opts.playerIds).toEqual(['human', 'bot:123456:1:1', 'bot:123456:2:2'])
    expect(last().opts.rules).toEqual(rules)
  })

  it('开局清空准备后电脑仍为已准备；再来一局只等真人准备', () => {
    const { table: t, last } = make({ capacity: 2 })
    t.join('human', '我', 0)
    t.addBot('standard', 0)
    expect(t.phase).toBe('inGame')
    last().finish()
    t.tick(1000)
    expect(t.phase).toBe('waiting')

    const out = t.setReady('human', true, t.rulesVersion, 2000)
    expect(t.phase).toBe('inGame')
    expect(out.some((o) => o.msg.type === 'tableState')).toBe(true)
    expect(t.view().seats.map((s) => s!.ready)).toEqual([false, true])
  })

  it('tick 时把 engine.view(电脑自己) 交给电脑，并把其动作转交引擎', () => {
    const { table: t, bots, last } = make({ capacity: 2 })
    t.join('human', '我', 0)
    t.addBot('expert', 0)
    const engine = last()
    const botId = 'bot:123456:1:1'

    t.tick(500)
    expect(engine.tickCalls).toEqual([500])
    expect(bots[0]!.calls).toHaveLength(1)
    expect(bots[0]!.calls[0]!.view).toEqual(engine.view(botId))
    // 电脑只看到自己的视图：others 里没有自己
    expect(bots[0]!.calls[0]!.view.others.map((o) => o.playerId)).toEqual(['human'])
    expect(bots[0]!.calls[0]!.rules).toEqual(rules)
    expect(bots[0]!.calls[0]!.now).toBe(500)
    expect(engine.calls).toEqual([{ playerId: botId, msg: { type: 'fire', row: 2, col: 3 }, now: 500 }])

    // 没有动作时不调用引擎
    bots[0]!.next = null
    t.tick(600)
    expect(engine.calls).toHaveLength(1)
  })

  it('引擎在电脑动作后结束 → 停止本轮轮询，余下的电脑不再被问', () => {
    const { table: t, bots, last } = make({ capacity: 3 })
    t.join('human', '我', 0)
    t.addBot('beginner', 0)
    t.addBot('beginner', 0)
    const engine = last()
    // 1 号电脑出一炮就把对局打完
    engine.handleOutput = () => {
      engine.finish()
      return []
    }

    const out = t.tick(50)
    expect(engine.calls).toHaveLength(1)
    expect(engine.calls[0]!.playerId).toBe('bot:123456:1:1')
    // 2 号电脑没被问到
    expect(bots[1]!.calls).toHaveLength(0)
    expect(t.phase).toBe('waiting')
    expect(out.some((o) => o.to.startsWith('bot:'))).toBe(false)
  })

  it('发给电脑的 Outbound 被丢弃', () => {
    const { table: t, last } = make({ capacity: 2 })
    t.join('human', '我', 0)
    t.addBot('beginner', 0)
    const engine = last()
    const botId = 'bot:123456:1:1'
    engine.tickOutput = [
      { to: botId, msg: { type: 'planeAccepted', planes: [] } },
      { to: 'human', msg: { type: 'planeAccepted', planes: [] } },
    ]
    engine.handleOutput = () => [{ to: botId, msg: { type: 'planeAccepted', planes: [] } }]

    const out = t.tick(10)
    expect(out.some((o) => o.to.startsWith('bot:'))).toBe(false)
    expect(out.filter((o) => o.to === 'human')).toHaveLength(1)
  })

  it('练习桌：真人离开 → isClosed；对局中真人离开 → isClosed 且引擎被丢弃', () => {
    // 等候中离开
    const waiting = make({ capacity: 2 })
    waiting.table.join('human', '我', 0)
    waiting.table.addBot('beginner', 0)
    waiting.last().finish()
    waiting.table.tick(1)
    expect(waiting.table.phase).toBe('waiting')
    waiting.table.leave('human', 2)
    expect(waiting.table.isClosed).toBe(true)
    expect(waiting.table.members).toEqual([])

    // 对局中离开
    const inGame = make({ capacity: 3 })
    inGame.table.join('human', '我', 0)
    inGame.table.addBot('beginner', 0)
    inGame.table.addBot('beginner', 0)
    expect(inGame.table.engine).not.toBeNull()
    inGame.table.leave('human', 5)
    expect(inGame.table.isClosed).toBe(true)
    expect(inGame.table.engine).toBeNull()
    expect(inGame.table.members).toEqual([])
  })

  it('匹配桌 2 真人 + 2 电脑：一名真人对局中离开 → 本局结束后关桌（P1 规则不变）', () => {
    const { table: t, last } = make({ kind: 'match', capacity: 4 })
    t.join('a', 'A', 0)
    t.join('b', 'B', 0)
    t.addBot('beginner', 0)
    t.addBot('beginner', 0)
    expect(t.phase).toBe('inGame')
    expect(botIds(t)).toEqual(['bot:123456:2:1', 'bot:123456:3:2'])

    t.leave('a', 1)
    expect(t.isClosed).toBe(false)
    expect(t.members).toHaveLength(4) // 座位保留到本局结束

    last().finish()
    const out = t.tick(2)
    expect(t.isClosed).toBe(true)
    expect(out.filter((o) => o.msg.type === 'roomClosed').map((o) => o.to)).toEqual(['b'])
  })

  it('座位保留只数真人：练习桌真人掉线保留 5 分钟', () => {
    const { table: t, last } = make({ capacity: 2 })
    t.join('human', '我', 0)
    t.addBot('beginner', 0)
    last().finish()
    t.tick(1)
    expect(t.phase).toBe('waiting')

    t.setConnected('human', false, 1000)
    expect(t.view().seats[0]!.connected).toBe(false)
    t.tick(1000 + FRIEND_SEAT_GRACE_MS - 1)
    expect(t.members).toEqual(['human', 'bot:123456:1:1'])
    expect(t.isClosed).toBe(false)
    t.tick(1000 + FRIEND_SEAT_GRACE_MS)
    // 真人座位释放后桌上只剩电脑 → 立即关桌
    expect(t.isClosed).toBe(true)
    expect(t.members).toEqual([])
  })

  it('lastResult.botIds 列出本局电脑', () => {
    const { table: t, last } = make({ capacity: 3 })
    t.join('human', '我', 0)
    t.addBot('advanced', 0)
    t.addBot('advanced', 0)
    last().finish()
    t.tick(1)
    expect(t.view().lastResult).toEqual({
      ...last().result!,
      botIds: ['bot:123456:1:1', 'bot:123456:2:2'],
    })

    // 全真人的桌：botIds 为空表
    const f = make({ kind: 'friend', capacity: 2 })
    f.table.join('a', 'A', 0)
    f.table.join('b', 'B', 0)
    f.table.setReady('a', true, f.table.rulesVersion, 0)
    f.table.setReady('b', true, f.table.rulesVersion, 0)
    f.last().finish()
    f.table.tick(1)
    expect(f.table.view().lastResult!.botIds).toEqual([])
  })

  it('练习桌没有房主：hostId 恒为 null，谁改规则都是 NOT_HOST', () => {
    const { table: t } = make({ capacity: 2 })
    t.join('human', '我', 0)
    t.addBot('beginner', 0)
    expect(t.view().hostId).toBeNull()
    expect(errorOf(t.updateRules('human', rules, 1))).toBe('NOT_HOST')
    expect(t.rules).toEqual(rules)
  })

  it('humanMembers / hasHumans 只数真人', () => {
    const { table: t } = make({ capacity: 3 })
    t.join('human', '我', 0)
    t.addBot('beginner', 0)
    t.addBot('beginner', 0)
    expect(t.members).toHaveLength(3)
    expect(t.humanMembers).toEqual(['human'])
    expect(t.hasHumans).toBe(true)
    // 对局中真人离开后座位还占着，但桌上已经没真人 → 关桌
    t.leave('human', 1)
    expect(t.humanMembers).toEqual([])
    expect(t.hasHumans).toBe(false)
  })

  it('addBot：对局中或满座 → 返回 []，座位不变', () => {    // 满座
    const full = make({ kind: 'match', capacity: 3 })
    full.table.join('a', 'A', 0)
    full.table.join('b', 'B', 0)
    full.table.addBot('beginner', 0)
    expect(full.table.members).toEqual(['a', 'b', 'bot:123456:2:1'])
    expect(full.table.phase).toBe('inGame') // 首局人满即开
    expect(full.table.addBot('beginner', 1)).toEqual([])
    expect(full.table.members).toEqual(['a', 'b', 'bot:123456:2:1'])

    // 对局中
    const playing = make({ capacity: 2 })
    playing.table.join('human', '我', 0)
    playing.table.addBot('beginner', 0)
    expect(playing.table.phase).toBe('inGame')
    expect(playing.table.addBot('beginner', 1)).toEqual([])
    expect(playing.table.members).toEqual(['human', 'bot:123456:1:1'])
  })
})
