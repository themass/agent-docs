/**
 * 棋盘渲染模型。渲染逻辑里唯一有判断的部分是"这一格该显示什么"，
 * 抽成纯函数就能单测，而 .vue 只负责画（Task 15）。
 */

import { candidateHeads, cellKey, cellsOfPlane, type Cell, type ShotResult, type TargetShot } from '@plane-duel/shared'

export type BoardCellState = 'unknown' | 'miss' | 'body' | 'head'

export type BoardCell = { row: number; col: number; state: BoardCellState }

export type BuildBoardOptions = {
  boardSize: number
  shots: readonly { row: number; col: number; result: ShotResult }[]
  planes: readonly Cell[]
  /** 为真时显示自己的飞机（自己的棋盘）；为假时只显示开炮结果（对手棋盘） */
  showPlane: boolean
}

/**
 * 生成按行优先排列的 boardSize² 个格子。
 *
 * 优先级：机头 > 机身 > 开炮结果。机头必须最后覆盖，
 * 否则「自己机头所在格也有命中记录」时会被画成普通命中。
 */
export function buildBoardCells(opts: BuildBoardOptions): BoardCell[] {
  const { boardSize, shots, planes, showPlane } = opts

  const cells: BoardCell[] = []
  for (let row = 0; row < boardSize; row++) {
    for (let col = 0; col < boardSize; col++) {
      cells.push({ row, col, state: 'unknown' })
    }
  }

  const at = (row: number, col: number): BoardCell | undefined =>
    row >= 0 && row < boardSize && col >= 0 && col < boardSize
      ? cells[row * boardSize + col]
      : undefined

  for (const s of shots) {
    const cell = at(s.row, s.col)
    if (cell !== undefined) cell.state = s.result
  }

  if (showPlane) {
    for (const head of planes) {
      for (const c of cellsOfPlane(head)) {
        const cell = at(c.row, c.col)
        if (cell !== undefined) cell.state = 'body'
      }
    }
    for (const head of planes) {
      const cell = at(head.row, head.col)
      if (cell !== undefined) cell.state = 'head'
    }
  }

  return cells
}

/** 供 UI 判断一个格子是否已被打过（不能重复开炮）。 */
export function firedKeys(shots: readonly { row: number; col: number }[]): Set<string> {
  return new Set(shots.map((s) => cellKey({ row: s.row, col: s.col })))
}

// ---------- 混战 / 多对手合并棋盘 ----------

export type SeatColor = string
export type TargetMark = { playerId: string; color: SeatColor; result: ShotResult; dim: boolean }
export type TargetCell = { row: number; col: number; fired: boolean; marks: TargetMark[]; hint: boolean }

/** 座位号 → 颜色，四色在深色海图底上可明显区分：琥珀、青绿、紫、玫红。 */
export const SEAT_COLORS: readonly SeatColor[] = ['#f0a030', '#3ec7b6', '#a78bfa', '#f472b6']

/**
 * 我的所有炮打在"对手棋盘"上的显示模型，行优先 boardSize² 格。
 *
 * - focus 为 null：合并视图，一格的 marks 按 opponents 数组顺序列出各对手的结果。
 * - focus 为某对手：只含该对手的标记。
 * - fired：我对任一对手打过该格（炮是同时打向所有人的格子，服务端按格去重）。
 * - hint：仅 focus 模式且 hintFor === focus 时，叠加该对手的机头候选格。
 */
export function buildTargetCells(opts: {
  boardSize: number
  shots: readonly TargetShot[]
  opponents: readonly { playerId: string; color: SeatColor; alive: boolean }[]
  focus: string | null
  hintFor: string | null
}): TargetCell[] {
  const { boardSize, shots, opponents, focus, hintFor } = opts

  const cells: TargetCell[] = []
  for (let row = 0; row < boardSize; row++) {
    for (let col = 0; col < boardSize; col++) {
      cells.push({ row, col, fired: false, marks: [], hint: false })
    }
  }
  const at = (row: number, col: number): TargetCell | undefined =>
    row >= 0 && row < boardSize && col >= 0 && col < boardSize ? cells[row * boardSize + col] : undefined

  const order = new Map(opponents.map((o, i) => [o.playerId, i]))
  const ordered = shots
    .filter((s) => order.has(s.targetId))
    .sort((a, b) => order.get(a.targetId)! - order.get(b.targetId)!)

  for (const s of shots) {
    const cell = at(s.row, s.col)
    if (cell) cell.fired = true
  }
  for (const s of ordered) {
    if (focus !== null && s.targetId !== focus) continue
    const opp = opponents[order.get(s.targetId)!]!
    at(s.row, s.col)?.marks.push({ playerId: s.targetId, color: opp.color, result: s.result, dim: !opp.alive })
  }

  if (focus !== null && hintFor === focus) {
    for (const h of hintHeads(shots.filter((s) => s.targetId === focus), boardSize)) {
      const cell = at(h.row, h.col)
      if (cell) cell.hint = true
    }
  }

  return cells
}

/**
 * 机头候选：每架尚未击落的飞机按自己命中的机身格分别推理，再取并集。
 * 没有任何未击落的、已命中机身的飞机时，退化为全部合法机头位置。
 */
export function hintHeads(shots: readonly TargetShot[], boardSize: number): Cell[] {
  const downed = new Set(shots.filter((s) => s.result === 'head').map((s) => s.planeId))
  const bodyByPlane = new Map<string, Cell[]>()
  for (const s of shots) {
    if (s.result !== 'body' || downed.has(s.planeId)) continue
    const list = bodyByPlane.get(s.planeId) ?? []
    list.push({ row: s.row, col: s.col })
    bodyByPlane.set(s.planeId, list)
  }
  if (bodyByPlane.size === 0) return candidateHeads([], boardSize)
  const union = new Map<string, Cell>()
  for (const hits of bodyByPlane.values()) {
    for (const h of candidateHeads(hits, boardSize)) union.set(cellKey(h), h)
  }
  return [...union.values()]
}

/**
 * 对决棋盘的推理提示格（cellKey 集合）：复用 hintHeads 按飞机分别推理再取并集。
 * 没有未击落飞机的机身命中时不显示提示（返回 undefined）。
 */
export function duelHintKeys(shots: readonly TargetShot[], boardSize: number): Set<string> | undefined {
  const downed = new Set(shots.filter((s) => s.result === 'head').map((s) => s.planeId))
  if (!shots.some((s) => s.result === 'body' && !downed.has(s.planeId))) return undefined
  return new Set(hintHeads(shots, boardSize).map(cellKey))
}
