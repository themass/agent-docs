import { describe, it, expect } from 'vitest'
import { PRESETS } from '@plane-duel/shared'
import { clampPlanes, defaultCreateRoom, densityWarning, practiceRequest, ruleSummary } from '../src/rule-editor-model'

describe('rule-editor-model', () => {
  it('边长从 14 改到 8 时，6 架降为 2 架', () =>
    expect(clampPlanes({ boardSize: 8, planeCount: 6, turnSeconds: 20, hintAllowed: true }).planeCount).toBe(2))

  it('飞机数未超上限时保持不变，且不改动其它字段', () => {
    const r = { boardSize: 12, planeCount: 2, turnSeconds: 45 as const, hintAllowed: false }
    expect(clampPlanes(r)).toEqual(r)
  })

  it('摘要', () => expect(ruleSummary(PRESETS.advanced)).toBe('12×12 · 2 架 · 20 秒 · 无提示'))

  it('允许提示的摘要', () => expect(ruleSummary(PRESETS.standard)).toBe('10×10 · 1 架 · 20 秒 · 可用提示'))

  it('16×16 1 架给出提示，10×10 1 架不提示', () => {
    expect(densityWarning({ boardSize: 16, planeCount: 1, turnSeconds: 20, hintAllowed: true })).toBe(
      '棋盘很空，对局会比较长',
    )
    expect(densityWarning({ boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true })).toBeNull()
  })

  it('defaultCreateRoom：标准档、默认公开', () =>
    expect(defaultCreateRoom(3)).toEqual({ type: 'createRoom', capacity: 3, rules: PRESETS.standard, listed: true }))

  it('practiceRequest', () =>
    expect(practiceRequest(4, 'beginner')).toEqual({ type: 'createPractice', capacity: 4, preset: 'beginner' }))
})
