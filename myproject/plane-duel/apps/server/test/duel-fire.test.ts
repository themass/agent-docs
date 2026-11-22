import { describe, it, expect } from 'vitest'
import type { RuleSet } from '@plane-duel/shared'
import { DuelEngine } from '../src/duel-engine'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }

const started = () => {
  const r = new DuelEngine({ rules, playerIds: ['a', 'b'], now: 0, rng: () => 0 })
  r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
  r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
  return r // rng()=0 → 先手是 players[0] 即 'a'
}

const firstTurn = (r: DuelEngine) => r.view('a').turn!

describe('开炮', () => {
  it('命中机头立即结束', () => {
    const r = started()
    const turn = firstTurn(r)
    const target = turn === 'a' ? 'b' : 'a'
    const head = target === 'b' ? { row: 7, col: 7 } : { row: 2, col: 2 }
    const out = r.handle(turn, { type: 'fire', row: head.row, col: head.col }, 100)
    expect(r.phase).toBe('finished')
    expect(out.some((o) => o.msg.type === 'gameOver')).toBe(true)
    const go = out.find((o) => o.msg.type === 'gameOver')!.msg as any
    expect(go.result.ranking[0].playerId).toBe(turn)
    expect(go.result.reason).toBe('head')
    expect(r.result).toEqual(go.result)
  })

  it('命中机身不结束并换手', () => {
    const r = started()
    const turn = firstTurn(r)
    const target = turn === 'a' ? 'b' : 'a'
    const head = target === 'b' ? { row: 7, col: 7 } : { row: 2, col: 2 }
    const out = r.handle(turn, { type: 'fire', row: head.row - 1, col: head.col - 1 }, 100)
    expect(r.phase).toBe('playing')
    expect(r.view('a').turn).not.toBe(turn)
    const shot = out.find((o) => o.msg.type === 'shotResult')!.msg as any
    expect(shot.result).toBe('body')
    expect(shot.planeId).toBe('p0')
  })

  it('未命中换手', () => {
    const r = started()
    const turn = firstTurn(r)
    const out = r.handle(turn, { type: 'fire', row: 1, col: 1 }, 100)
    const shot = out.find((o) => o.msg.type === 'shotResult')!.msg as any
    expect(shot.result).toBe('miss')
  })

  it('非本方回合开炮被拒且不改变状态（Review Focus #2）', () => {
    const r = started()
    const turn = firstTurn(r)
    const waiting = turn === 'a' ? 'b' : 'a'
    const before = JSON.stringify(r.view('a'))
    const out = r.handle(waiting, { type: 'fire', row: 1, col: 1 }, 100)
    expect(out).toHaveLength(1)
    expect(out[0]!.to).toBe(waiting)
    expect(out[0]!.msg.type).toBe('error')
    expect((out[0]!.msg as any).code).toBe('NOT_YOUR_TURN')
    expect(JSON.stringify(r.view('a'))).toBe(before)
  })

  it('重复打同一格被拒且不消耗回合（Review Focus #1）', () => {
    const r = started()
    const turn = firstTurn(r)
    r.handle(turn, { type: 'fire', row: 1, col: 1 }, 100)
    const back = r.view('a').turn!
    r.handle(back, { type: 'fire', row: 9, col: 9 }, 100)
    const again = r.view('a').turn!
    const out = r.handle(again, { type: 'fire', row: 1, col: 1 }, 100)
    expect(out[0]!.msg).toMatchObject({ type: 'error', code: 'REPEAT_SHOT' })
    expect(r.view('a').turn).toBe(again)
  })

  it('摆放阶段不能开炮（Review Focus #2）', () => {
    const r = new DuelEngine({ rules, playerIds: ['a', 'b'], now: 0, rng: () => 0 })
    const out = r.handle('a', { type: 'fire', row: 1, col: 1 }, 0)
    expect(out[0]!.msg).toMatchObject({ type: 'error', code: 'WRONG_PHASE' })
    expect(r.phase).toBe('placing')
  })

  it('越界坐标被拒', () => {
    const r = started()
    const turn = firstTurn(r)
    const out = r.handle(turn, { type: 'fire', row: 10, col: 1 }, 100)
    expect(out[0]!.msg).toMatchObject({ type: 'error', code: 'OUT_OF_RANGE' })
  })

  it('两炮连击的竞态：第二次被拒（Review Focus #1）', () => {
    const r = started()
    const turn = firstTurn(r)
    const out1 = r.handle(turn, { type: 'fire', row: 1, col: 1 }, 100)
    const out2 = r.handle(turn, { type: 'fire', row: 1, col: 2 }, 100) // 同一发送方，已换手
    expect(out1.some((o) => o.msg.type === 'shotResult')).toBe(true)
    expect(out2[0]!.msg).toMatchObject({ type: 'error', code: 'NOT_YOUR_TURN' })
  })

  it('多架飞机：击落一架不结束，全部击落才结束且 reason=allPlanes', () => {
    const r2: RuleSet = { boardSize: 10, planeCount: 2, turnSeconds: 20, hintAllowed: true }
    const r = new DuelEngine({ rules: r2, playerIds: ['a', 'b'], now: 0, rng: () => 0 })
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }, { row: 2, col: 7 }] }, 0)
    r.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 2 }, { row: 7, col: 7 }] }, 0)
    const out1 = r.handle('a', { type: 'fire', row: 7, col: 2 }, 10)
    expect(out1.find((o) => o.to === 'a' && o.msg.type === 'planeDestroyed')?.msg).toEqual({
      type: 'planeDestroyed',
      ownerId: 'b',
      planeId: 'p0',
    })
    expect(out1.some((o) => o.msg.type === 'gameOver')).toBe(false)
    expect(r.phase).toBe('playing')
    expect(r.view('a').others[0]!.planesDestroyed).toBe(1)
    expect(r.view('b').you.planesDestroyed).toBe(1)
    r.handle('b', { type: 'fire', row: 0, col: 0 }, 20)
    const out2 = r.handle('a', { type: 'fire', row: 7, col: 7 }, 30)
    expect(r.phase).toBe('finished')
    const go = out2.find((o) => o.to === 'b' && o.msg.type === 'gameOver')!.msg as any
    expect(go.result.reason).toBe('allPlanes')
    expect(go.result.ranking[0].playerId).toBe('a')
  })

  it('gameOver.ranking：胜者 rank 1，负者 rank 2，hits 为累计命中格数', () => {
    const r = started()
    r.handle('a', { type: 'fire', row: 6, col: 6 }, 10) // a 打 b 机身
    r.handle('b', { type: 'fire', row: 1, col: 1 }, 20) // b 打 a 机身
    r.handle('a', { type: 'fire', row: 0, col: 0 }, 30) // miss
    r.handle('b', { type: 'fire', row: 9, col: 9 }, 40) // miss
    const out = r.handle('a', { type: 'fire', row: 7, col: 7 }, 50) // a 打 b 机头
    const go = out.find((o) => o.to === 'a' && o.msg.type === 'gameOver')!.msg as any
    expect(go.result).toEqual({
      reason: 'head',
      ranking: [
        { playerId: 'a', rank: 1, eliminatedRound: null, hits: 2 },
        { playerId: 'b', rank: 2, eliminatedRound: null, hits: 1 },
      ],
    })
  })
})
