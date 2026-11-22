import { describe, it, expect } from 'vitest'
import type { GamePhase, GameResult, GameView, Mode, RuleSet } from '@plane-duel/shared'
import { Table } from '../src/table'
import type { TableOptions } from '../src/table'
import type { Engine, EngineOptions, Outbound } from '../src/engine'

const rules: RuleSet = { boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false }

class FakeEngine implements Engine {
  mode: Mode = 'melee'
  phase: GamePhase = 'placing'
  result: GameResult | null = null
  constructor(readonly opts: EngineOptions) {}
  handle(): Outbound[] {
    return []
  }
  tick(): Outbound[] {
    return []
  }
  setConnected(): Outbound[] {
    return []
  }
  view(): GameView {
    return {
      mode: this.mode,
      phase: this.phase,
      deadlineAt: null,
      turn: null,
      round: null,
      you: { planes: [], planesDestroyed: 0, alive: true, shots: [], incoming: [], submitted: false, pendingShot: null },
      others: [],
    }
  }
}

function make(over: Partial<TableOptions> = {}) {
  return new Table({
    roomCode: '123456',
    tableId: 'abcd1234abcd1234',
    kind: 'friend',
    capacity: 4,
    rules,
    now: 1000,
    engineFactory: (o) => new FakeEngine(o),
    ...over,
  })
}

const ids = ['a', 'b', 'c', 'd']
function fill(t: Table, n = 4): void {
  for (const id of ids.slice(0, n)) t.join(id, `昵称${id}`, 1000)
}
const errorOf = (out: Outbound[]) => {
  const m = out[0]?.msg
  return m && m.type === 'error' ? m.code : null
}

describe('Table 的公开列表投影（spec §20.6）', () => {
  it('公开、等候中、有空座的好友房 → 条目字段正确', () => {
    const t = make({ listed: true, now: 4242 })
    fill(t, 2)
    expect(t.tableId).toBe('abcd1234abcd1234')
    expect(t.listing()).toEqual({
      tableId: 'abcd1234abcd1234',
      capacity: 4,
      rules,
      hostNickname: '昵称a',
      seated: 2,
      seats: [{ seat: 0, nickname: '昵称a' }, { seat: 1, nickname: '昵称b' }, null, null],
      createdAt: 4242,
    })
  })

  it('电脑座位与真人一样只露出 { seat, nickname }', () => {
    const t = make({ listed: true })
    fill(t, 1)
    t.addBot('beginner', 1000)
    const entry = t.listing()!
    expect(entry.seated).toBe(2)
    expect(entry.seats[1]).toEqual({ seat: 1, nickname: '电脑2' })
    expect(Object.keys(entry.seats[1]!).sort()).toEqual(['nickname', 'seat'])
  })

  it('Review Focus #5：匹配房 / 练习房 / 未公开 / 对局中 / 满座 / 已关闭 → null', () => {
    const match = make({ kind: 'match', listed: true, capacity: 3 })
    match.join('a', 'A', 1000)
    expect(match.listing()).toBeNull()
    expect(match.listed).toBe(false)

    const practice = make({ kind: 'practice', listed: true, capacity: 3 })
    practice.join('a', 'A', 1000)
    expect(practice.listing()).toBeNull()

    const unlisted = make()
    fill(unlisted, 2)
    expect(unlisted.listing()).toBeNull()

    const full = make({ listed: true })
    fill(full, 4)
    expect(full.listing()).toBeNull()

    const inGame = make({ listed: true, capacity: 2 })
    fill(inGame, 2)
    inGame.setReady('a', true, inGame.rulesVersion, 1000)
    inGame.setReady('b', true, inGame.rulesVersion, 1000)
    expect(inGame.phase).toBe('inGame')
    expect(inGame.listing()).toBeNull()

    const closed = make({ listed: true })
    fill(closed, 1)
    closed.leave('a', 1000)
    expect(closed.isClosed).toBe(true)
    expect(closed.listing()).toBeNull()
  })

  it('不再满足条件的桌子返回 null，重新满足后恢复', () => {
    const t = make({ listed: true, capacity: 2 })
    fill(t, 1)
    expect(t.listing()).not.toBeNull()
    t.join('b', 'B', 1000)
    expect(t.listing()).toBeNull()
    t.leave('b', 1000)
    expect(t.listing()?.seated).toBe(1)
  })

  it('Review Focus #5：条目 JSON 不含 roomCode 与任何 playerId', () => {
    // 用不会与昵称混淆的 id：昵称里不含 id，断言才只检验"id 是否泄漏"
    const t = make({ listed: true })
    t.join('pid-alpha', '红方', 1000)
    t.join('pid-beta', '蓝方', 1000)
    t.addBot('beginner', 1000)
    const json = JSON.stringify(t.listing())
    expect(json).not.toContain(t.roomCode)
    for (const id of t.members) expect(json).not.toContain(id)
    expect(json).not.toContain('bot')
    expect(json).not.toContain('ready')
  })

  it('房主转移后 hostNickname 随之改变', () => {
    const t = make({ listed: true })
    fill(t, 3)
    expect(t.listing()!.hostNickname).toBe('昵称a')
    t.leave('a', 1000)
    expect(t.listing()!.hostNickname).toBe('昵称b')
  })

  it('每张桌的 tableId 默认各不相同，且是 16 位十六进制', () => {
    const a = new Table({ roomCode: '111111', kind: 'friend', capacity: 2, rules, now: 0 })
    const b = new Table({ roomCode: '222222', kind: 'friend', capacity: 2, rules, now: 0 })
    expect(a.tableId).toMatch(/^[0-9a-f]{16}$/)
    expect(b.tableId).toMatch(/^[0-9a-f]{16}$/)
    expect(a.tableId).not.toBe(b.tableId)
  })
})

