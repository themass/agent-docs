// 电脑的决策（spec §20.3）。纯函数：只读传入的 GameView（engine.view(botId)），不碰任何其它状态。

import {
  candidateHeads,
  cellKey,
  cellsOfPlane,
  isPlacementValid,
  type BotDifficulty,
  type Cell,
  type GameView,
  type RuleSet,
  type TargetShot,
} from '@plane-duel/shared'

export const BOT_MISTAKE_RATE: Readonly<Record<BotDifficulty, number>> = {
  beginner: 0.4,
  standard: 0.25,
  advanced: 0.1,
  expert: 0,
}

/** 「这一格能命中某架飞机」相对「这一格是机头」的权重。 */
export const PART_WEIGHT = 0.3

const TIE_EPS = 1e-9

export type OpponentModel = {
  /** 可行机头 F_t */
  feasible: Cell[]
  /** 有机身命中但未击落的飞机，及其候选机头 */
  active: { planeId: string; candidates: Cell[] }[]
  /** 未定位的飞机数 */
  unlocated: number
}

/**
 * 只用电脑打在某一对手身上的炮推理该对手的飞机位置。
 * 分组只看 body / head 的 planeId；miss 的 planeId 恒为 'p0'，不能用来分组。
 */
export function opponentModel(
  shotsOnTarget: readonly TargetShot[],
  planesDestroyed: number,
  rules: RuleSet,
): OpponentModel {
  const shot = new Set<string>()
  const missed = new Set<string>()
  const destroyedIds = new Set<string>()
  const bodyByPlane = new Map<string, Cell[]>()

  for (const s of shotsOnTarget) {
    const k = cellKey(s)
    shot.add(k)
    if (s.result === 'miss') {
      missed.add(k)
    } else if (s.result === 'head') {
      destroyedIds.add(s.planeId)
      for (const c of cellsOfPlane(s)) missed.add(cellKey(c)) // 被击落飞机的 9 格：已知格
    } else {
      const list = bodyByPlane.get(s.planeId)
      if (list) list.push({ row: s.row, col: s.col })
      else bodyByPlane.set(s.planeId, [{ row: s.row, col: s.col }])
    }
  }
  // known：未命中格 + 已击落飞机的 9 格。已击落飞机的机身命中不再作活跃线索。
  const known = missed
  for (const id of destroyedIds) bodyByPlane.delete(id)

  const feasible: Cell[] = []
  const feasibleKeys = new Set<string>()
  const n = rules.boardSize
  for (let row = 1; row <= n - 2; row++) {
    for (let col = 1; col <= n - 2; col++) {
      const h = { row, col }
      if (!isPlacementValid(h, n)) continue
      if (shot.has(cellKey(h))) continue
      if (cellsOfPlane(h).some((c) => known.has(cellKey(c)))) continue
      feasible.push(h)
      feasibleKeys.add(cellKey(h))
    }
  }

  const active: { planeId: string; candidates: Cell[] }[] = []
  let activeCount = 0
  for (const [planeId, hits] of bodyByPlane) {
    activeCount++
    const others = new Set<string>()
    for (const [id, list] of bodyByPlane) {
      if (id !== planeId) for (const c of list) others.add(cellKey(c))
    }
    const candidates = candidateHeads(hits, n).filter(
      (h) => feasibleKeys.has(cellKey(h)) && !cellsOfPlane(h).some((c) => others.has(cellKey(c))),
    )
    if (candidates.length > 0) active.push({ planeId, candidates })
    // 候选为空（理论上不会发生）→ 按未定位处理，由下面的 unlocated 计入
  }

  const unlocated = Math.max(0, rules.planeCount - planesDestroyed - activeCount) + (activeCount - active.length)
  return { feasible, active, unlocated }
}

/** 对每个未打过的格子打分（键为 cellKey）。 */
export function scoreCells(view: GameView, rules: RuleSet): Map<string, number> {
  const n = rules.boardSize
  const shotAny = new Set<string>()
  for (const s of view.you.shots) shotAny.add(cellKey(s))

  const scores = new Map<string, number>()
  for (let row = 0; row < n; row++) {
    for (let col = 0; col < n; col++) {
      const k = cellKey({ row, col })
      if (!shotAny.has(k)) scores.set(k, 0)
    }
  }

  const add = (c: Cell, v: number) => {
    const k = cellKey(c)
    const cur = scores.get(k)
    if (cur !== undefined) scores.set(k, cur + v)
  }
  const spread = (heads: readonly Cell[], weight: number) => {
    const w = weight / heads.length
    for (const h of heads) {
      add(h, w)
      for (const c of cellsOfPlane(h)) add(c, PART_WEIGHT * w)
    }
  }

  for (const o of view.others) {
    if (!o.alive) continue
    const model = opponentModel(
      view.you.shots.filter((s) => s.targetId === o.playerId),
      o.planesDestroyed,
      rules,
    )
    if (model.feasible.length === 0) continue
    for (const a of model.active) spread(a.candidates, 1)
    if (model.unlocated > 0) spread(model.feasible, model.unlocated)
  }
  return scores
}

/**
 * 选一格开炮；没有可打的格子时返回 null。
 * rng 的使用顺序固定：先抽一次判定是否失误；失误则再抽一次从所有未打格子里均匀选；
 * 否则取最高分，同分再抽一次均匀选。
 */
export function chooseShot(
  view: GameView,
  rules: RuleSet,
  difficulty: BotDifficulty,
  rng: () => number,
): Cell | null {
  const mistake = rng() < BOT_MISTAKE_RATE[difficulty]
  const scores = scoreCells(view, rules)
  if (scores.size === 0) return null

  const pickFrom = (keys: string[]): Cell => {
    const k = keys[Math.min(keys.length - 1, Math.floor(rng() * keys.length))] as string
    const [row, col] = k.split(',').map(Number) as [number, number]
    return { row, col }
  }

  const all = [...scores.keys()] // 行优先
  if (mistake) return pickFrom(all)

  let best = -Infinity
  for (const v of scores.values()) if (v > best) best = v
  const top = all.filter((k) => (scores.get(k) as number) >= best - TIE_EPS)
  return pickFrom(top)
}
