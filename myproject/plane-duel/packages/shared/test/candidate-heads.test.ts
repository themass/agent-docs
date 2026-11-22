import { describe, it, expect } from 'vitest'
import { candidateHeads } from '../src/index'

describe('candidateHeads', () => {
  it('没有机身命中时返回全部合法机头位置', () => {
    // 10x10 的合法机头是 1..8 × 1..8 = 64 个
    expect(candidateHeads([], 10)).toHaveLength(64)
  })

  it('单次机身命中把候选收缩到该格的 8 邻域内', () => {
    const c = candidateHeads([{ row: 5, col: 5 }], 10)
    expect(c).toHaveLength(8)
    expect(c).toContainEqual({ row: 4, col: 4 })
    expect(c).not.toContainEqual({ row: 5, col: 5 }) // 机头本身不可能
    expect(c).not.toContainEqual({ row: 3, col: 5 })
  })

  it('靠近边缘时按棋盘裁剪', () => {
    // (1,1) 的左上邻域只有 3 个合法机头
    const c = candidateHeads([{ row: 1, col: 1 }], 10)
    expect(c).toHaveLength(3)
    expect(c).toContainEqual({ row: 2, col: 2 })
    expect(c).toContainEqual({ row: 1, col: 2 })
    expect(c).toContainEqual({ row: 2, col: 1 })
  })

  it('两次机身命中取交集', () => {
    // 两个命中格共享的合法机头只可能是能同时覆盖它们的那一架
    const c = candidateHeads([{ row: 4, col: 5 }, { row: 5, col: 6 }], 10)
    expect(c).toContainEqual({ row: 5, col: 5 })
    expect(c.length).toBeLessThan(8)
  })

  it('互相矛盾的命中返回空集', () => {
    expect(candidateHeads([{ row: 1, col: 1 }, { row: 8, col: 8 }], 10)).toHaveLength(0)
  })
})
