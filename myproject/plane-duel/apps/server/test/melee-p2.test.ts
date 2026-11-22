/**
 * P2 对引擎的三处遗留修复（spec §20.7 M1–M3）：
 * - M1：本人视图的 submitted / pendingShot（重连后知道自己已开炮）；
 * - M2：回合中途出局当场广播 playerOut；
 * - M3：摆放阶段掉线不判出局，宽限从第 1 轮起算。
 */
import { describe, it, expect } from 'vitest'
import type { RuleSet, ServerMessage } from '@plane-duel/shared'
import { MeleeEngine } from '../src/melee-engine'
import { DuelEngine } from '../src/duel-engine'
import type { Outbound } from '../src/engine'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }
const HEADS = { a: { row: 2, col: 2 }, b: { row: 6, col: 6 }, c: { row: 2, col: 7 } } as const
type Id = keyof typeof HEADS

const fresh = () => new MeleeEngine({ rules, playerIds: ['a', 'b', 'c'], now: 0, rng: () => 0 }) // 摆放 deadline = 45_000
const started = () => {
  const e = fresh()
  for (const id of ['a', 'b', 'c'] as Id[]) e.handle(id, { type: 'placePlane', planes: [HEADS[id]] }, 0)
  return e // round 1，deadline = 20_000
}
const of = <T extends ServerMessage['type']>(out: Outbound[], to: string, type: T) =>
  out.filter((o) => o.to === to && o.msg.type === type).map((o) => o.msg as Extract<ServerMessage, { type: T }>)
const alive = (e: MeleeEngine, id: Id) => e.view(id).you.alive

