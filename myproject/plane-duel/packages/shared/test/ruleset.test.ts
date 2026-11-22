import { describe, it, expect } from 'vitest'
import {
  BOARD_MIN,
  BOARD_MAX,
  PRESETS,
  maxPlanes,
  validateRuleSet,
  placeSeconds,
  planeDensity,
} from '../src/index'

describe('maxPlanes', () => {
  it('与 spec §19.3 表格一致', () => {
    const table: Record<number, number> = { 6: 1, 7: 1, 8: 2, 9: 2, 10: 3, 11: 4, 12: 4, 13: 5, 14: 6, 15: 6, 16: 6 }
    for (const [n, max] of Object.entries(table)) expect(maxPlanes(Number(n))).toBe(max)
  })
  it('上限总能被 3×3 整齐排列放下', () => {
    for (let n = BOARD_MIN; n <= BOARD_MAX; n++) expect(maxPlanes(n)).toBeLessThanOrEqual(Math.floor(n / 3) ** 2)
  })
})

describe('validateRuleSet', () => {
  it('四档预设全部合法', () => {
    for (const r of Object.values(PRESETS)) expect(validateRuleSet(r).ok).toBe(true)
  })
  it('预设数值', () => {
    expect(PRESETS.beginner).toEqual({ boardSize: 8, planeCount: 1, turnSeconds: 30, hintAllowed: true })
    expect(PRESETS.standard).toEqual({ boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true })
    expect(PRESETS.advanced).toEqual({ boardSize: 12, planeCount: 2, turnSeconds: 20, hintAllowed: false })
    expect(PRESETS.expert).toEqual({ boardSize: 14, planeCount: 3, turnSeconds: 15, hintAllowed: false })
  })
  it.each([5, 17, 10.5, '10'])('边长 %s 非法', (b) =>
    expect(validateRuleSet({ ...PRESETS.standard, boardSize: b })).toEqual({ ok: false, reason: 'boardSize' }),
  )
  it('飞机数超上限非法（10×10 最多 3 架）', () =>
    expect(validateRuleSet({ ...PRESETS.standard, planeCount: 4 })).toEqual({ ok: false, reason: 'planeCount' }))
  it('飞机数 0 非法', () =>
    expect(validateRuleSet({ ...PRESETS.standard, planeCount: 0 })).toEqual({ ok: false, reason: 'planeCount' }))
  it('回合时长不在列表中非法', () =>
    expect(validateRuleSet({ ...PRESETS.standard, turnSeconds: 25 })).toEqual({ ok: false, reason: 'turnSeconds' }))
  it('缺字段或非对象', () => {
    expect(validateRuleSet(null)).toEqual({ ok: false, reason: 'shape' })
    expect(validateRuleSet([])).toEqual({ ok: false, reason: 'shape' })
    expect(validateRuleSet({ boardSize: 10 })).toEqual({ ok: false, reason: 'shape' })
  })
  it('hintAllowed 非布尔为 shape', () =>
    expect(validateRuleSet({ ...PRESETS.standard, hintAllowed: 'yes' })).toEqual({ ok: false, reason: 'shape' }))
  it('多余字段被丢弃', () => {
    const r = validateRuleSet({ ...PRESETS.standard, cheat: true })
    expect(r.ok && Object.keys(r.rules).sort()).toEqual(['boardSize', 'hintAllowed', 'planeCount', 'turnSeconds'])
  })
})

describe('placeSeconds / planeDensity', () => {
  it('30 + 15 × 飞机数', () => {
    expect(placeSeconds(PRESETS.standard)).toBe(45)
    expect(placeSeconds(PRESETS.expert)).toBe(75)
  })
  it('占比', () => expect(planeDensity(PRESETS.standard)).toBeCloseTo(0.09))
})
