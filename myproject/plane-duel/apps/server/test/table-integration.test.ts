import { describe, it, expect } from 'vitest'
import { placeSeconds } from '@plane-duel/shared'
import type { Cell, RuleSet, ServerMessage } from '@plane-duel/shared'
import { Table } from '../src/table'
import type { TableOptions } from '../src/table'
import type { Outbound } from '../src/engine'
import { mulberry32 } from '../../../packages/shared/test/helpers'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: false }
const bigRules: RuleSet = { boardSize: 12, planeCount: 2, turnSeconds: 30, hintAllowed: true }

const ids = ['a', 'b', 'c', 'd']

/** 真实引擎（默认 createEngine），确定性随机源。 */
function make(capacity: 2 | 3 | 4, over: Partial<TableOptions> = {}) {
  const table = new Table({
    roomCode: '123456',
    kind: 'friend',
    capacity,
    rules,
    now: 0,
    rng: mulberry32(7),
    ...over,
  })
  for (const id of ids.slice(0, capacity)) table.join(id, id.toUpperCase(), 0)
  return { table, ids: ids.slice(0, capacity) }
}

function readyAll(t: Table, members: string[], now = 0): Outbound[] {
  return members.flatMap((id) => t.setReady(id, true, t.rulesVersion, now))
}

const ofType = <T extends ServerMessage['type']>(out: Outbound[], to: string, type: T) =>
  out.filter((o) => o.to === to && o.msg.type === type).map((o) => o.msg as Extract<ServerMessage, { type: T }>)

// ---- 2 人：a(2,2) b(6,6)
const DUEL_HEADS: Record<string, Cell> = { a: { row: 2, col: 2 }, b: { row: 6, col: 6 } }

function placeDuel(t: Table, now = 0): void {
  for (const id of ['a', 'b']) t.handleGame(id, { type: 'placePlane', planes: [DUEL_HEADS[id]!] }, now)
}

/** 轮到谁，谁就打对手机头，直到对局结束。返回最后一次 handleGame 的输出。 */
function finishDuel(t: Table, now = 100): Outbound[] {
  const turn = t.engine!.view('a').turn!
  const target = turn === 'a' ? 'b' : 'a'
  const head = DUEL_HEADS[target]!
  return t.handleGame(turn, { type: 'fire', row: head.row, col: head.col }, now)
}

// ---- 4 人：a(2,2) b(2,7) c(7,2) d(7,7)
const MELEE_HEADS: Record<string, Cell> = {
  a: { row: 2, col: 2 },
  b: { row: 2, col: 7 },
  c: { row: 7, col: 2 },
  d: { row: 7, col: 7 },
}

function placeMelee(t: Table, members: string[], now = 0): void {
  for (const id of members) t.handleGame(id, { type: 'placePlane', planes: [MELEE_HEADS[id]!] }, now)
}

function fireAll(t: Table, shots: Record<string, Cell>, now = 100): Outbound[] {
  return Object.entries(shots).flatMap(([id, c]) => t.handleGame(id, { type: 'fire', row: c.row, col: c.col }, now))
}

