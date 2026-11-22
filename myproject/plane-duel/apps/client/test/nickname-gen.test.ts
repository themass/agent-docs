import { describe, it, expect } from 'vitest'
import { sanitizeNickname, isNicknameAllowed } from '@plane-duel/shared'
import { generateNickname } from '../src/nickname-gen'

describe('generateNickname', () => {
  it('长度 1–12 且通过 sanitizeNickname（遍历随机数边界与随机采样）', () => {
    const rngs = [() => 0, () => 0.999999, () => 0.5, Math.random]
    for (const rng of rngs) {
      for (let i = 0; i < 200; i++) {
        const n = generateNickname(rng)
        const len = [...n].length
        expect(len).toBeGreaterThanOrEqual(1)
        expect(len).toBeLessThanOrEqual(12)
        expect(sanitizeNickname(n, '__fallback__')).toBe(n)
      }
    }
  })

  it('形如 “形容词的名词”', () => {
    expect(generateNickname(() => 0)).toMatch(/^.+的.+$/u)
  })

  it('不同随机数给出不同昵称', () => {
    expect(generateNickname(() => 0)).not.toBe(generateNickname(() => 0.999999))
  })

  it('生成的昵称全部通过屏蔽词检查', () => {
    for (let i = 0; i < 1000; i++) {
      const n = generateNickname(() => Math.random())
      expect(isNicknameAllowed(n)).toBe(true)
    }
    // 遍历全部组合
    for (let a = 0; a < 16; a++) {
      for (let b = 0; b < 16; b++) {
        const seq = [(a + 0.5) / 16, (b + 0.5) / 16]
        let k = 0
        expect(isNicknameAllowed(generateNickname(() => seq[k++]!))).toBe(true)
      }
    }
  })
})
