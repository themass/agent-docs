import { describe, it, expect } from 'vitest'
import type { Cell, RuleSet, ServerMessage } from '@plane-duel/shared'
import { MeleeEngine, rankPlayers } from '../src/melee-engine'
import type { Outbound } from '../src/engine'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }
const HEADS: Record<string, Cell[]> = { a: [{ row: 2, col: 2 }], b: [{ row: 6, col: 6 }], c: [{ row: 2, col: 7 }] }

const started = (heads = HEADS, r: RuleSet = rules) => {
  const e = new MeleeEngine({ rules: r, playerIds: Object.keys(heads), now: 0, rng: () => 0 })
  for (const [id, planes] of Object.entries(heads)) e.handle(id, { type: 'placePlane', planes }, 0)
  return e
}
const fire = (e: MeleeEngine, id: string, row: number, col: number, now = 100) =>
  e.handle(id, { type: 'fire', row, col }, now)
const of = <T extends ServerMessage['type']>(out: Outbound[], to: string, type: T) =>
  out.filter((o) => o.to === to && o.msg.type === type).map((o) => o.msg as Extract<ServerMessage, { type: T }>)

const ranks = (rs: { playerId: string; rank: number }[]) => rs.map((r) => [r.playerId, r.rank])

describe('rankPlayers', () => {
  it('存活者第 1，越晚出局越靠前', () =>
    expect(
      ranks(
        rankPlayers([
          { playerId: 'a', eliminatedRound: 2, hits: 3 },
          { playerId: 'b', eliminatedRound: null, hits: 1 },
          { playerId: 'c', eliminatedRound: 5, hits: 0 },
        ]),
      ),
    ).toEqual([['b', 1], ['c', 2], ['a', 3]]))

  it('同轮出局按命中数', () =>
    expect(
      ranks(
        rankPlayers([
          { playerId: 'a', eliminatedRound: null, hits: 0 },
          { playerId: 'c', eliminatedRound: 3, hits: 2 },
          { playerId: 'b', eliminatedRound: 3, hits: 4 },
        ]),
      ),
    ).toEqual([['a', 1], ['b', 2], ['c', 3]]))

  it('同轮同命中 → 并列，名次跳号', () => {
    const r = rankPlayers([
      { playerId: 'd', eliminatedRound: 1, hits: 5 },
      { playerId: 'b', eliminatedRound: 3, hits: 2 },
      { playerId: 'a', eliminatedRound: null, hits: 0 },
      { playerId: 'c', eliminatedRound: 3, hits: 2 },
    ])
    expect(r.map((x) => x.rank)).toEqual([1, 2, 2, 4])
    expect(r.map((x) => x.playerId)).toEqual(['a', 'b', 'c', 'd'])
    expect(r[3]).toEqual({ playerId: 'd', rank: 4, eliminatedRound: 1, hits: 5 })
  })

  it('Review Focus #2：最后两人同轮出局，命中数高者第 1', () =>
    expect(
      ranks(
        rankPlayers([
          { playerId: 'a', eliminatedRound: 4, hits: 3 },
          { playerId: 'b', eliminatedRound: 4, hits: 5 },
          { playerId: 'c', eliminatedRound: 2, hits: 9 },
        ]),
      ),
    ).toEqual([['b', 1], ['a', 2], ['c', 3]]))

  it('Review Focus #2：最后两人同轮出局且命中相同 → 并列第 1，ranking 里至少一个 rank 1', () => {
    const r = rankPlayers([
      { playerId: 'a', eliminatedRound: 4, hits: 3 },
      { playerId: 'b', eliminatedRound: 4, hits: 3 },
      { playerId: 'c', eliminatedRound: 2, hits: 9 },
    ])
    expect(ranks(r)).toEqual([['a', 1], ['b', 1], ['c', 3]])
    expect(r.some((x) => x.rank === 1)).toBe(true)
  })
})