describe('Table + 真实引擎', () => {
  it('好友房 2 人：打完一局 → waiting、lastResult 有值 → 双方准备 → 第二局用当前规则', () => {
    const { table, ids: members } = make(2)
    readyAll(table, members)
    expect(table.phase).toBe('inGame')
    expect(table.engine!.mode).toBe('duel')
    placeDuel(table)
    expect(table.engine!.phase).toBe('playing')

    const turn = table.engine!.view('a').turn!
    const out = finishDuel(table)
    expect(table.phase).toBe('waiting')
    expect(table.engine).toBeNull()
    expect(ofType(out, 'a', 'gameOver')).toHaveLength(1)
    const lr = table.view().lastResult!
    expect(lr.reason).toBe('head')
    expect(lr.ranking[0]!.playerId).toBe(turn)
    // 出局后桌子广播 waiting 状态
    for (const id of members) expect(ofType(out, id, 'tableState')[0]!.table.phase).toBe('waiting')

    // 房主改规则，随后双方准备 → 第二局使用新规则
    table.updateRules('a', bigRules, 200)
    expect(table.view().rules).toEqual(bigRules)
    readyAll(table, members, 300)
    expect(table.phase).toBe('inGame')
    expect(table.view().lastResult).toBeNull()
    const v = table.engine!.view('a')
    expect(v.phase).toBe('placing')
    expect(v.deadlineAt).toBe(300 + placeSeconds(bigRules) * 1000)
    // 新规则要 2 架：只放 1 架被拒，放 2 架被接受
    const bad = table.handleGame('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 300)
    expect(bad[0]!.msg).toMatchObject({ type: 'error', code: 'INVALID_PLACEMENT' })
    const good = table.handleGame(
      'a',
      { type: 'placePlane', planes: [{ row: 2, col: 2 }, { row: 7, col: 7 }] },
      300,
    )
    expect(good[0]!.msg.type).toBe('planeAccepted')
    expect(table.engine!.view('a').you.planes).toHaveLength(2)
  })

  it('好友房 4 人混战：打完回等候室；房主改为 12×12/2 架 → 全员准备 → 新局 view.you.planes 需 2 架', () => {
    const { table, ids: members } = make(4)
    readyAll(table, members)
    expect(table.engine!.mode).toBe('melee')
    placeMelee(table, members)
    expect(table.engine!.phase).toBe('playing')

    // 第 1 轮：a 打 b，b 打 d，c 打 d，d 打 a → a、b、d 的机头都被打掉，只剩 c
    const out = fireAll(table, {
      a: MELEE_HEADS.b!,
      b: MELEE_HEADS.d!,
      c: MELEE_HEADS.d!,
      d: MELEE_HEADS.a!,
    })
    expect(table.phase).toBe('waiting')
    const lr = table.view().lastResult!
    expect(lr.reason).toBe('lastStanding')
    expect(lr.ranking[0]!.playerId).toBe('c')
    expect(lr.ranking).toHaveLength(4)
    for (const id of members) expect(ofType(out, id, 'gameOver')).toHaveLength(1)

    table.updateRules('a', bigRules, 200)
    readyAll(table, members, 300)
    expect(table.phase).toBe('inGame')
    expect(table.engine!.mode).toBe('melee')
    const one = table.handleGame('b', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 300)
    expect(one[0]!.msg).toMatchObject({ type: 'error', code: 'INVALID_PLACEMENT' })
    table.handleGame('b', { type: 'placePlane', planes: [{ row: 2, col: 2 }, { row: 7, col: 7 }] }, 300)
    expect(table.engine!.view('b').you.planes).toHaveLength(2)
    expect(table.engine!.view('b').deadlineAt).toBe(300 + placeSeconds(bigRules) * 1000)
  })

  it('Review Focus #3：准备与改规则竞态（真实引擎）', () => {
    // 情形一：满员前部分人已准备，房主改规则会清掉所有准备，最后一人准备也不能开局
    const { table, ids: members } = make(4)
    for (const id of ['b', 'c', 'd']) table.setReady(id, true, table.rulesVersion, 0)
    table.updateRules('a', bigRules, 10)
    expect(table.view().seats.every((s) => s !== null && !s.ready)).toBe(true)
    table.setReady('a', true, table.rulesVersion, 20)
    expect(table.phase).toBe('waiting')
    expect(table.engine).toBeNull()
    // 重新准备后开局，引擎用的是新规则
    for (const id of ['b', 'c', 'd']) table.setReady(id, true, table.rulesVersion, 30)
    expect(table.phase).toBe('inGame')
    expect(table.engine!.view('a').deadlineAt).toBe(30 + placeSeconds(bigRules) * 1000)

    // 情形二：已经开局后改规则被拒，规则与引擎都不变
    const rejected = table.updateRules('a', rules, 40)
    expect(rejected[0]!.msg).toMatchObject({ type: 'error', code: 'ROOM_IN_GAME' })
    expect(table.view().rules).toEqual(bigRules)
    const bad = table.handleGame('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 50)
    expect(bad[0]!.msg).toMatchObject({ type: 'error', code: 'INVALID_PLACEMENT' })

    // 情形三：对局中再准备被拒，不影响引擎
    const engine = table.engine
    const ready = table.setReady('b', true, table.rulesVersion, 60)
    expect(ready[0]!.msg).toMatchObject({ type: 'error', code: 'WRONG_PHASE' })
    expect(table.engine).toBe(engine)
    expect(members).toHaveLength(4)
  })

  it('混战中有人 leaveRoom：对局继续；本局结束后其座位被释放', () => {
    const { table, ids: members } = make(4)
    readyAll(table, members)
    placeMelee(table, members)

    const out = table.handleGame('c', { type: 'leaveRoom' }, 50)
    expect(table.phase).toBe('inGame')
    expect(table.engine!.phase).toBe('playing')
    // 座位保留到本局结束
    expect(table.members).toContain('c')
    expect(table.engine!.view('a').others.find((o) => o.playerId === 'c')!.alive).toBe(false)
    // 其余人收到桌子状态，离开者不再收到广播
    for (const id of ['a', 'b', 'd']) expect(ofType(out, id, 'tableState')).toHaveLength(1)
    expect(ofType(out, 'c', 'tableState')).toHaveLength(0)

    // 第 1 轮：全员打空；第 2 轮：a 打掉 b；第 3 轮：a 打掉 d
    fireAll(table, { a: { row: 0, col: 0 }, b: { row: 0, col: 1 }, d: { row: 0, col: 2 } })
    expect(table.engine!.phase).toBe('playing')
    expect(table.engine!.view('a').round).toBe(2)
    fireAll(table, { a: MELEE_HEADS.b!, b: { row: 0, col: 3 }, d: { row: 0, col: 4 } })
    expect(table.engine!.phase).toBe('playing')
    const last = fireAll(table, { a: MELEE_HEADS.d!, d: { row: 0, col: 5 } })

    expect(table.phase).toBe('waiting')
    expect(table.view().lastResult!.ranking[0]!.playerId).toBe('a')
    expect(table.members.sort()).toEqual(['a', 'b', 'd'])
    expect(table.view().seats[2]).toBeNull()
    for (const id of ['a', 'b', 'd']) expect(ofType(last, id, 'tableState')[0]!.table.phase).toBe('waiting')
    expect(ofType(last, 'c', 'tableState')).toHaveLength(0)

    // 释放的座位可被新人占用
    const joined = table.join('e', 'E', 500)
    expect(ofType(joined, 'e', 'tableState')).toHaveLength(1)
    expect(table.view().seats[2]!.playerId).toBe('e')
  })

  it('2 人对局中 leaveRoom：对手胜（forfeit），回到 waiting', () => {
    const { table, ids: members } = make(2)
    readyAll(table, members)
    placeDuel(table)
    expect(table.engine!.phase).toBe('playing')

    const out = table.leave('a', 100)
    expect(table.phase).toBe('waiting')
    expect(table.engine).toBeNull()
    const lr = table.view().lastResult!
    expect(lr.reason).toBe('forfeit')
    expect(lr.ranking[0]!.playerId).toBe('b')
    expect(lr.ranking[1]!.playerId).toBe('a')
    expect(ofType(out, 'b', 'gameOver')).toHaveLength(1)
    // 离开者座位释放，房主转给 b
    expect(table.members).toEqual(['b'])
    expect(table.view().hostId).toBe('b')
  })

  it('好友房开局：给每个在座者发 state，含摆放 deadlineAt', () => {
    const { table, ids: members } = make(2)
    const start = 1234
    const out = readyAll(table, members, start)
    for (const id of members) {
      const states = ofType(out, id, 'state')
      expect(states).toHaveLength(1)
      const s = states[0]!
      expect(s.table.phase).toBe('inGame')
      expect(s.game).not.toBeNull()
      expect(s.game!.phase).toBe('placing')
      expect(s.game!.deadlineAt).toBe(start + placeSeconds(rules) * 1000)
      // 同时仍广播 tableState
      expect(ofType(out, id, 'tableState').length).toBeGreaterThan(0)
    }
  })

  it('匹配房满员开局：给每个在座者发 state，含摆放 deadlineAt', () => {
    const table = new Table({ roomCode: '654321', kind: 'match', capacity: 3, rules, now: 0, rng: mulberry32(3) })
    const start = 5000
    table.join('a', 'A', start)
    table.join('b', 'B', start)
    const out = table.join('c', 'C', start)
    expect(table.phase).toBe('inGame')
    for (const id of ['a', 'b', 'c']) {
      const states = ofType(out, id, 'state')
      expect(states).toHaveLength(1)
      expect(states[0]!.game!.phase).toBe('placing')
      expect(states[0]!.game!.deadlineAt).toBe(start + placeSeconds(rules) * 1000)
      expect(ofType(out, id, 'tableState').length).toBeGreaterThan(0)
    }
  })

  it('评审 I1：准备后掉线的人在开局时被引擎视为掉线', () => {
    const { table } = make(3)
    table.setReady('a', true, table.rulesVersion, 0)
    table.setReady('b', true, table.rulesVersion, 0)
    table.setConnected('b', false, 10)
    const out = table.setReady('c', true, table.rulesVersion, 20)
    expect(table.phase).toBe('inGame')
    expect(table.engine!.view('a').others.find((o) => o.playerId === 'b')!.connected).toBe(false)
    const [sa] = ofType(out, 'a', 'state')
    expect(sa!.game!.others.find((o) => o.playerId === 'b')!.connected).toBe(false)
  })
})
