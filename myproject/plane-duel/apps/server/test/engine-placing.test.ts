import { describe, it, expect } from 'vitest'
import { checkPlacement } from '@plane-duel/shared'
import { mulberry32 } from '../../../packages/shared/test/helpers'
import { PlacingPhase, createEngine } from '../src/engine'
import { DuelEngine } from '../src/duel-engine'
import { MeleeEngine } from '../src/melee-engine'

const rules = { boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false } as const

describe('PlacingPhase', () => {
  it('deadline = now + placeSeconds', () => expect(new PlacingPhase(rules, ['a','b','c'], 1000, () => 0).deadlineAt).toBe(1000 + 60_000))
  it('合法摆放只回给本人', () => {
    const p = new PlacingPhase(rules, ['a','b','c'], 0, () => 0)
    expect(p.place('a', [{row:2,col:2},{row:6,col:6}])).toEqual([{ to:'a', msg:{ type:'planeAccepted', planes:[{row:2,col:2},{row:6,col:6}] } }])
  })
  it('飞机数不对 / 重叠 → INVALID_PLACEMENT', () => {
    const p = new PlacingPhase(rules, ['a','b'], 0, () => 0)
    expect(p.place('a', [{row:2,col:2}])[0]!.msg).toMatchObject({ type:'error', code:'INVALID_PLACEMENT' })
    expect(p.place('a', [{row:2,col:2},{row:2,col:3}])[0]!.msg).toMatchObject({ code:'INVALID_PLACEMENT' })
  })
  it('autoPlaceMissing 只补未摆放者，且结果合法', () => {
    const p = new PlacingPhase(rules, ['a','b','c'], 0, mulberry32(1))
    p.place('a', [{row:2,col:2},{row:6,col:6}])
    const out = p.autoPlaceMissing()
    expect(out.map(o => o.to).sort()).toEqual(['b','c'])
    expect(p.allPlaced).toBe(true)
    for (const id of ['b','c']) expect(checkPlacement(p.planesOf(id)!, 12, 2)).toEqual({ ok: true })
  })
  it('自动摆放的结果只发给其本人', () => {
    const p = new PlacingPhase(rules, ['a','b','c'], 0, mulberry32(2))
    const out = p.autoPlaceMissing()
    expect(out).toHaveLength(3)
    for (const o of out) expect((o.msg as any).planes).toEqual(p.planesOf(o.to))
    expect(new Set(out.map(o => o.to)).size).toBe(3)
  })
  it('非房间成员 place → []，且不影响 allPlaced', () => {
    const p = new PlacingPhase(rules, ['a','b'], 0, () => 0)
    expect(p.place('x', [{row:2,col:2},{row:6,col:6}])).toEqual([])
    expect(p.planesOf('x')).toBeNull()
  })
  it('截止前可重摆，替换旧摆放', () => {
    const p = new PlacingPhase(rules, ['a','b'], 0, () => 0)
    p.place('a', [{row:2,col:2},{row:6,col:6}])
    p.place('a', [{row:3,col:3},{row:7,col:7}])
    expect(p.planesOf('a')).toEqual([{row:3,col:3},{row:7,col:7}])
  })
  it('非法重摆不覆盖原有合法摆放', () => {
    const p = new PlacingPhase(rules, ['a','b'], 0, () => 0)
    p.place('a', [{row:2,col:2},{row:6,col:6}])
    p.place('a', [{row:2,col:2}])
    expect(p.planesOf('a')).toEqual([{row:2,col:2},{row:6,col:6}])
  })
  it('allPlaced 需要全员摆放；extend 顺延 deadline', () => {
    const p = new PlacingPhase(rules, ['a','b'], 0, () => 0)
    p.place('a', [{row:2,col:2},{row:6,col:6}])
    expect(p.allPlaced).toBe(false)
    p.extend(5000)
    expect(p.deadlineAt).toBe(65_000)
  })
})

describe('createEngine', () => {
  it('2 人 → DuelEngine（mode duel，从 placing 开始）', () => {
    const e = createEngine({ rules, playerIds: ['a','b'], now: 0 })
    expect(e).toBeInstanceOf(DuelEngine)
    expect(e.mode).toBe('duel')
    expect(e.phase).toBe('placing')
  })
  it('3–4 人 → MeleeEngine（mode melee，从 placing 开始）', () => {
    for (const ids of [['a','b','c'], ['a','b','c','d']]) {
      const e = createEngine({ rules, playerIds: ids, now: 0 })
      expect(e).toBeInstanceOf(MeleeEngine)
      expect(e.mode).toBe('melee')
      expect(e.phase).toBe('placing')
    }
  })
  it('人数不在 2–4 → 抛错', () => {
    expect(() => createEngine({ rules, playerIds: ['a'], now: 0 })).toThrow(/2.4/)
    expect(() => createEngine({ rules, playerIds: ['a','b','c','d','e'], now: 0 })).toThrow(/2.4/)
  })
})
