import { describe, it, expect } from 'vitest'
import type { RuleSet } from '@plane-duel/shared'
import { DuelEngine } from '../src/duel-engine'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }
// placeSeconds(rules) = 30 + 15 × 1 = 45 秒
const PLACE_MS = 45_000

const placing = (r: RuleSet = rules) => new DuelEngine({ rules: r, playerIds: ['a', 'b'], now: 0, rng: () => 0 })

const playing = (r: RuleSet = rules) => {
  const e = placing(r)
  e.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
  e.handle('b', { type: 'placePlane', planes: [{ row: 7, col: 7 }] }, 0)
  return e
}

describe('回合计时', () => {
  it('未到 20 秒什么都不做', () => {
    const r = playing()
    expect(r.tick(19999)).toEqual([])
  })

  it('到 20 秒时代打一炮并换手', () => {
    const r = playing()
    const turn = r.view('a').turn
    const out = r.tick(20000)
    expect(out.some((o) => o.msg.type === 'shotResult')).toBe(true)
    expect(r.view('a').turn).not.toBe(turn)
  })

  it('回合时长取自 rules（15 秒）', () => {
    const r = playing({ ...rules, turnSeconds: 15 })
    expect(r.view('a').deadlineAt).toBe(15000)
    expect(r.tick(14999)).toEqual([])
    const out = r.tick(15000)
    const shot = out.find((o) => o.msg.type === 'shotResult')?.msg as any
    expect(shot.by).toBe('a')
    expect(r.view('a').deadlineAt).toBe(30000)
  })

  it('代打一定选未打过的格子', () => {
    const r = playing()
    const turn = r.view('a').turn!
    r.handle(turn, { type: 'fire', row: 1, col: 1 }, 100)
    // 现在对手回合，等对手超时
    const out = r.tick(100 + 20000)
    const shot = out.find((o) => o.msg.type === 'shotResult')?.msg as any
    expect([shot.row, shot.col]).not.toEqual([1, 1])
  })

  it('连续 tick 不会重复代打', () => {
    const r = playing()
    r.tick(20000)
    expect(r.tick(20001)).toEqual([])
  })
})

describe('摆放计时', () => {
  it('摆放时长到点未摆自动落子', () => {
    const r = placing()
    expect(r.tick(PLACE_MS - 1)).toEqual([])
    const out = r.tick(PLACE_MS)
    expect(out.some((o) => o.msg.type === 'planeAccepted')).toBe(true)
  })

  it('自动落子后双方都摆好则进入 playing', () => {
    const r = placing()
    r.handle('a', { type: 'placePlane', planes: [{ row: 2, col: 2 }] }, 0)
    const out = r.tick(PLACE_MS)
    expect(r.phase).toBe('playing')
    expect(out.filter((o) => o.msg.type === 'planeAccepted').map((o) => o.to)).toEqual(['b'])
    expect(r.view('a').deadlineAt).toBe(PLACE_MS + 20000)
  })

  it('自动落子的位置合法', () => {
    const r = placing()
    r.tick(PLACE_MS)
    const v = r.view('a')
    const p = v.you.planes[0]!
    expect(p.row).toBeGreaterThanOrEqual(1)
    expect(p.row).toBeLessThanOrEqual(8)
  })

  it('摆放超时不判负（spec §二）', () => {
    const r = placing()
    const out = r.tick(PLACE_MS)
    expect(out.some((o) => o.msg.type === 'gameOver')).toBe(false)
  })

  it('摆放 deadline 以开局时刻为基准，而非绝对值（真实时钟回归）', () => {
    const T = 1_700_000_000_000
    const r = new DuelEngine({ rules, playerIds: ['a', 'b'], rng: () => 0, now: T })
    expect(r.tick(T + 1000)).toEqual([])
    expect(r.view('a').deadlineAt).toBe(T + PLACE_MS)
  })
})
