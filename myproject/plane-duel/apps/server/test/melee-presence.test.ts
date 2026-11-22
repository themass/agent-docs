import { describe, it, expect } from 'vitest'
import type { RuleSet, ServerMessage } from '@plane-duel/shared'
import { MeleeEngine } from '../src/melee-engine'
import type { Outbound } from '../src/engine'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }
const HEADS = { a: { row: 2, col: 2 }, b: { row: 6, col: 6 }, c: { row: 2, col: 7 } } as const
type Id = keyof typeof HEADS
/** 每人一行谁都打不中的格子：第 n 轮打 (ROW[id], n-1) */
const ROW: Record<Id, number> = { a: 9, b: 8, c: 0 }

const fresh = () => new MeleeEngine({ rules, playerIds: ['a', 'b', 'c'], now: 0, rng: () => 0 })
const started = () => {
  const e = fresh()
  for (const id of ['a', 'b', 'c'] as Id[]) e.handle(id, { type: 'placePlane', planes: [HEADS[id]] }, 0)
  return e // round 1，deadline = 20_000
}
const fire = (e: MeleeEngine, id: Id, now: number) => {
  const round = e.view(id).round!
  return e.handle(id, { type: 'fire', row: ROW[id], col: round - 1 }, now)
}
const of = <T extends ServerMessage['type']>(out: Outbound[], to: string, type: T) =>
  out.filter((o) => o.to === to && o.msg.type === type).map((o) => o.msg as Extract<ServerMessage, { type: T }>)
const alive = (e: MeleeEngine, id: Id) => e.view(id).you.alive
/** shooters 提交后走到本轮 deadline 结算，返回结算输出 */
const playRound = (e: MeleeEngine, shooters: Id[]) => {
  const dl = e.view('b').deadlineAt!
  for (const id of shooters) fire(e, id, dl - 1000)
  return e.tick(dl)
}

