import { describe, it, expect } from 'vitest'
import type { RuleSet, ServerMessage } from '@plane-duel/shared'
import { MeleeEngine } from '../src/melee-engine'
import type { Outbound } from '../src/engine'

// 3 人：a(2,2) b(6,6) c(2,7)；10×10、1 架、20 秒
const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }
const HEADS = { a: { row: 2, col: 2 }, b: { row: 6, col: 6 }, c: { row: 2, col: 7 } } as const
type Id = keyof typeof HEADS

const started = () => {
  const e = new MeleeEngine({ rules, playerIds: ['a', 'b', 'c'], now: 0, rng: () => 0 })
  for (const id of ['a', 'b', 'c'] as Id[]) e.handle(id, { type: 'placePlane', planes: [HEADS[id]] }, 0)
  return e // round 1，deadline = 20_000
}
const fire = (e: MeleeEngine, id: string, row: number, col: number, now = 100) =>
  e.handle(id, { type: 'fire', row, col }, now)
const of = <T extends ServerMessage['type']>(out: Outbound[], to: string, type: T) =>
  out.filter((o) => o.to === to && o.msg.type === type).map((o) => o.msg as Extract<ServerMessage, { type: T }>)

describe('MeleeEngine 回合', () => {
  it('摆放完成进入 round 1，广播 phaseChanged', () => {
    const e = new MeleeEngine({ rules, playerIds: ['a', 'b', 'c'], now: 0, rng: () => 0 })
    e.handle('a', { type: 'placePlane', planes: [HEADS.a] }, 0)
    e.handle('b', { type: 'placePlane', planes: [HEADS.b] }, 0)
    const out = e.handle('c', { type: 'placePlane', planes: [HEADS.c] }, 50)
    expect(e.mode).toBe('melee')
    expect(e.phase).toBe('playing')
    for (const id of ['a', 'b', 'c'])
      expect(of(out, id, 'phaseChanged')).toEqual([{ type: 'phaseChanged', phase: 'playing', deadlineAt: 20_050, round: 1 }])
  })

  it('提交只广播 submitted，不含坐标', () => {
    const e = started()
    const out = fire(e, 'a', 9, 9)
    expect(out).toHaveLength(3)
    expect(out.map((o) => o.to).sort()).toEqual(['a', 'b', 'c'])
    for (const o of out) expect(o.msg).toEqual({ type: 'submitted', playerId: 'a', round: 1 })
    expect(JSON.stringify(out)).not.toMatch(/"row"|"col"/)
  })

  it('全员提交后立即结算，不等到时', () => {
    const e = started()
    fire(e, 'a', 9, 9)
    fire(e, 'b', 9, 8)
    expect(e.view('a').round).toBe(1)
    const out = fire(e, 'c', 9, 7, 500)
    for (const id of ['a', 'b', 'c']) {
      expect(of(out, id, 'roundResult')).toHaveLength(1)
      expect(of(out, id, 'phaseChanged')).toEqual([{ type: 'phaseChanged', phase: 'playing', deadlineAt: 20_500, round: 2 }])
    }
    expect(e.view('a').round).toBe(2)
    expect(e.view('a').deadlineAt).toBe(20_500)
    expect(e.phase).toBe('playing')
  })

  it('一炮落在每个存活对手棋盘上', () => {
    const e = started()
    fire(e, 'a', 6, 6)
    fire(e, 'b', 9, 9)
    const out = fire(e, 'c', 9, 8)
    const [ra] = of(out, 'a', 'roundResult')
    expect(ra!.round).toBe(1)
    expect(ra!.shots).toHaveLength(2)
    expect(ra!.shots).toContainEqual({ targetId: 'b', row: 6, col: 6, result: 'head', planeId: 'p0' })
    expect(ra!.shots).toContainEqual(expect.objectContaining({ targetId: 'c', row: 6, col: 6, result: 'miss' }))
    expect(ra!.destroyed).toEqual([{ playerId: 'b', planesDestroyed: 1 }])
    expect(e.view('b').you.planesDestroyed).toBe(1)
  })

  it('roundResult 按人私有：b 只看到打在自己身上的 incoming', () => {
    const e = started()
    fire(e, 'a', 5, 5) // b: body，c: miss
    fire(e, 'b', 1, 1) // a: body，c: miss
    const out = fire(e, 'c', 3, 3) // a: body，b: miss
    const [rb] = of(out, 'b', 'roundResult')
    expect(rb!.incoming).toHaveLength(2)
    expect(rb!.incoming).toContainEqual({ by: 'a', row: 5, col: 5, result: 'body', planeId: 'p0' })
    expect(rb!.incoming).toContainEqual(expect.objectContaining({ by: 'c', row: 3, col: 3, result: 'miss' }))
    expect(rb!.shots).toHaveLength(2)
    expect(rb!.shots).toContainEqual({ targetId: 'a', row: 1, col: 1, result: 'body', planeId: 'p0' })
    expect(rb!.shots).toContainEqual(expect.objectContaining({ targetId: 'c', row: 1, col: 1, result: 'miss' }))
    // a 打 c、c 打 a 的结果 b 看不到
    expect(JSON.stringify(rb)).not.toMatch(/"by":"c"[^}]*"result":"body"/)
    expect(rb!.destroyed).toEqual([])
    expect(rb!.eliminated).toEqual([])
  })

  it('Review Focus #1：发给 a 的所有消息里都没有 b 打 c 的结果', () => {
    // b 的炮全部打在 c 的机身上、却落在 a 的空白处；a、c 的炮选在谁都打不中的地方
    const bShots = [[1, 6], [1, 8], [3, 6], [3, 8], [2, 6]] as const
    const e = started()
    const toA: { round: number; msg: ServerMessage }[] = []
    for (let i = 0; i < 5; i++) {
      const outs = [fire(e, 'a', 9, i), fire(e, 'b', bShots[i]![0], bShots[i]![1]), fire(e, 'c', 8, i)]
      for (const o of outs.flat()) if (o.to === 'a') toA.push({ round: i + 1, msg: o.msg })
    }
    const results = toA.filter((m) => m.msg.type === 'roundResult')
    expect(results).toHaveLength(5)
    for (const { round, msg } of toA) {
      if (msg.type !== 'roundResult') {
        expect(JSON.stringify(msg)).not.toMatch(/"row"|"col"/)
        continue
      }
      // shots 只有 a 自己这一炮
      for (const s of msg.shots) expect([s.row, s.col]).toEqual([9, round - 1])
      // incoming 只是打在 a 棋盘上的结果（全是 miss），不是打在 c 身上的 body
      for (const s of msg.incoming) expect(s.result).toBe('miss')
    }
    // b→c 的命中（body）从未出现在发给 a 的任何消息里
    expect(JSON.stringify(toA)).not.toMatch(/"result":"body"/)
    // 确认 b→c 确实都是 body（否则上面的断言没有意义）
    expect(e.view('b').you.shots.filter((s) => s.targetId === 'c').every((s) => s.result === 'body')).toBe(true)
    expect(e.view('b').you.shots.filter((s) => s.targetId === 'c')).toHaveLength(5)
  })

  it('同一轮重复提交 → NOT_YOUR_TURN，第一次的坐标不变', () => {
    const e = started()
    fire(e, 'a', 9, 9)
    const dup = fire(e, 'a', 8, 8)
    expect(dup).toEqual([{ to: 'a', msg: expect.objectContaining({ type: 'error', code: 'NOT_YOUR_TURN' }) }])
    fire(e, 'b', 0, 0)
    const out = fire(e, 'c', 0, 1)
    const [ra] = of(out, 'a', 'roundResult')
    expect(ra!.shots.map((s) => [s.row, s.col])).toEqual([[9, 9], [9, 9]])
  })

  it('打过的格子 → REPEAT_SHOT；越界 → OUT_OF_RANGE', () => {
    const e = started()
    fire(e, 'a', 9, 9)
    fire(e, 'b', 0, 0)
    fire(e, 'c', 0, 1)
    expect(fire(e, 'a', 9, 9)).toEqual([{ to: 'a', msg: expect.objectContaining({ type: 'error', code: 'REPEAT_SHOT' }) }])
    expect(fire(e, 'a', 10, 0)).toEqual([{ to: 'a', msg: expect.objectContaining({ type: 'error', code: 'OUT_OF_RANGE' }) }])
    expect(fire(e, 'a', 0, 10)).toEqual([{ to: 'a', msg: expect.objectContaining({ type: 'error', code: 'OUT_OF_RANGE' }) }])
    // 被拒后仍可正常提交
    expect(of(fire(e, 'a', 9, 8), 'b', 'submitted')).toEqual([{ type: 'submitted', playerId: 'a', round: 2 }])
  })

  it('到时结算：只结算已提交者，未提交者本轮无炮', () => {
    const e = started()
    fire(e, 'a', 5, 5)
    expect(e.tick(19_999)).toEqual([])
    const out = e.tick(20_000)
    const [ra] = of(out, 'a', 'roundResult')
    const [rb] = of(out, 'b', 'roundResult')
    const [rc] = of(out, 'c', 'roundResult')
    expect(ra!.shots).toHaveLength(2)
    expect(rb!.shots).toEqual([])
    expect(rc!.shots).toEqual([])
    expect(rb!.incoming).toEqual([{ by: 'a', row: 5, col: 5, result: 'body', planeId: 'p0' }])
    expect(of(out, 'a', 'phaseChanged')).toEqual([{ type: 'phaseChanged', phase: 'playing', deadlineAt: 40_000, round: 2 }])
    expect(e.view('a').you.incoming).toEqual([])
  })

  it('view：others 含 submitted 标记与 planesDestroyed，不含任何坐标', () => {
    const e = started()
    fire(e, 'a', 9, 9)
    const v = e.view('b')
    expect(v).toMatchObject({ mode: 'melee', phase: 'playing', turn: null, round: 1, deadlineAt: 20_000 })
    expect(v.you.planes).toEqual([HEADS.b])
    expect(v.others).toEqual([
      { playerId: 'a', connected: true, alive: true, planesDestroyed: 0, submitted: true },
      { playerId: 'c', connected: true, alive: true, planesDestroyed: 0, submitted: false },
    ])
    expect(JSON.stringify(v.others)).not.toMatch(/"row"|"col"/)
    // 回合结算后 submitted 清零
    fire(e, 'b', 0, 0)
    fire(e, 'c', 0, 1)
    expect(e.view('b').others.every((o) => o.submitted === false)).toBe(true)
  })
})
