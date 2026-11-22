/**
 * 对局引擎接口与两种引擎共用的摆放阶段。
 * 工厂：2 人 → DuelEngine，3–4 人 → MeleeEngine。
 */
import { autoPlace, checkPlacement, placeSeconds } from '@plane-duel/shared'
import { DuelEngine } from './duel-engine'
import { MeleeEngine } from './melee-engine'
import type {
  Cell,
  ClientMessage,
  GamePhase,
  GameResult,
  GameView,
  Mode,
  RuleSet,
  ServerMessage,
} from '@plane-duel/shared'

export type Outbound = { to: string; msg: ServerMessage }

export const DISCONNECT_GRACE_MS = 30_000

export type EngineOptions = {
  rules: RuleSet
  playerIds: string[]
  now: number
  rng?: () => number
}

export interface Engine {
  readonly mode: Mode
  readonly phase: GamePhase
  /** phase === 'finished' 时非空 */
  readonly result: GameResult | null
  /** 只处理 placePlane / fire / leaveRoom */
  handle(playerId: string, msg: ClientMessage, now: number): Outbound[]
  tick(now: number): Outbound[]
  setConnected(playerId: string, connected: boolean, now: number): Outbound[]
  view(playerId: string): GameView
}

/** 2 人 → DuelEngine，3–4 人 → MeleeEngine。 */
export function createEngine(opts: EngineOptions): Engine {
  const n = opts.playerIds.length
  if (n < 2 || n > 4) throw new Error(`createEngine: playerIds must have 2-4 players, got ${n}`)
  if (n === 2) return new DuelEngine(opts)
  return new MeleeEngine(opts)
}

/** 两种引擎共用的摆放阶段：同时摆放、可重摆、到时自动摆放。 */
export class PlacingPhase {
  private _deadlineAt: number
  private readonly planes = new Map<string, Cell[]>()

  constructor(
    private readonly rules: RuleSet,
    private readonly playerIds: string[],
    now: number,
    private readonly rng: () => number,
  ) {
    this._deadlineAt = now + placeSeconds(rules) * 1000
  }

  get deadlineAt(): number {
    return this._deadlineAt
  }

  /** 合法 → planeAccepted 给本人（可重摆，替换旧摆放）；非法 → INVALID_PLACEMENT。非成员 → []。 */
  place(playerId: string, heads: Cell[]): Outbound[] {
    if (!this.playerIds.includes(playerId)) return []
    const check = checkPlacement(heads, this.rules.boardSize, this.rules.planeCount)
    if (!check.ok) {
      return [{ to: playerId, msg: { type: 'error', code: 'INVALID_PLACEMENT', message: check.reason } }]
    }
    const planes = heads.map((c) => ({ row: c.row, col: c.col }))
    this.planes.set(playerId, planes)
    return [{ to: playerId, msg: { type: 'planeAccepted', planes } }]
  }

  /** 给未摆放者 autoPlace，各发 planeAccepted。 */
  autoPlaceMissing(): Outbound[] {
    const out: Outbound[] = []
    for (const id of this.playerIds) {
      if (this.planes.has(id)) continue
      const planes = autoPlace(this.rules.boardSize, this.rules.planeCount, this.rng)
      this.planes.set(id, planes)
      out.push({ to: id, msg: { type: 'planeAccepted', planes } })
    }
    return out
  }

  get allPlaced(): boolean {
    return this.playerIds.every((id) => this.planes.has(id))
  }

  planesOf(playerId: string): Cell[] | null {
    return this.planes.get(playerId) ?? null
  }

  /** duel 暂停顺延用。 */
  extend(ms: number): void {
    this._deadlineAt += ms
  }
}
