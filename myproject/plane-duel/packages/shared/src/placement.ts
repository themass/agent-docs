// 自动摆放。随机性只来自传入的 rng，保证同一随机源下结果确定。

import { cellKey, cellsOfPlane } from './rules'
import type { Cell } from './types'

const MAX_ATTEMPTS = 200

/** 返回 planeCount 个互不重叠、全在棋盘内的机头。 */
export function autoPlace(boardSize: number, planeCount: number, rng: () => number): Cell[] {
  const all: Cell[] = []
  for (let row = 1; row <= boardSize - 2; row++) {
    for (let col = 1; col <= boardSize - 2; col++) all.push({ row, col })
  }

  for (let attempt = 0; attempt < MAX_ATTEMPTS; attempt++) {
    const order = all.slice()
    for (let i = order.length - 1; i > 0; i--) {
      const j = Math.floor(rng() * (i + 1))
      const tmp = order[i] as Cell
      order[i] = order[j] as Cell
      order[j] = tmp
    }
    const used = new Set<string>()
    const heads: Cell[] = []
    for (const head of order) {
      const cells = cellsOfPlane(head)
      if (cells.some((c) => used.has(cellKey(c)))) continue
      for (const c of cells) used.add(cellKey(c))
      heads.push(head)
      if (heads.length === planeCount) return heads
    }
  }

  // 保底：机头取 (1+3i, 1+3j) 的整齐网格，行优先。
  const perAxis = Math.floor((boardSize - 3) / 3) + 1
  const heads: Cell[] = []
  for (let i = 0; i < perAxis && heads.length < planeCount; i++) {
    for (let j = 0; j < perAxis && heads.length < planeCount; j++) {
      heads.push({ row: 1 + 3 * i, col: 1 + 3 * j })
    }
  }
  return heads
}
