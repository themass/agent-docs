/**
 * P6 手感模块单测：合成计划、震动计划、静音持久化、假 AudioContext 播放冒烟。
 */
import { describe, it, expect } from 'vitest'
import { synthPlan, createFx, MUTE_KEY, type FxSound } from '../src/fx/audio'
import { vibratePlan, createHaptics } from '../src/fx/haptics'

const ALL: FxSound[] = ['tap', 'fire', 'miss', 'body', 'head', 'win', 'lose', 'tick', 'coin']

describe('synthPlan 合成计划', () => {
  it('每个声音都有至少一步，参数在合法区间', () => {
    for (const s of ALL) {
      const steps = synthPlan(s)
      expect(steps.length, s).toBeGreaterThan(0)
      for (const st of steps) {
        expect(st.dur, s).toBeGreaterThan(0)
        expect(st.dur, s).toBeLessThanOrEqual(1)
        expect(st.peak, s).toBeGreaterThan(0)
        expect(st.peak, s).toBeLessThanOrEqual(1)
        expect(st.at, s).toBeGreaterThanOrEqual(0)
        expect(st.f0, s).toBeGreaterThan(0)
        expect(st.f1, s).toBeGreaterThan(0)
      }
    }
  })

  it('胜利是上行三连、失败是下行三连（听感方向由频率序列决定）', () => {
    const win = synthPlan('win').map((s) => s.f0)
    const lose = synthPlan('lose').map((s) => s.f0)
    expect(win[0]!).toBeLessThan(win[1]!)
    expect(win[1]!).toBeLessThan(win[2]!)
    expect(lose[0]!).toBeGreaterThan(lose[1]!)
    expect(lose[1]!).toBeGreaterThan(lose[2]!)
  })
})

describe('createFx', () => {
  function fakeStorage() {
    const m = new Map<string, string>()
    return { getItem: (k: string) => m.get(k) ?? null, setItem: (k: string, v: string) => void m.set(k, v), m }
  }

  function fakeCtx() {
    const started: { type: string; f0: number; f1: number }[] = []
    const ctx = {
      currentTime: 0,
      state: 'running',
      destination: {},
      createOscillator: () => {
        const rec = { type: 'sine', f0: 0, f1: 0 }
        started.push(rec)
        return {
          set type(v: string) {
            rec.type = v
          },
          frequency: {
            setValueAtTime: (v: number) => (rec.f0 = v),
            exponentialRampToValueAtTime: (v: number) => (rec.f1 = v),
          },
          connect: () => {},
          start: () => {},
          stop: () => {},
        }
      },
      createGain: () => ({
        gain: { setValueAtTime: () => {}, linearRampToValueAtTime: () => {} },
        connect: () => {},
      }),
    }
    return { ctx, started }
  }

  it('静音状态读写 localStorage（plane-duel:muted）', () => {
    const st = fakeStorage()
    const fx = createFx({ ctx: () => null, storage: st })
    expect(fx.muted).toBe(false)
    fx.setMuted(true)
    expect(st.m.get(MUTE_KEY)).toBe('1')
    const fx2 = createFx({ ctx: () => null, storage: st })
    expect(fx2.muted).toBe(true)
  })

  it('播放：未静音建振荡器，静音后一个都不建', () => {
    const { ctx, started } = fakeCtx()
    const st = fakeStorage()
    const fx = createFx({ ctx: () => ctx, storage: st })
    fx.play('head')
    expect(started.length).toBe(synthPlan('head').length)
    fx.setMuted(true)
    started.length = 0
    fx.play('head')
    expect(started.length).toBe(0)
  })

  it('AudioContext 创建失败/播放抛异常都不冒出来', () => {
    const fx = createFx({ ctx: () => null })
    expect(() => fx.play('fire')).not.toThrow()
    const boom = createFx({
      ctx: () => {
        throw new Error('no audio')
      },
    })
    expect(() => boom.play('win')).not.toThrow()
  })
})

describe('haptics', () => {
  it('击落比未中震得久；每个事件都有模式', () => {
    const sum = (e: Parameters<typeof vibratePlan>[0]) => vibratePlan(e).reduce((a, b) => a + b, 0)
    expect(sum('head')).toBeGreaterThan(sum('miss'))
    expect(vibratePlan('ui').length).toBeGreaterThan(0)
  })

  it('目标不存在或 vibrate 抛异常时静默降级', () => {
    const h = createHaptics(null)
    expect(() => h.vibrate('head')).not.toThrow()
    const boom = createHaptics({
      vibrate: () => {
        throw new Error('denied')
      },
    })
    expect(() => boom.vibrate('body')).not.toThrow()
  })

  it('转发到注入目标的 vibrate，参数即计划', () => {
    const got: number[][] = []
    const h = createHaptics({ vibrate: (p) => (got.push(p), true) })
    h.vibrate('body')
    expect(got).toEqual([vibratePlan('body')])
  })
})
