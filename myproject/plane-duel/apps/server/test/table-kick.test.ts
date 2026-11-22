import { describe, it, expect } from 'vitest'
import type { ClientMessage, GamePhase, GameResult, GameView, Mode, RuleSet } from '@plane-duel/shared'
import { Table, MATCH_SEAT_GRACE_MS } from '../src/table'
import type { TableOptions } from '../src/table'
import type { Engine, EngineOptions, Outbound } from '../src/engine'

const rules: RuleSet = { boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false }
const otherRules: RuleSet = { boardSize: 10, planeCount: 3, turnSeconds: 30, hintAllowed: true }

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

function make(over: Partial<TableOptions> = {}) {
  return new Table({
    roomCode: '123456',
    kind: 'friend',
    capacity: 4,
    rules,
    now: 0,
    engineFactory: (o) => new FakeEngine(o),
    ...over,
  })
}

const ids = ['a', 'b', 'c', 'd']
function fill(t: Table, n = 4): void {
  for (const id of ids.slice(0, n)) t.join(id, id.toUpperCase(), 0)
}
const errorOf = (out: Outbound[]) => {
  const m = out[0]?.msg
  return m && m.type === 'error' ? m.code : null
}
/** 取出 Outbound 里的 tableState，保留投递对象，便于断言"谁收到了什么"。 */
const statesOf = (out: Outbound[]) =>
  out.flatMap((o) => (o.msg.type === 'tableState' ? [{ to: o.to, table: o.msg.table }] : []))

describe('Table 的规则版本（M4）', () => {
  it('M4：房主改规则后，带旧 rulesVersion 的准备 → STALE_RULES，准备不生效，回发 tableState', () => {
    const t = make()
    fill(t, 3)
    const stale = t.rulesVersion
    t.updateRules('a', otherRules, 0)
    expect(t.rulesVersion).toBe(stale + 1)
    expect(t.view().rulesVersion).toBe(stale + 1)

    const out = t.setReady('b', true, stale, 0)
    expect(out.map((o) => o.to)).toEqual(['b', 'b'])
    expect(errorOf(out)).toBe('STALE_RULES')
    // 补发本人的 tableState，带上新的规则与 rulesVersion（spec §20.7 M4）
    expect(out[1]).toEqual({ to: 'b', msg: { type: 'tableState', table: t.view() } })
    expect(t.view().seats[1]!.ready).toBe(false)
  })

  it('M4：带当前 rulesVersion 的准备正常生效', () => {
    const t = make()
    fill(t, 2)
    t.updateRules('a', otherRules, 0)
    const out = t.setReady('b', true, t.rulesVersion, 0)
    expect(out.every((o) => o.msg.type === 'tableState')).toBe(true)
    expect(out.map((o) => o.to).sort()).toEqual(['a', 'b'])
    expect(t.view().seats[1]!.ready).toBe(true)
  })
})

