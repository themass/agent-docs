import { describe, it, expect } from 'vitest'
import type { ClientMessage, GamePhase, GameResult, GameView, Mode, RuleSet } from '@plane-duel/shared'
import { Table, FRIEND_SEAT_GRACE_MS, MATCH_SEAT_GRACE_MS } from '../src/table'
import type { TableOptions } from '../src/table'
import type { Engine, EngineOptions, Outbound } from '../src/engine'

const rules: RuleSet = { boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false }
const otherRules: RuleSet = { boardSize: 10, planeCount: 3, turnSeconds: 30, hintAllowed: true }

class FakeEngine implements Engine {
  mode: Mode = 'melee'
  phase: GamePhase = 'placing'
  result: GameResult | null = null
  calls: { playerId: string; msg: ClientMessage; now: number }[] = []
  connectedCalls: { playerId: string; connected: boolean; now: number }[] = []
  tickCalls: number[] = []
  constructor(readonly opts: EngineOptions) {}
  handle(playerId: string, msg: ClientMessage, now: number): Outbound[] {
    this.calls.push({ playerId, msg, now })
    return [{ to: playerId, msg: { type: 'planeAccepted', planes: [] } }]
  }
  tick(now: number): Outbound[] {
    this.tickCalls.push(now)
    return []
  }
  setConnected(playerId: string, connected: boolean, now: number): Outbound[] {
    this.connectedCalls.push({ playerId, connected, now })
    return []
  }
  view(playerId: string): GameView {
    return {
      mode: this.mode,
      phase: this.phase,
      deadlineAt: null,
      turn: null,
      round: null,
      you: { planes: [], planesDestroyed: 0, alive: true, shots: [], incoming: [], submitted: false, pendingShot: null },
      others: this.opts.playerIds.filter((id) => id !== playerId).map((id) => ({
        playerId: id, connected: true, alive: true, planesDestroyed: 0, submitted: false,
      })),
    }
  }
  finish(): void {
    this.phase = 'finished'
    this.result = {
      reason: 'lastStanding',
      ranking: this.opts.playerIds.map((id, i) => ({ playerId: id, rank: i + 1, eliminatedRound: null, hits: 0 })),
    }
  }
}

function make(over: Partial<TableOptions> = {}) {
  const engines: FakeEngine[] = []
  const table = new Table({
    roomCode: '123456',
    kind: 'friend',
    capacity: 4,
    rules,
    now: 0,
    engineFactory: (o) => {
      const e = new FakeEngine(o)
      engines.push(e)
      return e
    },
    ...over,
  })
  return { table, engines, last: () => engines[engines.length - 1]! }
}

const ids = ['a', 'b', 'c', 'd']
function fill(t: Table, n = 4): void {
  for (const id of ids.slice(0, n)) t.join(id, id.toUpperCase(), 0)
}
function readyAll(t: Table, n = 4): void {
  for (const id of ids.slice(0, n)) t.setReady(id, true, t.rulesVersion, 0)
}
const errorOf = (out: Outbound[]) => {
  const m = out[0]?.msg
  return m && m.type === 'error' ? m.code : null
}
const toSet = (out: Outbound[]) => out.map((o) => o.to).sort()

