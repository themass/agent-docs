/**
 * P6 手感：音效计划（纯数据）+ WebAudio 合成引擎。
 * 无音频素材——全部用振荡器现场合成（复古街机感，和电竞配色一路）。
 * 浏览器策略：AudioContext 懒创建 + resume（首个用户手势后才允许出声），
 * 创建/播放失败一律静默降级，绝不影响对局。
 */

export type FxSound =
  | 'tap' // 通用 UI 点击
  | 'fire' // 开炮发出
  | 'miss' // 未中
  | 'body' // 命中机身
  | 'head' // 命中机头（击落）
  | 'win' // 胜利
  | 'lose' // 败北
  | 'tick' // 倒计时最后 3 秒
  | 'coin' // 金币到账

/** 一步振荡：从 f0 滑到 f1，持续 dur 秒，峰值音量 peak（0~1） */
export type SynthStep = { type: OscillatorType; f0: number; f1: number; at: number; dur: number; peak: number }

/** 纯函数：声音 → 振荡计划。node 可测，不碰浏览器 API */
export function synthPlan(sound: FxSound): SynthStep[] {
  switch (sound) {
    case 'tap':
      return [{ type: 'sine', f0: 660, f1: 520, at: 0, dur: 0.05, peak: 0.10 }]
    case 'fire':
      return [{ type: 'sawtooth', f0: 880, f1: 180, at: 0, dur: 0.12, peak: 0.16 }]
    case 'miss':
      return [{ type: 'sine', f0: 200, f1: 120, at: 0, dur: 0.09, peak: 0.14 }]
    case 'body':
      return [
        { type: 'square', f0: 520, f1: 520, at: 0, dur: 0.05, peak: 0.18 },
        { type: 'square', f0: 660, f1: 620, at: 0.06, dur: 0.07, peak: 0.2 },
      ]
    case 'head':
      return [
        { type: 'square', f0: 760, f1: 90, at: 0, dur: 0.28, peak: 0.26 },
        { type: 'sawtooth', f0: 120, f1: 40, at: 0, dur: 0.22, peak: 0.2 },
      ]
    case 'win':
      return [
        { type: 'sine', f0: 523, f1: 523, at: 0, dur: 0.1, peak: 0.2 },
        { type: 'sine', f0: 659, f1: 659, at: 0.1, dur: 0.1, peak: 0.2 },
        { type: 'sine', f0: 784, f1: 784, at: 0.2, dur: 0.16, peak: 0.22 },
      ]
    case 'lose':
      return [
        { type: 'sine', f0: 392, f1: 392, at: 0, dur: 0.12, peak: 0.18 },
        { type: 'sine', f0: 330, f1: 330, at: 0.12, dur: 0.12, peak: 0.18 },
        { type: 'sine', f0: 262, f1: 246, at: 0.24, dur: 0.22, peak: 0.18 },
      ]
    case 'tick':
      return [{ type: 'sine', f0: 990, f1: 990, at: 0, dur: 0.04, peak: 0.12 }]
    case 'coin':
      return [
        { type: 'sine', f0: 988, f1: 988, at: 0, dur: 0.06, peak: 0.16 },
        { type: 'sine', f0: 1319, f1: 1319, at: 0.07, dur: 0.12, peak: 0.16 },
      ]
  }
}

export const MUTE_KEY = 'plane-duel:muted'

type AudioCtxLike = {
  currentTime: number
  state: string
  resume?: () => unknown
  createOscillator: () => {
    type: string
    frequency: { setValueAtTime: (v: number, t: number) => void; exponentialRampToValueAtTime: (v: number, t: number) => void }
    connect: (dest: unknown) => void
    start: (t: number) => void
    stop: (t: number) => void
  }
  createGain: () => {
    gain: { setValueAtTime: (v: number, t: number) => void; linearRampToValueAtTime: (v: number, t: number) => void }
    connect: (dest: unknown) => void
  }
  destination: unknown
}

export type FxHandle = {
  play: (s: FxSound) => void
  setMuted: (m: boolean) => void
  readonly muted: boolean
}

export type FxDeps = {
  /** 注入点：测试传假 AudioContext；默认懒建浏览器 AudioContext */
  ctx?: () => AudioCtxLike | null
  storage?: { getItem: (k: string) => string | null; setItem: (k: string, v: string) => void } | null
  onMuteChange?: (m: boolean) => void
}

export function createFx(deps: FxDeps = {}): FxHandle {
  const storage =
    deps.storage !== undefined ? deps.storage : typeof localStorage !== 'undefined' ? localStorage : null
  let muted = storage?.getItem(MUTE_KEY) === '1'
  // undefined = 还没尝试创建；null = 创建失败，永久静默。
  // 注意：注入的 ctx 工厂也要懒调用——构造期抛异常同样不许冒出来
  let ctx: AudioCtxLike | null | undefined

  function ensureCtx(): AudioCtxLike | null {
    if (ctx !== undefined) return ctx
    let made: AudioCtxLike | null = null
    try {
      if (deps.ctx) {
        made = deps.ctx()
      } else {
        const Ctor =
          typeof AudioContext !== 'undefined'
            ? AudioContext
            : (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
        // AudioContext 的结构比 AudioCtxLike 更宽（connect 重载），断言为注入协议子集
        made = Ctor ? (new Ctor() as unknown as AudioCtxLike) : null
      }
    } catch {
      made = null
    }
    ctx = made
    return made
  }

  const handle: FxHandle = {
    play(sound) {
      if (muted) return
      const c = ensureCtx()
      if (c === null) return
      try {
        if (c.state === 'suspended') void c.resume?.()
        const t0 = c.currentTime
        for (const st of synthPlan(sound)) {
          const osc = c.createOscillator()
          const gain = c.createGain()
          osc.type = st.type
          osc.frequency.setValueAtTime(st.f0, t0 + st.at)
          osc.frequency.exponentialRampToValueAtTime(Math.max(1, st.f1), t0 + st.at + st.dur)
          // 快起快落的爆点包络
          gain.gain.setValueAtTime(0.0001, t0 + st.at)
          gain.gain.linearRampToValueAtTime(st.peak, t0 + st.at + 0.008)
          gain.gain.linearRampToValueAtTime(0.0001, t0 + st.at + st.dur)
          osc.connect(gain)
          gain.connect(c.destination)
          osc.start(t0 + st.at)
          osc.stop(t0 + st.at + st.dur + 0.02)
        }
      } catch {
        // 任何 WebAudio 异常都不允许冒到对局代码里
      }
    },
    setMuted(m) {
      muted = m
      storage?.setItem(MUTE_KEY, m ? '1' : '0')
      deps.onMuteChange?.(m)
    },
    get muted() {
      return muted
    },
  }
  return handle
}
