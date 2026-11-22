import { describe, it, expect } from 'vitest'
import { cellsOfPlane, isPlacementValid, checkPlacement, cellKey } from '../src/index'

describe('cellsOfPlane', () => {
  it('返回机头为中心的 9 格', () => {
    const cells = cellsOfPlane({ row: 5, col: 5 })
    expect(cells).toHaveLength(9)
    expect(cells).toContainEqual({ row: 4, col: 4 })
    expect(cells).toContainEqual({ row: 6, col: 6 })
    expect(cells).toContainEqual({ row: 5, col: 5 })
  })

  it('机头本身包含在 9 格内', () => {
    expect(cellsOfPlane({ row: 3, col: 7 })).toContainEqual({ row: 3, col: 7 })
  })
})

describe('isPlacementValid', () => {
  it('棋盘中央合法', () => {
    expect(isPlacementValid({ row: 5, col: 5 }, 10)).toBe(true)
  })

  it('机头在 0 或 9 越界（机身会出棋盘）', () => {
    expect(isPlacementValid({ row: 0, col: 5 }, 10)).toBe(false)
    expect(isPlacementValid({ row: 9, col: 5 }, 10)).toBe(false)
    expect(isPlacementValid({ row: 5, col: 0 }, 10)).toBe(false)
    expect(isPlacementValid({ row: 5, col: 9 }, 10)).toBe(false)
  })

  it('合法范围是 1..boardSize-2', () => {
    expect(isPlacementValid({ row: 1, col: 1 }, 10)).toBe(true)
    expect(isPlacementValid({ row: 8, col: 8 }, 10)).toBe(true)
  })

  it('小棋盘 6x6 的范围是 1..4', () => {
    expect(isPlacementValid({ row: 4, col: 4 }, 6)).toBe(true)
    expect(isPlacementValid({ row: 5, col: 5 }, 6)).toBe(false)
  })
})

describe('checkPlacement', () => {
  it('数量不匹配返回 count', () => {
    expect(checkPlacement([{ row: 5, col: 5 }], 10, 2)).toEqual({ ok: false, reason: 'count' })
  })

  it('多机重叠返回 overlap', () => {
    // 两个机头相邻，(5,5) 与 (5,6) 的 9 格必然相交
    expect(checkPlacement([{ row: 5, col: 5 }, { row: 5, col: 6 }], 10, 2)).toEqual({
      ok: false,
      reason: 'overlap',
    })
  })

  it('多机不重叠通过', () => {
    expect(checkPlacement([{ row: 2, col: 2 }, { row: 6, col: 6 }], 10, 2)).toEqual({ ok: true })
  })

  it('越界优先于重叠被报出', () => {
    expect(checkPlacement([{ row: 0, col: 0 }, { row: 5, col: 5 }], 10, 2)).toEqual({
      ok: false,
      reason: 'outOfBounds',
    })
  })
})

describe('cellKey', () => {
  it('稳定且区分相邻格', () => {
    expect(cellKey({ row: 3, col: 4 })).toBe('3,4')
    expect(cellKey({ row: 4, col: 3 })).not.toBe(cellKey({ row: 3, col: 4 }))
  })
})
