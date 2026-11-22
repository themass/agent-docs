/**
 * 摆放界面的纯逻辑（spec §19.4）。
 *
 * 一个手势做两件事：点已有飞机的任一格 = 移除它；点空处 = 放一架新的。
 * 这样手机上不需要"删除模式"——想重摆就点掉再点新的。
 */

import { cellKey, cellsOfPlane, isPlacementValid, type Cell, type Mode, type RuleSet } from '@plane-duel/shared'

export type ToggleResult = { heads: Cell[]; error: 'edge' | 'overlap' | 'full' | null }

export function togglePlane(heads: readonly Cell[], tap: Cell, rules: RuleSet): ToggleResult {
  // 先看这一格是否属于某架已有的飞机：点机身任何一格都算点这架
  const existing = heads.findIndex((head) => cellsOfPlane(head).some((c) => cellKey(c) === cellKey(tap)))
  if (existing >= 0) {
    return { heads: heads.filter((_, i) => i !== existing), error: null }
  }

  if (!isPlacementValid(tap, rules.boardSize)) {
    return { heads: [...heads], error: 'edge' }
  }

  const occupied = new Set<string>()
  for (const head of heads) for (const c of cellsOfPlane(head)) occupied.add(cellKey(c))
  if (cellsOfPlane(tap).some((c) => occupied.has(cellKey(c)))) {
    return { heads: [...heads], error: 'overlap' }
  }

  if (heads.length >= rules.planeCount) {
    return { heads: [...heads], error: 'full' }
  }

  return { heads: [...heads, { row: tap.row, col: tap.col }], error: null }
}

/**
 * 大棋盘与混战必须两步开炮：点格子只是选中，再按"开炮"才发。
 * 小棋盘的 2 人局保持 P0 的一点即开。
 */
export function needsTwoStep(rules: RuleSet, mode: Mode): boolean {
  return mode === 'melee' || rules.boardSize >= 12
}