describe('setListed', () => {
  it('房主开启公开：广播 tableState，view().listed=true，listing() 非空', () => {
    const t = make()
    fill(t, 2)
    const out = t.setListed('a', true)
    expect(t.listed).toBe(true)
    expect(t.view().listed).toBe(true)
    expect(out.every((o) => o.msg.type === 'tableState')).toBe(true)
    expect(out.map((o) => o.to).sort()).toEqual(['a', 'b'])
    expect(t.listing()).not.toBeNull()
  })

  it('非房主 → NOT_HOST，状态不变', () => {
    const t = make()
    fill(t, 2)
    const out = t.setListed('b', true)
    expect(errorOf(out)).toBe('NOT_HOST')
    expect(t.listed).toBe(false)
  })

  it('不在房间的人 → NOT_IN_ROOM', () => {
    const t = make()
    fill(t, 1)
    expect(errorOf(t.setListed('zzz', true))).toBe('NOT_IN_ROOM')
  })

  it('匹配房 / 练习房 → NOT_HOST', () => {
    const m = make({ kind: 'match', capacity: 3 })
    m.join('a', 'A', 1000)
    expect(errorOf(m.setListed('a', true))).toBe('NOT_HOST')
    expect(m.listed).toBe(false)
    const p = make({ kind: 'practice', capacity: 3 })
    p.join('a', 'A', 1000)
    expect(errorOf(p.setListed('a', true))).toBe('NOT_HOST')
  })

  it('对局中 → ROOM_IN_GAME', () => {
    const t = make({ capacity: 2 })
    fill(t, 2)
    t.setReady('a', true, t.rulesVersion, 1000)
    t.setReady('b', true, t.rulesVersion, 1000)
    expect(errorOf(t.setListed('a', true))).toBe('ROOM_IN_GAME')
    expect(t.listed).toBe(false)
  })

  it('房主关闭公开后 listing() 为 null，view().listed=false', () => {
    const t = make({ listed: true })
    fill(t, 2)
    expect(t.listing()).not.toBeNull()
    const out = t.setListed('a', false)
    expect(out.every((o) => o.msg.type === 'tableState')).toBe(true)
    expect(t.listing()).toBeNull()
    expect(t.view().listed).toBe(false)
  })
})
