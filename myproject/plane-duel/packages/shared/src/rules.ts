/**
 * 纯函数游戏规则。无 IO、无时间、无随机 —— 因此可被确定性测试。
 * 所有涉及棋盘尺寸的函数都必须接受 boardSize 参数，不得读常量（spec §四、§十五）。
 */

import type { Cell, Plane } from './types'

/** 稳定的格坐标键，用于 Set/Map 索引。 */
export function cellKey(cell: Cell): string {
  return `${cell.row},${cell.col}`
}

/**
 * 一架飞机的 9 格：以机头为中心的 3×3。
 * 不检查越界——越界由 isPlacementValid / checkPlacement 负责。
 */
export function cellsOfPlane(head: Cell): Cell[] {
  const cells: Cell[] = []
  for (let row = head.row - 1; row <= head.row + 1; row++) {
    for (let col = head.col - 1; col <= head.col + 1; col++) {
      cells.push({ row, col })
    }
  }
  return cells
}

/**
 * 机头是否能让整架飞机落在棋盘内。
 * 合法范围是 1..boardSize-2（机身要向四周各扩一格）。
 */
export function isPlacementValid(head: Cell, boardSize: number): boolean {
  if (!Number.isInteger(head.row) || !Number.isInteger(head.col)) return false
  return (
    head.row >= 1 &&
    head.row <= boardSize - 2 &&
    head.col >= 1 &&
    head.col <= boardSize - 2
  )
}

export type PlacementCheck =
  | { ok: true }
  | { ok: false; reason: 'count' | 'outOfBounds' | 'overlap' }

/**
 * 校验一组机头。检查顺序即优先级：count → outOfBounds → overlap。
 * P0 只有 1 架飞机，但这里从一开始就按 planeCount 实现，
 * 使 P1 的多机摆放无需改动本函数（spec §三）。
 */
export function checkPlacement(
  heads: readonly Cell[],
  boardSize: number,
  planeCount: number,
): PlacementCheck {
  if (heads.length !== planeCount) return { ok: false, reason: 'count' }

  for (const head of heads) {
    if (!isPlacementValid(head, boardSize)) return { ok: false, reason: 'outOfBounds' }
  }

  const seen = new Set<string>()
  for (const head of heads) {
    for (const cell of cellsOfPlane(head)) {
      const k = cellKey(cell)
      if (seen.has(k)) return { ok: false, reason: 'overlap' }
      seen.add(k)
    }
  }

  return { ok: true }
}

export type ShotResolution =
  | { result: 'miss' }
  | { result: 'body'; planeId: string }
  | { result: 'head'; planeId: string }

/**
 * 一炮打在 planes 上的结果。
 *
 * 必须先判机头再判机身：机头本身也包含在 cellsOfPlane 的 9 格里，
 * 顺序反了会把机头误判成 body。
 */
export function resolveShot(planes: readonly Plane[], cell: Cell): ShotResolution {
  const target = cellKey(cell)

  for (const plane of planes) {
    if (cellKey(plane.head) === target) return { result: 'head', planeId: plane.id }
  }

  for (const plane of planes) {
    for (const c of cellsOfPlane(plane.head)) {
      if (cellKey(c) === target) return { result: 'body', planeId: plane.id }
    }
  }

  return { result: 'miss' }
}

/**
 * 由已命中的机身格推导可能的机头位置。
 *
 * H(c) = { h | isPlacementValid(h) && c ∈ cellsOfPlane(h) && h ≠ c }
 * 即 c 的 8 邻域内的合法位置——注意是 8 邻域，**不含 c 自身**：
 * c 是机身格，机头不可能就是 c。这一条来自 spec §二「机头必然在该格的 8 邻域内」。
 *
 * 多个命中取交集；无命中时返回全部合法位置。
 *
 * 这是"命中机身 → 缩小机头范围"这一核心推理的实现（spec §二）。
 */
export function candidateHeads(bodyHits: readonly Cell[], boardSize: number): Cell[] {
  const allValid = (): Cell[] => {
    const out: Cell[] = []
    for (let row = 1; row <= boardSize - 2; row++) {
      for (let col = 1; col <= boardSize - 2; col++) {
        out.push({ row, col })
      }
    }
    return out
  }

  if (bodyHits.length === 0) return allValid()

  let candidates = allValid()
  for (const hit of bodyHits) {
    const hitKey = cellKey(hit)
    candidates = candidates.filter(
      (h) => cellKey(h) !== hitKey && cellsOfPlane(h).some((c) => cellKey(c) === hitKey),
    )
    if (candidates.length === 0) break
  }
  return candidates
}

/** 所有飞机都被击落 ⇒ 该方输。空列表视为已结束（防御性）。 */
export function isAllPlanesDestroyed(
  planes: readonly Plane[],
  destroyedPlaneIds: readonly string[],
): boolean {
  return planes.every((p) => destroyedPlaneIds.includes(p.id))
}

/** 这一格是否已经打过。 */
export function isRepeatShot(shotKeys: ReadonlySet<string>, cell: Cell): boolean {
  return shotKeys.has(cellKey(cell))
}

/** 棋盘上所有未打过的格子。用于超时代打。 */
export function unshotCells(boardSize: number, shotKeys: ReadonlySet<string>): Cell[] {
  const out: Cell[] = []
  for (let row = 0; row < boardSize; row++) {
    for (let col = 0; col < boardSize; col++) {
      if (!shotKeys.has(cellKey({ row, col }))) out.push({ row, col })
    }
  }
  return out
}