describe('M1：view.you.submitted / pendingShot', () => {
  it('M1：提交后本人视图 submitted=true 且 pendingShot 为所提交格；他人视图里看不到该坐标', () => {
    const e = started()
    e.handle('a', { type: 'fire', row: 9, col: 9 }, 100)

    const va = e.view('a')
    expect(va.you.submitted).toBe(true)
    expect(va.you.pendingShot).toEqual({ row: 9, col: 9 })

    const vb = e.view('b')
    expect(vb.you.submitted).toBe(false)
    expect(vb.you.pendingShot).toBeNull()
    // 谁已提交仍是公开信息（无坐标）
    expect(vb.others.find((o) => o.playerId === 'a')!.submitted).toBe(true)
    expect(JSON.stringify(vb)).not.toContain('"row":9,"col":9')
  })

  it('M1：结算后 submitted 复位为 false、pendingShot 为 null', () => {
    const e = started()
    for (const [i, id] of (['a', 'b', 'c'] as Id[]).entries()) e.handle(id, { type: 'fire', row: 9, col: i }, 100)
    expect(e.view('a').round).toBe(2)
    for (const id of ['a', 'b', 'c'] as Id[]) {
      expect(e.view(id).you.submitted).toBe(false)
      expect(e.view(id).you.pendingShot).toBeNull()
    }
  })

  it('M1：duel 视图 submitted=false、pendingShot=null', () => {
    const d = new DuelEngine({ rules, playerIds: ['x', 'y'], now: 0, rng: () => 0 })
    d.handle('x', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    d.handle('y', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
    for (const id of ['x', 'y']) expect(d.view(id).you).toMatchObject({ submitted: false, pendingShot: null })

    d.handle(d.view('x').turn!, { type: 'fire', row: 9, col: 9 }, 100)
    for (const id of ['x', 'y']) {
      expect(d.view(id).you.submitted).toBe(false)
      expect(d.view(id).you.pendingShot).toBeNull()
    }
  })
})

describe('M2：中途出局当场广播 playerOut', () => {
  it('M2：回合中途离开 → 立即广播 playerOut，下一条 roundResult.eliminated 仍含该玩家', () => {
    const e = started()
    e.handle('a', { type: 'fire', row: 9, col: 0 }, 100)
    e.handle('b', { type: 'fire', row: 9, col: 1 }, 100)
    const out = e.handle('c', { type: 'leaveRoom' }, 200)

    for (const id of ['a', 'b', 'c']) {
      expect(of(out, id, 'playerOut')).toEqual([{ type: 'playerOut', playerId: 'c', round: 1 }])
    }
    // 当场广播：早于本条 roundResult
    const types = out.filter((o) => o.to === 'a').map((o) => o.msg.type)
    expect(types.indexOf('playerOut')).toBeLessThan(types.indexOf('roundResult'))

    expect(alive(e, 'c')).toBe(false)
    expect(of(out, 'b', 'roundResult')[0]!.eliminated).toEqual(['c'])
    expect(of(out, 'a', 'roundResult')[0]!.eliminated).toEqual(['c'])
  })

  it('M2：掉线满 30 秒出局 → playerOut 当场广播', () => {
    // 60 秒一回合，避免同一 tick 里又走到结算，突出「当场」
    const e = new MeleeEngine({ rules: { ...rules, turnSeconds: 60 }, playerIds: ['a', 'b', 'c'], now: 0, rng: () => 0 })
    for (const id of ['a', 'b', 'c'] as Id[]) e.handle(id, { type: 'placePlane', planes: [HEADS[id]] }, 0)
    e.setConnected('a', false, 1_000)

    const out = e.tick(31_000)
    expect(out.filter((o) => o.msg.type !== 'playerOut')).toEqual([])
    for (const id of ['a', 'b', 'c']) {
      expect(of(out, id, 'playerOut')).toEqual([{ type: 'playerOut', playerId: 'a', round: 1 }])
    }
    expect(alive(e, 'a')).toBe(false)
    expect(e.phase).toBe('playing')
  })
})

describe('M3：摆放阶段的掉线宽限', () => {
  it('M3：摆放阶段掉线 40 秒（摆放 45 秒）不出局，到时被自动摆放并进入第 1 轮', () => {
    const e = fresh()
    e.handle('a', { type: 'placePlane', planes: [HEADS.a] }, 0)
    e.handle('b', { type: 'placePlane', planes: [HEADS.b] }, 0)
    e.setConnected('c', false, 0)

    expect(e.tick(40_000)).toEqual([])
    expect(alive(e, 'c')).toBe(true)

    const out = e.tick(45_000)
    expect(of(out, 'c', 'planeAccepted')).toHaveLength(1)
    expect(of(out, 'a', 'phaseChanged')).toEqual([{ type: 'phaseChanged', phase: 'playing', deadlineAt: 65_000, round: 1 }])
    expect(of(out, 'a', 'playerOut')).toEqual([])
    expect(alive(e, 'c')).toBe(true)
  })

  it('M3：首轮开始时仍掉线 → 从第 1 轮开始再过 30 秒才出局', () => {
    const e = fresh()
    e.handle('a', { type: 'placePlane', planes: [HEADS.a] }, 0)
    e.handle('b', { type: 'placePlane', planes: [HEADS.b] }, 0)
    e.setConnected('c', false, 0)

    e.tick(45_000) // 自动摆放 c，进入第 1 轮；c 的宽限从此刻起算
    expect(e.view('a').round).toBe(1)
    expect(alive(e, 'c')).toBe(true)

    e.tick(74_999) // 29_999ms：还差 1ms，仍存活（这一 tick 只结算了第 1 轮）
    expect(alive(e, 'c')).toBe(true)

    const out = e.tick(75_000) // 30_000ms：出局
    for (const id of ['a', 'b', 'c']) {
      expect(of(out, id, 'playerOut')).toEqual([{ type: 'playerOut', playerId: 'c', round: 2 }])
    }
    expect(alive(e, 'c')).toBe(false)
  })

  it('M3：摆放阶段重连不判出局', () => {
    const e = fresh()
    e.setConnected('c', false, 0)
    const out = e.setConnected('c', true, 40_000)
    expect(out).toEqual([
      { to: 'a', msg: { type: 'presence', playerId: 'c', connected: true } },
      { to: 'b', msg: { type: 'presence', playerId: 'c', connected: true } },
    ])
    expect(alive(e, 'c')).toBe(true)
    expect(e.phase).toBe('placing')
  })
})