describe('出局流程', () => {
  /** round 1：a 击中 b 机头，b 出局 */
  const afterBOut = () => {
    const e = started()
    fire(e, 'a', 6, 6)
    fire(e, 'b', 9, 9)
    const out = fire(e, 'c', 9, 8)
    return { e, out }
  }

  it('飞机全灭者在本轮结算后出局，roundResult.eliminated 列出', () => {
    const { e, out } = afterBOut()
    for (const id of ['a', 'b', 'c']) {
      const [rr] = of(out, id, 'roundResult')
      expect(rr!.eliminated).toEqual(['b'])
      expect(rr!.destroyed).toEqual([{ playerId: 'b', planesDestroyed: 1 }])
    }
    // b 本轮那一炮照常结算
    expect(of(out, 'b', 'roundResult')[0]!.shots).toHaveLength(2)
    expect(e.view('a').others.find((o) => o.playerId === 'b')!.alive).toBe(false)
    expect(e.view('b').you.alive).toBe(false)
    expect(e.phase).toBe('playing')
    expect(e.view('a').round).toBe(2)
  })

  it('出局者之后不再是任何人的目标（下一轮对其的 roundResult.shots 不含其 targetId）', () => {
    const { e } = afterBOut()
    const bIncoming = e.view('b').you.incoming.length
    fire(e, 'a', 9, 7)
    const out = fire(e, 'c', 9, 6) // 只等存活者，立即结算
    const [ra] = of(out, 'a', 'roundResult')
    const [rc] = of(out, 'c', 'roundResult')
    expect(ra!.shots.map((s) => s.targetId)).toEqual(['c'])
    expect(rc!.shots.map((s) => s.targetId)).toEqual(['a'])
    // 出局者仍收到公开部分，自己的 shots / incoming 为空
    expect(of(out, 'b', 'roundResult')).toEqual([
      { type: 'roundResult', round: 2, shots: [], incoming: [], destroyed: [], eliminated: [] },
    ])
    expect(e.view('b').you.incoming).toHaveLength(bIncoming)
  })

  it('出局者的提交被拒（WRONG_PHASE）', () => {
    const { e } = afterBOut()
    expect(fire(e, 'b', 0, 0)).toEqual([{ to: 'b', msg: expect.objectContaining({ type: 'error', code: 'WRONG_PHASE' }) }])
    expect(e.view('a').others.find((o) => o.playerId === 'b')!.submitted).toBe(false)
  })

  it('仅剩 1 人 → gameOver，reason=lastStanding', () => {
    const { e } = afterBOut()
    fire(e, 'a', 2, 7)
    const out = fire(e, 'c', 9, 6, 300)
    expect(e.phase).toBe('finished')
    expect(of(out, 'a', 'roundResult')[0]!.eliminated).toEqual(['c'])
    expect(of(out, 'a', 'phaseChanged')).toEqual([])
    const types = out.filter((o) => o.to === 'a').map((o) => o.msg.type)
    expect(types).toEqual(['submitted', 'roundResult', 'gameOver'])
    const result = {
      reason: 'lastStanding',
      ranking: [
        { playerId: 'a', rank: 1, eliminatedRound: null, hits: 2 }, // r1: b 机头；r2: c 机头（b 已出局，不再是目标）
        { playerId: 'c', rank: 2, eliminatedRound: 2, hits: 0 },
        { playerId: 'b', rank: 3, eliminatedRound: 1, hits: 0 },
      ],
    }
    expect(e.result).toEqual(result)
    for (const id of ['a', 'b', 'c']) expect(of(out, id, 'gameOver')).toEqual([{ type: 'gameOver', result }])
    expect(e.view('a').deadlineAt).toBeNull()
    expect(fire(e, 'a', 0, 0)).toEqual([])
    expect(e.tick(1_000_000)).toEqual([])
  })

  it('同轮全部出局 → gameOver，reason=lastStanding，按命中数决出第 1', () => {
    // a(2,2) b(3,7) c(2,7)：a 打 (2,7) = c 机头 + b 机身；b 打 a 机头；c 打 b 机头
    const e = started({ a: [{ row: 2, col: 2 }], b: [{ row: 3, col: 7 }], c: [{ row: 2, col: 7 }] })
    fire(e, 'a', 2, 7)
    fire(e, 'b', 2, 2)
    const out = fire(e, 'c', 3, 7)
    expect(e.phase).toBe('finished')
    expect(of(out, 'a', 'roundResult')[0]!.eliminated.sort()).toEqual(['a', 'b', 'c'])
    expect(e.result).toEqual({
      reason: 'lastStanding',
      ranking: [
        { playerId: 'a', rank: 1, eliminatedRound: 1, hits: 2 },
        { playerId: 'b', rank: 2, eliminatedRound: 1, hits: 1 },
        { playerId: 'c', rank: 2, eliminatedRound: 1, hits: 1 },
      ],
    })
  })

  it('多架飞机：击落一架不出局', () => {
    const two: RuleSet = { ...rules, planeCount: 2 }
    const heads = { a: [{ row: 2, col: 2 }, { row: 6, col: 6 }], b: [{ row: 2, col: 2 }, { row: 6, col: 6 }], c: [{ row: 2, col: 2 }, { row: 6, col: 6 }] }
    const e = started(heads, two)
    fire(e, 'a', 2, 2)
    fire(e, 'b', 9, 9)
    const out = fire(e, 'c', 9, 8)
    const [rb] = of(out, 'b', 'roundResult')
    expect(rb!.eliminated).toEqual([])
    expect(rb!.destroyed).toEqual([
      { playerId: 'b', planesDestroyed: 1 },
      { playerId: 'c', planesDestroyed: 1 },
    ])
    expect(e.view('b').you.alive).toBe(true)
    expect(e.phase).toBe('playing')
  })

  it('评审 I3：第 2 轮中途离开者排在同轮结算出局者之后，不会并列或夺得第 1', () => {
    const e = started()
    fire(e, 'a', 5, 5) // b 机身：a 命中 ≥ 1
    fire(e, 'b', 8, 0)
    fire(e, 'c', 0, 0)
    expect(e.view('a').round).toBe(2)
    e.handle('a', { type: 'leaveRoom' }, 200)
    fire(e, 'b', 2, 7, 300) // c 机头
    fire(e, 'c', 6, 6, 300) // b 机头
    expect(e.phase).toBe('finished')
    const ranking = e.result!.ranking
    const a = ranking.find((r) => r.playerId === 'a')!
    expect(a.rank).toBe(3)
    expect(a.eliminatedRound).toBe(2)
    expect(ranking.filter((r) => r.rank === 1).map((r) => r.playerId).sort()).toEqual(['b', 'c'])
  })
})