describe('MeleeEngine 超时 / 挂机 / 掉线 / 离开', () => {
  it('超时未提交：本轮无炮，不代打', () => {
    const e = started()
    fire(e, 'b', 100)
    fire(e, 'c', 100)
    expect(e.tick(19_999)).toEqual([])
    const out = e.tick(20_000)
    expect(of(out, 'a', 'roundResult')[0]!.shots).toEqual([])
    expect(of(out, 'b', 'roundResult')[0]!.incoming.map((s) => s.by)).toEqual(['c'])
    expect(e.view('a').you.shots).toEqual([])
    expect(alive(e, 'a')).toBe(true)
  })

  it('连续 3 轮在线未提交 → 出局；中间提交一次则重新计数', () => {
    const e = started()
    playRound(e, ['b', 'c']) // r1 a idle 1
    playRound(e, ['b', 'c']) // r2 a idle 2
    playRound(e, ['a', 'b', 'c']) // r3 a 提交 → 0（全员提交，立即结算）
    expect(e.view('a').round).toBe(4)
    playRound(e, ['b', 'c']) // r4 idle 1
    playRound(e, ['b', 'c']) // r5 idle 2
    expect(alive(e, 'a')).toBe(true)
    const out = playRound(e, ['b', 'c']) // r6 idle 3 → 出局
    expect(of(out, 'b', 'roundResult')[0]).toMatchObject({ round: 6, eliminated: ['a'] })
    expect(alive(e, 'a')).toBe(false)
    expect(e.phase).toBe('playing')
  })

  it('掉线不暂停：其他人照常进行，phase 仍为 playing', () => {
    const e = started()
    const out = e.setConnected('a', false, 100)
    expect(out).toEqual([
      { to: 'b', msg: { type: 'presence', playerId: 'a', connected: false } },
      { to: 'c', msg: { type: 'presence', playerId: 'a', connected: false } },
    ])
    expect(e.phase).toBe('playing')
    expect(e.view('b').deadlineAt).toBe(20_000)
    expect(e.view('b').others.find((o) => o.playerId === 'a')!.connected).toBe(false)
    const r = e.tick(20_000)
    expect(of(r, 'b', 'phaseChanged')).toEqual([{ type: 'phaseChanged', phase: 'playing', deadlineAt: 40_000, round: 2 }])
    expect(e.phase).toBe('playing')
  })

  it('掉线期间不计挂机：掉线 25 秒（跨 2 轮）后回来，idle 计数为 0', () => {
    const e = started()
    e.setConnected('a', false, 1_000)
    fire(e, 'b', 10_000)
    fire(e, 'c', 10_000) // 在线存活者已齐 → r1 立即结算
    fire(e, 'b', 20_000)
    fire(e, 'c', 20_000) // r2 立即结算
    expect(e.view('b').round).toBe(3)
    expect(e.setConnected('a', true, 26_000)).toEqual([
      { to: 'b', msg: { type: 'presence', playerId: 'a', connected: true } },
      { to: 'c', msg: { type: 'presence', playerId: 'a', connected: true } },
    ])
    playRound(e, ['b', 'c']) // r3 idle 1
    playRound(e, ['b', 'c']) // r4 idle 2 —— 若掉线期间也计数，这里早已出局
    expect(alive(e, 'a')).toBe(true)
    const out = playRound(e, ['b', 'c']) // r5 idle 3
    expect(of(out, 'a', 'roundResult')[0]).toMatchObject({ round: 5, eliminated: ['a'] })
    expect(alive(e, 'a')).toBe(false)
  })

  it('掉线满 30 秒 → 出局', () => {
    const e = started()
    e.setConnected('a', false, 1_000)
    e.tick(20_000) // r1 超时结算，r2 deadline 40_000
    e.tick(30_999)
    expect(alive(e, 'a')).toBe(true)
    e.tick(31_000)
    expect(alive(e, 'a')).toBe(false)
    expect(e.view('b').others.find((o) => o.playerId === 'a')!.alive).toBe(false)
    expect(e.phase).toBe('playing')
    // 出局在本轮 roundResult 里公开；之后不再是目标
    fire(e, 'b', 32_000)
    const out = fire(e, 'c', 32_000)
    const [rb] = of(out, 'b', 'roundResult')
    expect(rb).toMatchObject({ round: 2, eliminated: ['a'] })
    expect(rb!.shots.map((s) => s.targetId)).toEqual(['c'])

    // 宽限已过、tick 还没判就重连：同样出局
    const e2 = started()
    e2.setConnected('a', false, 1_000)
    e2.setConnected('a', true, 31_500)
    expect(alive(e2, 'a')).toBe(false)
  })

  it('Review Focus #5：提交后立刻掉线，本轮那一炮仍然结算', () => {
    const e = started()
    e.handle('a', { type: 'fire', row: 5, col: 5 }, 100) // b 机身
    e.setConnected('a', false, 200)
    fire(e, 'b', 300)
    const out = fire(e, 'c', 400)
    expect(of(out, 'b', 'roundResult')[0]!.incoming).toContainEqual({ by: 'a', row: 5, col: 5, result: 'body', planeId: 'p0' })
    expect(of(out, 'a', 'roundResult')[0]!.shots).toHaveLength(2)
    expect(e.view('a').you.shots).toHaveLength(2)
  })

  it('本轮所有在线存活者都已提交、掉线者未提交 → 立即结算，不等掉线者', () => {
    const e = started()
    e.setConnected('a', false, 100)
    fire(e, 'b', 200)
    const out = fire(e, 'c', 500)
    expect(of(out, 'b', 'roundResult')).toHaveLength(1)
    expect(of(out, 'b', 'phaseChanged')).toEqual([{ type: 'phaseChanged', phase: 'playing', deadlineAt: 20_500, round: 2 }])

    // 反过来：在线者都已提交后，最后一个未提交者掉线 → 当场结算
    const e2 = started()
    fire(e2, 'b', 200)
    fire(e2, 'c', 300)
    const out2 = e2.setConnected('a', false, 700)
    expect(of(out2, 'b', 'presence')).toHaveLength(1)
    expect(of(out2, 'b', 'roundResult')).toHaveLength(1)
    expect(e2.view('b').round).toBe(2)
  })

  it('摆放阶段掉线不暂停，到时自动摆放', () => {
    const e = fresh() // placing deadline = 45_000
    e.handle('a', { type: 'placePlane', planes: [HEADS.a] }, 0)
    e.handle('b', { type: 'placePlane', planes: [HEADS.b] }, 0)
    expect(of(e.setConnected('c', false, 20_000), 'a', 'presence')).toEqual([{ type: 'presence', playerId: 'c', connected: false }])
    expect(e.phase).toBe('placing')
    expect(e.view('a').deadlineAt).toBe(45_000)
    expect(e.tick(44_999)).toEqual([])
    const out = e.tick(45_000)
    expect(of(out, 'c', 'planeAccepted')).toHaveLength(1)
    expect(of(out, 'a', 'planeAccepted')).toEqual([])
    expect(of(out, 'a', 'phaseChanged')).toEqual([{ type: 'phaseChanged', phase: 'playing', deadlineAt: 65_000, round: 1 }])
    expect(e.phase).toBe('playing')
    expect(alive(e, 'c')).toBe(true)
  })

  it('leaveRoom → 当场出局；只剩 1 人 → gameOver', () => {
    const e = started()
    fire(e, 'b', 100)
    fire(e, 'c', 100)
    // a 是唯一未提交者：离开后在线存活者已齐 → 本轮当场结算
    const out1 = e.handle('a', { type: 'leaveRoom' }, 200)
    expect(alive(e, 'a')).toBe(false)
    expect(of(out1, 'b', 'roundResult')[0]).toMatchObject({ round: 1, eliminated: ['a'] })
    expect(of(out1, 'b', 'roundResult')[0]!.shots.map((s) => s.targetId)).toEqual(['c'])
    expect(e.phase).toBe('playing')

    const out2 = e.handle('b', { type: 'leaveRoom' }, 300) // round 2
    expect(e.phase).toBe('finished')
    const result = {
      reason: 'lastStanding',
      ranking: [
        { playerId: 'c', rank: 1, eliminatedRound: null, hits: 0 },
        { playerId: 'b', rank: 2, eliminatedRound: 2, hits: 0 },
        { playerId: 'a', rank: 3, eliminatedRound: 1, hits: 0 },
      ],
    }
    expect(e.result).toEqual(result)
    expect(of(out2, 'c', 'gameOver')).toEqual([{ type: 'gameOver', result }])
  })

  it('重连收到 state（view），其中 round 与 deadlineAt 为当前值', () => {
    const e = started()
    e.setConnected('a', false, 100)
    e.tick(20_000) // → r2，deadline 40_000
    fire(e, 'b', 22_000)
    const out = e.setConnected('a', true, 25_000)
    expect(out.map((o) => o.to)).toEqual(['b', 'c'])
    expect(out.every((o) => o.msg.type === 'presence')).toBe(true)
    const v = e.view('a')
    expect(v).toMatchObject({ mode: 'melee', phase: 'playing', round: 2, deadlineAt: 40_000, turn: null })
    expect(v.you.alive).toBe(true)
    expect(v.others.find((o) => o.playerId === 'b')!.submitted).toBe(true)
  })

  it('评审 I2：提交后掉线、回合结束前宽限到期出局 → 那一炮仍然落在 b、c 棋盘上', () => {
    const e = new MeleeEngine({ rules: { ...rules, turnSeconds: 60 }, playerIds: ['a', 'b', 'c'], now: 0, rng: () => 0 })
    for (const id of ['a', 'b', 'c'] as Id[]) e.handle(id, { type: 'placePlane', planes: [HEADS[id]] }, 0)
    e.handle('a', { type: 'fire', row: 5, col: 5 }, 100) // b 机身
    e.setConnected('a', false, 200)
    e.tick(200 + 30_000)
    expect(alive(e, 'a')).toBe(false)
    fire(e, 'b', 31_000)
    const out = fire(e, 'c', 31_000)
    const [rb] = of(out, 'b', 'roundResult')
    expect(rb).toMatchObject({ round: 1, eliminated: ['a'] })
    expect(rb!.incoming).toContainEqual({ by: 'a', row: 5, col: 5, result: 'body', planeId: 'p0' })
    expect(of(out, 'c', 'roundResult')[0]!.incoming.map((s) => s.by)).toContain('a')
    expect(e.view('a').you.shots.map((s) => s.targetId).sort()).toEqual(['b', 'c'])
    // a 已出局，不再是目标
    expect(rb!.shots.map((s) => s.targetId)).toEqual(['c'])
  })

  it('评审 I2：提交后 leaveRoom，那一炮同样在本轮结算', () => {
    const e = started()
    e.handle('a', { type: 'fire', row: 5, col: 5 }, 100)
    e.handle('a', { type: 'leaveRoom' }, 150)
    fire(e, 'b', 200)
    const out = fire(e, 'c', 300)
    expect(of(out, 'b', 'roundResult')[0]!.incoming).toContainEqual({ by: 'a', row: 5, col: 5, result: 'body', planeId: 'p0' })
  })
})