describe('Table', () => {
  it('好友房：人满且全员准备才开局，开局后清空准备', () => {
    const { table: t } = make()
    fill(t)
    expect(t.engine).toBeNull()
    t.setReady('a', true, t.rulesVersion, 0)
    t.setReady('b', true, t.rulesVersion, 0)
    t.setReady('c', true, t.rulesVersion, 0)
    expect(t.engine).toBeNull()
    expect(t.phase).toBe('waiting')
    t.setReady('d', true, t.rulesVersion, 0)
    expect(t.engine).not.toBeNull()
    expect(t.view().seats.every((s) => s && !s.ready)).toBe(true)
    expect(t.phase).toBe('inGame')
  })

  it('好友房：人未满时全员准备也不开局；取消准备生效', () => {
    const { table: t } = make()
    fill(t, 3)
    readyAll(t, 3)
    expect(t.engine).toBeNull()
    t.setReady('a', false, t.rulesVersion, 0)
    expect(t.view().seats[0]!.ready).toBe(false)
  })

  it('引擎以座位顺序的 playerIds 与当前规则创建', () => {
    const { table: t, last } = make({ now: 5, capacity: 2 })
    t.join('a', 'A', 5)
    t.join('b', 'B', 5)
    t.setReady('a', true, t.rulesVersion, 7)
    t.setReady('b', true, t.rulesVersion, 9)
    expect(last().opts.playerIds).toEqual(['a', 'b'])
    expect(last().opts.now).toBe(9)
  })

  it('匹配房：人满自动开局', () => {
    const { table: t } = make({ kind: 'match', capacity: 3 })
    t.join('a', 'A', 0)
    t.join('b', 'B', 0)
    expect(t.engine).toBeNull()
    t.join('c', 'C', 0)
    expect(t.engine).not.toBeNull()
    expect(t.phase).toBe('inGame')
  })

  it('房主改规则清空所有人准备并广播', () => {
    const { table: t } = make()
    fill(t)
    t.setReady('b', true, t.rulesVersion, 0)
    t.setReady('c', true, t.rulesVersion, 0)
    const out = t.updateRules('a', otherRules, 0)
    expect(toSet(out)).toEqual(ids)
    expect(out.every((o) => o.msg.type === 'tableState')).toBe(true)
    expect(t.rules).toEqual(otherRules)
    expect(t.view().rules).toEqual(otherRules)
    expect(t.view().seats.every((s) => s && !s.ready)).toBe(true)
  })

  it('非房主改规则 → NOT_HOST；匹配房改规则 → NOT_HOST', () => {
    const { table: t } = make()
    fill(t)
    const out = t.updateRules('b', otherRules, 0)
    expect(out).toHaveLength(1)
    expect(out[0]!.to).toBe('b')
    expect(errorOf(out)).toBe('NOT_HOST')
    expect(t.rules).toEqual(rules)

    const { table: m } = make({ kind: 'match', capacity: 3 })
    m.join('a', 'A', 0)
    m.join('b', 'B', 0)
    expect(errorOf(m.updateRules('a', otherRules, 0))).toBe('NOT_HOST')
    expect(m.rules).toEqual(rules)
  })

  it('Review Focus #3：最后一人准备即同步开局，之后改规则 → ROOM_IN_GAME，引擎用的是开局时的规则', () => {
    const { table: t, engines } = make()
    fill(t)
    t.updateRules('a', otherRules, 0)
    readyAll(t)
    expect(engines).toHaveLength(1)
    expect(engines[0]!.opts.rules).toEqual(otherRules)
    expect(errorOf(t.updateRules('a', rules, 0))).toBe('ROOM_IN_GAME')
    expect(engines[0]!.opts.rules).toEqual(otherRules)
    expect(t.rules).toEqual(otherRules)
  })

  it('对局中加入 → ROOM_IN_GAME；满员加入 → ROOM_FULL', () => {
    const { table: t } = make({ capacity: 3 })
    fill(t, 3)
    expect(errorOf(t.join('x', 'X', 0))).toBe('ROOM_FULL')
    readyAll(t, 3)
    const out = t.join('x', 'X', 0)
    expect(out).toHaveLength(1)
    expect(out[0]!.to).toBe('x')
    expect(errorOf(out)).toBe('ROOM_IN_GAME')
    expect(t.members).toEqual(['a', 'b', 'c'])
  })

  it('已在座者再次加入：只回 stateFor', () => {
    const { table: t } = make()
    fill(t, 2)
    const out = t.join('a', 'A', 0)
    expect(out).toEqual([t.stateFor('a')])
    expect(t.members).toEqual(['a', 'b'])
  })

  it('join 广播 tableState 给全体在座者（含新人），昵称被清洗', () => {
    const { table: t } = make()
    t.join('a', 'A', 0)
    const out = t.join('b', '  \u0000Bob  ', 0)
    expect(toSet(out)).toEqual(['a', 'b'])
    const m = out[0]!.msg
    expect(m.type).toBe('tableState')
    expect(t.view().seats[1]!.nickname).toBe('Bob')
    expect(t.view().seats[1]!.seat).toBe(1)
  })

  it('空昵称回退为 玩家N', () => {
    const { table: t } = make()
    t.join('a', '', 0)
    expect(t.view().seats[0]!.nickname).toBe('玩家1')
  })

  it('setNickname 更新并广播', () => {
    const { table: t } = make()
    fill(t, 2)
    const out = t.setNickname('b', 'Zed')
    expect(toSet(out)).toEqual(['a', 'b'])
    expect(t.view().seats[1]!.nickname).toBe('Zed')
  })

  it('非成员 setReady / updateRules → NOT_IN_ROOM', () => {
    const { table: t } = make()
    fill(t, 2)
    expect(errorOf(t.setReady('x', true, t.rulesVersion, 0))).toBe('NOT_IN_ROOM')
    expect(errorOf(t.updateRules('x', otherRules, 0))).toBe('NOT_IN_ROOM')
  })

  it('对局中 setReady → WRONG_PHASE', () => {
    const { table: t } = make({ kind: 'match', capacity: 2 })
    fill(t, 2)
    expect(errorOf(t.setReady('a', true, t.rulesVersion, 0))).toBe('WRONG_PHASE')
  })

  it('初始视图：房主为首个加入者，匹配房无房主', () => {
    const { table: t } = make()
    expect(t.view().hostId).toBeNull()
    fill(t, 2)
    expect(t.view().hostId).toBe('a')
    expect(t.view().seats).toHaveLength(4)
    expect(t.view().seats[2]).toBeNull()
    expect(t.view().lastResult).toBeNull()
    // P2 新字段：真人的座位 bot=false
    expect(t.view().seats.map((s) => s && s.bot)).toEqual([false, false, null, null])
    expect(t.view().rulesVersion).toBe(0)
    expect(t.view().listed).toBe(false)
    const { table: m } = make({ kind: 'match', capacity: 2 })
    m.join('a', 'A', 0)
    expect(m.view().hostId).toBeNull()
  })

  it('handleGame：无引擎 → WRONG_PHASE；有引擎则转发', () => {
    const { table: t, last } = make({ capacity: 2 })
    fill(t, 2)
    expect(errorOf(t.handleGame('a', { type: 'fire', row: 0, col: 0 }, 0))).toBe('WRONG_PHASE')
    readyAll(t, 2)
    const msg: ClientMessage = { type: 'placePlane', planes: [{ row: 1, col: 1 }] }
    const out = t.handleGame('a', msg, 42)
    expect(last().calls).toEqual([{ playerId: 'a', msg, now: 42 }])
    expect(out[0]!.msg.type).toBe('planeAccepted')
  })

  it('stateFor 带上本人的 game 视图；无引擎时 game 为 null', () => {
    const { table: t, last } = make({ capacity: 2 })
    fill(t, 2)
    expect(t.stateFor('a')).toEqual({ to: 'a', msg: { type: 'state', table: t.view(), game: null } })
    readyAll(t, 2)
    expect(t.stateFor('a')).toEqual({ to: 'a', msg: { type: 'state', table: t.view(), game: last().view('a') } })
  })

  it('引擎结束 → 回到 waiting、记录 lastResult、丢弃引擎', () => {
    const { table: t, last } = make({ capacity: 2 })
    fill(t, 2)
    readyAll(t, 2)
    const e = last()
    e.finish()
    const out = t.tick(1000)
    expect(t.phase).toBe('waiting')
    expect(t.engine).toBeNull()
    expect(t.view().lastResult).toEqual({ ...e.result!, botIds: [] })
    expect(t.view().phase).toBe('waiting')
    const states = out.filter((o) => o.msg.type === 'tableState')
    expect(toSet(states)).toEqual(['a', 'b'])
  })

  it('handleGame / setConnected 之后也会检查引擎结束', () => {
    const { table: t, last } = make({ capacity: 2 })
    fill(t, 2)
    readyAll(t, 2)
    last().finish()
    t.handleGame('a', { type: 'fire', row: 0, col: 0 }, 5)
    expect(t.phase).toBe('waiting')
    readyAll(t, 2)
    expect(t.phase).toBe('inGame')
    last().finish()
    t.setConnected('a', false, 6)
    expect(t.phase).toBe('waiting')
  })

  it('下一局开始时 lastResult 清空，引擎是新建的', () => {
    const { table: t, engines } = make({ capacity: 2 })
    fill(t, 2)
    readyAll(t, 2)
    engines[0]!.finish()
    t.tick(1)
    expect(t.view().lastResult).not.toBeNull()
    readyAll(t, 2)
    expect(engines).toHaveLength(2)
    expect(t.view().lastResult).toBeNull()
    expect(t.phase).toBe('inGame')
  })

  it('tick 在对局中转发给引擎并带出其输出', () => {
    const { table: t, last } = make({ capacity: 2 })
    fill(t, 2)
    readyAll(t, 2)
    t.tick(77)
    expect(last().tickCalls).toEqual([77])
  })

  it('房主在等候室离开 → 房主转给最小座位号', () => {
    const { table: t } = make()
    fill(t)
    const out = t.leave('a', 0)
    expect(t.view().hostId).toBe('b')
    expect(t.view().seats[0]).toBeNull()
    expect(t.members).toEqual(['b', 'c', 'd'])
    expect(toSet(out.filter((o) => o.msg.type === 'tableState'))).toEqual(['b', 'c', 'd'])
    // 座位空出后由下一个加入者补最小空位
    t.join('e', 'E', 0)
    expect(t.view().seats[0]!.playerId).toBe('e')
    expect(t.view().hostId).toBe('b')
  })

  it('等候室非成员 leave → 空', () => {
    const { table: t } = make()
    fill(t, 2)
    expect(t.leave('x', 0)).toEqual([])
  })

  it('匹配房打完一局后有人离开 → 其余人收到 roomClosed，isClosed', () => {
    const { table: t, last } = make({ kind: 'match', capacity: 3 })
    fill(t, 3)
    last().finish()
    t.tick(1)
    expect(t.isClosed).toBe(false)
    const out = t.leave('c', 2)
    expect(t.isClosed).toBe(true)
    expect(out.filter((o) => o.msg.type === 'roomClosed').map((o) => o.to).sort()).toEqual(['a', 'b'])
  })

  it('好友房打完一局后有人离开 → 只释放座位，不关桌', () => {
    const { table: t, last } = make({ capacity: 3 })
    fill(t, 3)
    readyAll(t, 3)
    last().finish()
    t.tick(1)
    const out = t.leave('c', 2)
    expect(t.isClosed).toBe(false)
    expect(out.some((o) => o.msg.type === 'roomClosed')).toBe(false)
    expect(t.members).toEqual(['a', 'b'])
  })

  it('匹配房首局开始前有人离开 → 只释放座位，不关桌', () => {
    const { table: t } = make({ kind: 'match', capacity: 3 })
    t.join('a', 'A', 0)
    t.join('b', 'B', 0)
    t.leave('b', 1)
    expect(t.isClosed).toBe(false)
    expect(t.members).toEqual(['a'])
  })

  it('R2：好友房里还有别人在座时，掉线者 60 秒后让出座位；59 秒内回来保留', () => {
    const { table: t } = make()
    fill(t, 2)
    t.setConnected('b', false, 1000)
    expect(t.view().seats[1]!.connected).toBe(false)
    t.tick(1000 + MATCH_SEAT_GRACE_MS - 1)
    expect(t.members).toEqual(['a', 'b'])
    t.tick(1000 + MATCH_SEAT_GRACE_MS)
    expect(t.members).toEqual(['a'])

    t.join('c', 'C', 400_000)
    t.setConnected('c', false, 400_000)
    t.tick(400_000 + MATCH_SEAT_GRACE_MS - 1)
    t.setConnected('c', true, 400_000 + MATCH_SEAT_GRACE_MS - 1)
    expect(t.view().seats[1]!.connected).toBe(true)
    t.tick(400_000 + FRIEND_SEAT_GRACE_MS * 3)
    expect(t.members).toEqual(['a', 'c'])
  })

  it('R2：掉线者是唯一在座者（房主切出去发房间号）→ 座位保留 5 分钟', () => {
    const { table: t } = make()
    t.join('a', 'A', 0)
    t.setConnected('a', false, 1000)
    t.tick(1000 + MATCH_SEAT_GRACE_MS)
    t.tick(1000 + FRIEND_SEAT_GRACE_MS - 1)
    expect(t.members).toEqual(['a'])
    expect(t.isClosed).toBe(false)
    t.tick(1000 + FRIEND_SEAT_GRACE_MS)
    expect(t.isClosed).toBe(true)
  })

  it('FRIEND_SEAT_GRACE_MS = 300000, MATCH_SEAT_GRACE_MS = 60000', () => {
    expect(FRIEND_SEAT_GRACE_MS).toBe(300_000)
    expect(MATCH_SEAT_GRACE_MS).toBe(60_000)
  })

  it('匹配房等候室掉线 60 秒后让出座位；59 秒内回来保留', () => {
    const { table: t } = make({ kind: 'match', capacity: 3 })
    t.join('a', 'A', 0)
    t.join('b', 'B', 0)
    t.setConnected('b', false, 1000)
    t.tick(1000 + MATCH_SEAT_GRACE_MS - 1000)
    expect(t.members).toEqual(['a', 'b'])
    t.tick(1000 + MATCH_SEAT_GRACE_MS)
    expect(t.members).toEqual(['a'])

    t.join('c', 'C', 100_000)
    t.setConnected('c', false, 100_000)
    t.setConnected('c', true, 159_000)
    t.tick(100_000 + MATCH_SEAT_GRACE_MS * 5)
    expect(t.members).toEqual(['a', 'c'])
  })

  it('匹配房打完一局后等候室掉线超时 → 视同离开，关桌', () => {
    const { table: t, last } = make({ kind: 'match', capacity: 2 })
    fill(t, 2)
    last().finish()
    t.tick(1000)
    t.setConnected('b', false, 2000)
    const out = t.tick(2000 + MATCH_SEAT_GRACE_MS)
    expect(t.isClosed).toBe(true)
    expect(out.filter((o) => o.msg.type === 'roomClosed').map((o) => o.to)).toEqual(['a'])
  })

  it('所有人离开 → isClosed', () => {
    const { table: t } = make()
    fill(t, 2)
    t.leave('a', 0)
    expect(t.isClosed).toBe(false)
    t.leave('b', 0)
    expect(t.isClosed).toBe(true)
    expect(t.members).toEqual([])
  })

  it('关闭后的桌子拒绝加入', () => {
    const { table: t } = make()
    t.join('a', 'A', 0)
    t.leave('a', 0)
    expect(errorOf(t.join('b', 'B', 0))).toBe('ROOM_NOT_FOUND')
  })

  it('对局中 leave 转发给引擎，座位到本局结束才释放', () => {
    const { table: t, last } = make({ capacity: 3 })
    fill(t, 3)
    readyAll(t, 3)
    const out = t.leave('c', 50)
    expect(last().calls).toEqual([{ playerId: 'c', msg: { type: 'leaveRoom' }, now: 50 }])
    expect(t.view().seats[2]).not.toBeNull()
    expect(t.members).toEqual(['a', 'b', 'c'])
    expect(t.phase).toBe('inGame')
    expect(out.some((o) => o.to === 'c' && o.msg.type === 'planeAccepted')).toBe(true)
    // 本局结束时释放
    last().finish()
    t.tick(100)
    expect(t.view().seats[2]).toBeNull()
    expect(t.members).toEqual(['a', 'b'])
    expect(t.isClosed).toBe(false)
  })

  it('对局中收到 leaveRoom 消息（handleGame）等同于 leave', () => {
    const { table: t, last } = make({ capacity: 2 })
    fill(t, 2)
    readyAll(t, 2)
    t.handleGame('b', { type: 'leaveRoom' }, 9)
    expect(last().calls).toHaveLength(1)
    last().finish()
    t.tick(10)
    expect(t.members).toEqual(['a'])
  })

  it('对局中离开的人不再收到后续 tableState 广播；匹配房结束后关桌', () => {
    const { table: t, last } = make({ kind: 'match', capacity: 3 })
    fill(t, 3)
    t.leave('c', 5)
    last().finish()
    const out = t.tick(10)
    expect(t.isClosed).toBe(true)
    expect(out.filter((o) => o.msg.type === 'roomClosed').map((o) => o.to).sort()).toEqual(['a', 'b'])
    expect(out.some((o) => o.to === 'c' && (o.msg.type === 'tableState' || o.msg.type === 'roomClosed'))).toBe(false)
  })

  it('对局中全员离开且引擎结束 → isClosed', () => {
    const { table: t, last } = make({ capacity: 2 })
    fill(t, 2)
    readyAll(t, 2)
    t.leave('a', 1)
    t.leave('b', 2)
    last().finish()
    t.tick(3)
    expect(t.isClosed).toBe(true)
  })

  it('对局中 setConnected 转发给引擎并更新座位连接状态', () => {
    const { table: t, last } = make({ capacity: 2 })
    fill(t, 2)
    readyAll(t, 2)
    const out = t.setConnected('b', false, 33)
    expect(last().connectedCalls).toEqual([{ playerId: 'b', connected: false, now: 33 }])
    expect(t.view().seats[1]!.connected).toBe(false)
    expect(out.some((o) => o.msg.type === 'tableState')).toBe(true)
    // 对局中不会因为掉线而释放座位
    t.tick(33 + FRIEND_SEAT_GRACE_MS * 10)
    expect(t.members).toEqual(['a', 'b'])
  })
})