describe('房主踢人（spec §20.8）', () => {
  it('房主踢未准备者：被踢者收到 kicked，其余人 tableState 中座位空出', () => {
    const t = make()
    fill(t, 3)
    const out = t.kick('a', 'b', 0)
    expect(out.filter((o) => o.msg.type === 'kicked')).toEqual([
      { to: 'b', msg: { type: 'kicked', roomCode: t.roomCode } },
    ])
    expect(t.members).toEqual(['a', 'c'])
    expect(t.view().seats[1]).toBeNull()
    const states = statesOf(out)
    expect(states.map((s) => s.to).sort()).toEqual(['a', 'c'])
    expect(states[0]!.table.seats[1]).toBeNull()
    // 房主仍是 a：房主没被踢，不需要转移
    expect(t.view().hostId).toBe('a')
  })

  it('Review Focus #3：目标已准备 → TARGET_READY，座位不变', () => {
    const t = make()
    fill(t, 3)
    t.setReady('b', true, t.rulesVersion, 0)
    const out = t.kick('a', 'b', 0)
    expect(out).toHaveLength(1)
    expect(out[0]!.to).toBe('a')
    expect(errorOf(out)).toBe('TARGET_READY')
    expect(t.members).toEqual(['a', 'b', 'c'])
    expect(t.view().seats[1]!.ready).toBe(true)
    expect(t.canJoin('b')).toBeNull()
  })

  it('Review Focus #3：最后一人准备同步开局后再踢 → ROOM_IN_GAME', () => {
    const t = make({ capacity: 2 })
    fill(t, 2)
    t.setReady('b', true, t.rulesVersion, 0)
    t.setReady('a', true, t.rulesVersion, 0)
    expect(t.phase).toBe('inGame')
    const out = t.kick('a', 'b', 0)
    expect(out).toHaveLength(1)
    expect(out[0]!.to).toBe('a')
    expect(errorOf(out)).toBe('ROOM_IN_GAME')
    expect(t.members).toEqual(['a', 'b'])
  })

  it('Review Focus #3：被踢者再 join → BANNED；canJoin 返回 BANNED', () => {
    const t = make()
    fill(t, 3)
    t.kick('a', 'b', 0)
    expect(t.canJoin('b')).toBe('BANNED')
    const out = t.join('b', 'B', 0)
    expect(out).toHaveLength(1)
    expect(out[0]!.to).toBe('b')
    expect(errorOf(out)).toBe('BANNED')
    expect(t.members).toEqual(['a', 'c'])
    // 没被踢的人照常可以加入
    expect(t.canJoin('a')).toBeNull()
  })

  it('可以踢掉线中的未准备者', () => {
    const t = make()
    fill(t, 3)
    t.setConnected('b', false, 100)
    expect(t.view().seats[1]!.connected).toBe(false)
    const out = t.kick('a', 'b', 200)
    expect(out.some((o) => o.to === 'b' && o.msg.type === 'kicked')).toBe(true)
    expect(t.members).toEqual(['a', 'c'])
    // 座位已释放，之后不会再被判为掉线超时
    t.tick(100 + MATCH_SEAT_GRACE_MS)
    expect(t.members).toEqual(['a', 'c'])
  })

  it('非房主 / 匹配房 / 练习房 踢人 → NOT_HOST', () => {
    const t = make()
    fill(t, 3)
    const out = t.kick('b', 'c', 0)
    expect(out).toHaveLength(1)
    expect(out[0]!.to).toBe('b')
    expect(errorOf(out)).toBe('NOT_HOST')
    expect(t.members).toEqual(['a', 'b', 'c'])

    const m = make({ kind: 'match', capacity: 3 })
    m.join('a', 'A', 0)
    m.join('b', 'B', 0)
    expect(errorOf(m.kick('a', 'b', 0))).toBe('NOT_HOST')
    expect(m.members).toEqual(['a', 'b'])

    // 练习房没有房主：连"房主"都无从谈起，一律 NOT_HOST
    const p = make({ kind: 'practice', capacity: 3 })
    p.join('human', '我', 0)
    p.addBot('beginner', 0)
    const botId = 'bot:123456:1:1'
    expect(errorOf(p.kick('human', botId, 0))).toBe('NOT_HOST')
    expect(p.members).toEqual(['human', botId])
  })

  it('发起者不在桌上 → NOT_IN_ROOM', () => {
    const t = make()
    fill(t, 3)
    const out = t.kick('x', 'b', 0)
    expect(out).toHaveLength(1)
    expect(out[0]!.to).toBe('x')
    expect(errorOf(out)).toBe('NOT_IN_ROOM')
    expect(t.members).toEqual(['a', 'b', 'c'])
  })

  it('踢自己 / 踢不在桌的人 / 踢电脑 → TARGET_NOT_FOUND', () => {
    const t = make()
    fill(t, 3)
    expect(errorOf(t.kick('a', 'a', 0))).toBe('TARGET_NOT_FOUND')
    expect(errorOf(t.kick('a', 'zzz', 0))).toBe('TARGET_NOT_FOUND')
    t.addBot('beginner', 0)
    const botId = 'bot:123456:3:1'
    expect(t.members).toContain(botId)
    const out = t.kick('a', botId, 0)
    expect(out).toHaveLength(1)
    expect(out[0]!.to).toBe('a')
    expect(errorOf(out)).toBe('TARGET_NOT_FOUND')
    expect(t.members).toContain(botId)
  })

  it('kicked 只发给被踢者，且排在释放之后的 tableState 不发给被踢者', () => {
    const t = make()
    fill(t, 3)
    const out = t.kick('a', 'c', 0)
    expect(out.filter((o) => o.to === 'c').map((o) => o.msg.type)).toEqual(['kicked'])
    expect(statesOf(out).map((s) => s.to).sort()).toEqual(['a', 'b'])
    // 顺序：先 kicked，再借 release 广播 tableState
    expect(out.findIndex((o) => o.msg.type === 'kicked')).toBe(0)
    expect(out.findIndex((o) => o.msg.type === 'tableState')).toBeGreaterThan(0)
  })
})
