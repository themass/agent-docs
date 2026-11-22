import { describe, it, expect } from 'vitest'
import { isAllPlanesDestroyed, isRepeatShot } from '../src/index'
import type { Plane } from '../src/index'

const planes: Plane[] = [
  { id: 'p0', head: { row: 2, col: 2 } },
  { id: 'p1', head: { row: 7, col: 7 } },
]

describe('isAllPlanesDestroyed', () => {
  it('单机被击落即结束', () => {
    expect(isAllPlanesDestroyed([planes[0]!], ['p0'])).toBe(true)
  })

  it('多机只击落一架不结束', () => {
    expect(isAllPlanesDestroyed(planes, ['p0'])).toBe(false)
  })

  it('全部击落才结束', () => {
    expect(isAllPlanesDestroyed(planes, ['p0', 'p1'])).toBe(true)
  })

  it('无飞机视为已结束（防御）', () => {
    expect(isAllPlanesDestroyed([], [])).toBe(true)
  })
})

describe('isRepeatShot', () => {
  it('打过的格子返回 true', () => {
    expect(isRepeatShot(new Set(['3,4']), { row: 3, col: 4 })).toBe(true)
  })

  it('没打过的格子返回 false', () => {
    expect(isRepeatShot(new Set(['3,4']), { row: 4, col: 3 })).toBe(false)
  })
})
