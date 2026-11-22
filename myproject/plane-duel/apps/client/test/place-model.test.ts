import { describe, it, expect } from 'vitest'
import type { RuleSet } from '@plane-duel/shared'
import { needsTwoStep, togglePlane } from '../src/place-model'

const rules = (boardSize: number, planeCount = 1): RuleSet => ({
  boardSize,
  planeCount,
  turnSeconds: 20,
  hintAllowed: true,
})

describe('togglePlane', () => {
  it('点空处新增一架合法飞机', () => {
    const r = togglePlane([], { row: 3, col: 4 }, rules(10, 2))
    expect(r).toEqual({ heads: [{ row: 3, col: 4 }], error: null })
  })

  it('机头贴边 → edge，heads 不变', () => {
    const heads = [{ row: 3, col: 4 }]
    expect(togglePlane(heads, { row: 0, col: 4 }, rules(10, 2))).toEqual({ heads, error: 'edge' })
    expect(togglePlane(heads, { row: 9, col: 4 }, rules(10, 2))).toEqual({ heads, error: 'edge' })
  })

  it('与已有飞机重叠 → overlap', () => {
    const heads = [{ row: 3, col: 4 }]
    // (5,4) 这架飞机的机身会压到 (3,4) 这架的机身（3×3 以机头为中心，两架在 row 4 重叠）
    expect(togglePlane(heads, { row: 5, col: 4 }, rules(10, 2))).toEqual({ heads, error: 'overlap' })
  })

  it('已放满后点空处 → full', () => {
    const heads = [{ row: 3, col: 4 }]
    expect(togglePlane(heads, { row: 6, col: 6 }, rules(10, 1))).toEqual({ heads, error: 'full' })
  })

  it('点已有飞机的任一机身格 → 移除该架', () => {
    const heads = [
      { row: 3, col: 4 },
      { row: 7, col: 7 },
    ]
    expect(togglePlane(heads, { row: 2, col: 3 }, rules(10, 2))).toEqual({
      heads: [{ row: 7, col: 7 }],
      error: null,
    })
    expect(togglePlane(heads, { row: 7, col: 7 }, rules(10, 2))).toEqual({
      heads: [{ row: 3, col: 4 }],
      error: null,
    })
  })
})

describe('needsTwoStep', () => {
  it('混战恒为两步', () => {
    expect(needsTwoStep(rules(8), 'melee')).toBe(true)
  })

  it('2 人局边长 ≥ 12 才两步', () => {
    expect(needsTwoStep(rules(10), 'duel')).toBe(false)
    expect(needsTwoStep(rules(12), 'duel')).toBe(true)
  })
})
