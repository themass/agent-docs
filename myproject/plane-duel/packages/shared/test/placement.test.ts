import { describe, it, expect } from 'vitest'
import { BOARD_MIN, BOARD_MAX, maxPlanes, checkPlacement, autoPlace } from '../src'
import { mulberry32 } from './helpers'

describe('autoPlace', () => {
  it('每个边长、每个合法飞机数都摆得下且合法（含上限）', () => {
    for (let n = BOARD_MIN; n <= BOARD_MAX; n++)
      for (let k = 1; k <= maxPlanes(n); k++) {
        const heads = autoPlace(n, k, mulberry32(n * 100 + k))
        expect(checkPlacement(heads, n, k)).toEqual({ ok: true })
      }
  })
  it('随机源恒返回 0.999 时（随机尝试最容易失败）仍有解', () => {
    expect(checkPlacement(autoPlace(16, 6, () => 0.999), 16, 6)).toEqual({ ok: true })
  })
  it('同一随机种子结果确定', () => expect(autoPlace(12, 2, mulberry32(7))).toEqual(autoPlace(12, 2, mulberry32(7))))
})
