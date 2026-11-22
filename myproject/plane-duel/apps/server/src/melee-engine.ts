/**
 * 3–4 人混战引擎（spec §19.6）：同时制回合、一炮打所有存活对手、结果按人私有。
 *
 * 设计约束同 DuelEngine：不持有 socket、不调用 Date.now()、不直接调 Math.random()。
 * 本引擎从不发 state / tableState / roomClosed（属于 Table / Hub）。
 *
 * 信息可见性（Review Focus #1）：
 * - 公开：谁已提交（submitted，无坐标）、每人被击落几架、谁出局；
 * - 私有：自己的每一炮在每个对手棋盘上的结果、别人打在自己棋盘上的炮；
 * - 无人可见：别人打别人的结果。
 */

import {
  cellKey,
  resolveShot,
  type Cell,
  type ClientMessage,
  type ErrorCode,
  type GamePhase,
  type GameResult,
  type GameView,
  type IncomingShot,
  type RankEntry,
  type RuleSet,
  type ServerMessage,
  type TargetShot,
} from '@plane-duel/shared'
import { DISCONNECT_GRACE_MS, PlacingPhase, type Engine, type EngineOptions, type Outbound } from './engine'

type PlayerState = {
  playerId: string
  /** 被击落的飞机 id */
  destroyed: Set<string>
  /** 我打出去的炮（每炮对每个对手一条） */
  shots: TargetShot[]
  /** 我打过的格子 */
  shotKeys: Set<string>
  /** 打在我棋盘上的炮 */
  incoming: IncomingShot[]
  /** 命中别人机身 + 机头的格数（跨所有对手累加） */
  hits: number
  connected: boolean
  /** 掉线时刻；在线时为 null。满 DISCONNECT_GRACE_MS 出局 */
  disconnectedAt: number | null
  /** 连续在线未提交的轮数；掉线期间不累计，达 IDLE_LIMIT 出局 */
  idleStreak: number
  /** 本轮已提交的坐标；未提交为 null */
  pending: Cell | null
  /** 出局轮次；存活为 null */
  eliminatedRound: number | null
  /** 在回合中途（离开 / 掉线超时）出局：排名在同轮结算出局者之后（评审 I3） */
  midRound: boolean
}

/** 连续这么多轮在线未提交 → 判定挂机出局（spec §19.6） */
const IDLE_LIMIT = 3

const toPlaneRefs = (heads: readonly Cell[]) => heads.map((head, i) => ({ id: `p${i}`, head }))

/**
 * 排名（spec §19.6）：存活者最前，其余按出局轮次降序；同轮按累计命中降序；
 * 仍相同 → 并列，名次跳号（1,1,3）。同名次者保持输入顺序。
 * 同一轮内，回合中途出局（midRound）者排在本轮结算时出局者之后（评审 I3）。
 */
export function rankPlayers(
  players: { playerId: string; eliminatedRound: number | null; hits: number; midRound?: boolean }[],
): RankEntry[] {
  const roundKey = (p: (typeof players)[number]) =>
    p.eliminatedRound === null ? Infinity : p.eliminatedRound - (p.midRound ? 0.5 : 0)
  const cmp = (x: (typeof players)[number], y: (typeof players)[number]) =>
    roundKey(y) - roundKey(x) || y.hits - x.hits
  const sorted = players
    .map((p, i) => ({ p, i }))
    .sort((x, y) => cmp(x.p, y.p) || x.i - y.i)
    .map(({ p }) => p)
  const out: RankEntry[] = []
  sorted.forEach((p, i) => {
    const prev = sorted[i - 1]
    const rank = prev !== undefined && cmp(prev, p) === 0 ? out[i - 1]!.rank : i + 1
    out.push({ playerId: p.playerId, rank, eliminatedRound: p.eliminatedRound, hits: p.hits })
  })
  return out
}

export class MeleeEngine implements Engine {
  readonly mode = 'melee' as const

  private readonly rules: RuleSet
  private readonly playerIds: string[]
  private readonly players: Map<string, PlayerState>
  private readonly placing: PlacingPhase
  private _phase: GamePhase = 'placing'
  private _result: GameResult | null = null
  /** 当前轮次；摆放阶段为 0 */
  private round = 0
  private roundDeadlineAt: number | null = null
  /** 回合中途出局（离开 / 掉线超时）的玩家，在下一条 roundResult.eliminated 里公开 */
  private midRoundEliminated: string[] = []

  constructor(opts: EngineOptions) {
    const n = opts.playerIds.length
    if (n < 3 || n > 4) throw new Error(`MeleeEngine needs 3-4 players, got ${n}`)
    this.rules = opts.rules
    this.playerIds = [...opts.playerIds]
    this.players = new Map()
    for (const id of this.playerIds) {
      this.players.set(id, {
        playerId: id,
        destroyed: new Set(),
        shots: [],
        shotKeys: new Set(),
        incoming: [],
        hits: 0,
        connected: true,
        disconnectedAt: null,
        idleStreak: 0,
        pending: null,
        eliminatedRound: null,
        midRound: false,
      })
    }
    this.placing = new PlacingPhase(this.rules, this.playerIds, opts.now, opts.rng ?? Math.random)
  }

  get phase(): GamePhase {
    return this._phase
  }

  get result(): GameResult | null {
    return this._result
  }

  private get deadlineAt(): number | null {
    if (this._phase === 'placing') return this.placing.deadlineAt
    if (this._phase === 'playing') return this.roundDeadlineAt
    return null
  }

  private error(to: string, code: ErrorCode, message?: string): Outbound {
    return { to, msg: { type: 'error', code, message: message ?? code } }
  }

  private broadcast(msg: ServerMessage): Outbound[] {
    return this.playerIds.map((to) => ({ to, msg }))
  }

  private get alivePlayers(): PlayerState[] {
    return [...this.players.values()].filter((p) => p.eliminatedRound === null)
  }

  private others(playerId: string, msg: ServerMessage): Outbound[] {
    return this.playerIds.filter((to) => to !== playerId).map((to) => ({ to, msg }))
  }

  // ---------------------------------------------------------------- handle

  handle(playerId: string, msg: ClientMessage, now: number): Outbound[] {
    const player = this.players.get(playerId)
    if (player === undefined || this._phase === 'finished') return []

    if (msg.type === 'leaveRoom') return player.eliminatedRound === null ? this.eliminateNow(player, now) : []
    if (player.eliminatedRound !== null) return [this.error(playerId, 'WRONG_PHASE', '你已出局')]

    if (this._phase === 'placing') {
      if (msg.type !== 'placePlane') return [this.error(playerId, 'WRONG_PHASE', '当前是摆放阶段')]
      const out = this.placing.place(playerId, msg.planes)
      if (this.allAlivePlaced) out.push(...this.startRound(now))
      return out
    }

    if (msg.type !== 'fire') return [this.error(playerId, 'WRONG_PHASE', '当前不能执行该操作')]
    return this.submit(player, msg.row, msg.col, now)
  }

  private submit(player: PlayerState, row: number, col: number, now: number): Outbound[] {
    const id = player.playerId
    if (player.pending !== null) return [this.error(id, 'NOT_YOUR_TURN', '本轮你已开过炮')]
    const size = this.rules.boardSize
    if (!Number.isInteger(row) || !Number.isInteger(col) || row < 0 || row >= size || col < 0 || col >= size) {
      return [this.error(id, 'OUT_OF_RANGE')]
    }
    const cell = { row, col }
    if (player.shotKeys.has(cellKey(cell))) return [this.error(id, 'REPEAT_SHOT')]

    player.pending = cell
    const out = this.broadcast({ type: 'submitted', playerId: id, round: this.round })
    out.push(...this.resolveIfAllSubmitted(now))
    return out
  }

  private get allAlivePlaced(): boolean {
    return this.alivePlayers.every((p) => this.placing.planesOf(p.playerId) !== null)
  }

  /** 所有在线存活者都已提交 → 不等到时、不等掉线者，立即结算。无人在线时只能等到时。 */
  private resolveIfAllSubmitted(now: number): Outbound[] {
    if (this._phase !== 'playing') return []
    const online = this.alivePlayers.filter((p) => p.connected)
    if (online.length === 0 || online.some((p) => p.pending === null)) return []
    return this.resolveRound(now)
  }

  /**
   * 离开 / 掉线超时：当场出局（记为当前轮次，排名在同轮结算出局者之后）。
   * 本轮已提交的那一炮保留，在本轮结算时作为射手结算（评审 I2）。
   * 只剩 ≤ 1 人 → gameOver；否则可能触发开局或结算。
   */
  private eliminateNow(player: PlayerState, now: number): Outbound[] {
    player.eliminatedRound = this.round
    player.midRound = true
    this.midRoundEliminated.push(player.playerId)
    // 当场公开（评审 M2）：谁出局本就是公开信息，不必等到本轮结算；结算里照旧列出
    const out = this.broadcast({ type: 'playerOut', playerId: player.playerId, round: this.round })
    if (this.alivePlayers.length <= 1) return [...out, ...this.finish()]
    if (this._phase === 'placing') return this.allAlivePlaced ? [...out, ...this.startRound(now)] : out
    return [...out, ...this.resolveIfAllSubmitted(now)]
  }

  // ---------------------------------------------------------------- 回合

  private startRound(now: number): Outbound[] {
    this._phase = 'playing'
    this.round++
    this.roundDeadlineAt = now + this.rules.turnSeconds * 1000
    for (const p of this.players.values()) {
      p.pending = null
      // 摆放阶段掉线的宽限从第 1 轮起算（评审 M3），否则摆放时长（≥45 秒）就先耗光 30 秒宽限
      if (this.round === 1 && p.disconnectedAt !== null && p.eliminatedRound === null) p.disconnectedAt = now
    }
    return this.broadcast({ type: 'phaseChanged', phase: 'playing', deadlineAt: this.roundDeadlineAt, round: this.round })
  }

  /** 结算本轮：每个已提交射手（含本轮中途出局者）的那一炮落在每个存活对手棋盘上。 */
  private resolveRound(now: number): Outbound[] {
    const targets = this.alivePlayers
    const leftShooters = this.midRoundEliminated.map((id) => this.players.get(id)!).filter((p) => p.pending !== null)
    const shooters = [...targets.filter((p) => p.pending !== null), ...leftShooters]
    const roundShots = new Map<string, TargetShot[]>()
    const roundIncoming = new Map<string, IncomingShot[]>()
    const before = new Map(targets.map((p) => [p.playerId, p.destroyed.size]))

    for (const s of shooters) {
      const cell = s.pending!
      s.shotKeys.add(cellKey(cell))
      for (const t of targets) {
        if (t === s) continue
        const r = resolveShot(toPlaneRefs(this.placing.planesOf(t.playerId) ?? []), cell)
        const planeId = r.result === 'miss' ? 'p0' : r.planeId
        const shot: TargetShot = { targetId: t.playerId, row: cell.row, col: cell.col, result: r.result, planeId }
        const inc: IncomingShot = { by: s.playerId, row: cell.row, col: cell.col, result: r.result, planeId }
        s.shots.push(shot)
        t.incoming.push(inc)
        push(roundShots, s.playerId, shot)
        push(roundIncoming, t.playerId, inc)
        if (r.result !== 'miss') s.hits++
        if (r.result === 'head') t.destroyed.add(planeId)
      }
    }

    // 挂机计数：提交清零；在线未提交 +1；掉线期间不变
    for (const p of targets) {
      if (p.pending !== null) p.idleStreak = 0
      else if (p.connected) p.idleStreak++
    }

    const eliminated: string[] = this.midRoundEliminated
    this.midRoundEliminated = []
    for (const p of targets) {
      if (p.destroyed.size >= this.rules.planeCount || p.idleStreak >= IDLE_LIMIT) {
        p.eliminatedRound = this.round
        eliminated.push(p.playerId)
      }
    }

    const destroyed = targets
      .filter((p) => p.destroyed.size !== before.get(p.playerId))
      .map((p) => ({ playerId: p.playerId, planesDestroyed: p.destroyed.size }))

    const out: Outbound[] = this.playerIds.map((to) => ({
      to,
      msg: {
        type: 'roundResult',
        round: this.round,
        shots: roundShots.get(to) ?? [],
        incoming: roundIncoming.get(to) ?? [],
        destroyed,
        eliminated,
      },
    }))
    out.push(...(this.alivePlayers.length <= 1 ? this.finish() : this.startRound(now)))
    return out
  }

  /** 存活 ≤ 1 人：结束并广播排名。 */
  private finish(): Outbound[] {
    this._phase = 'finished'
    this.roundDeadlineAt = null
    this.midRoundEliminated = []
    this._result = { reason: 'lastStanding', ranking: rankPlayers([...this.players.values()]) }
    return this.broadcast({ type: 'gameOver', result: this._result })
  }

  // ---------------------------------------------------------------- tick / 连接

  /** 推进计时：先判掉线超时出局，再处理摆放 / 回合到时。不暂停。 */
  tick(now: number): Outbound[] {
    const out: Outbound[] = []
    // 摆放阶段不因掉线出局（评审 M3）：掉线者到时照样被自动摆放，宽限从第 1 轮起算
    if (this._phase !== 'placing') {
      for (const p of this.alivePlayers) {
        if (this._phase === 'finished') break
        if (p.disconnectedAt !== null && now - p.disconnectedAt >= DISCONNECT_GRACE_MS) out.push(...this.eliminateNow(p, now))
      }
    }

    if (this._phase === 'placing' && now >= this.placing.deadlineAt) {
      // 摆放超时：为未摆放者随机落子（含掉线者），不判负
      out.push(...this.placing.autoPlaceMissing())
      out.push(...this.startRound(now))
    } else if (this._phase === 'playing' && this.roundDeadlineAt !== null && now >= this.roundDeadlineAt) {
      out.push(...this.resolveRound(now))
    }
    return out
  }

  /**
   * 掉线：通知其他人 presence，不暂停；若因此在线存活者已全部提交 → 立即结算。
   * 重连：通知 presence（快照由 Table 发送）；宽限已过但 tick 还没判 → 当场出局。
   */
  setConnected(playerId: string, connected: boolean, now: number): Outbound[] {
    const player = this.players.get(playerId)
    if (player === undefined || player.connected === connected) return []
    const droppedAt = player.disconnectedAt
    player.connected = connected
    player.disconnectedAt = connected ? null : now
    if (this._phase === 'finished') return []

    const out = this.others(playerId, { type: 'presence', playerId, connected })
    if (player.eliminatedRound !== null) return out
    if (!connected) {
      out.push(...this.resolveIfAllSubmitted(now))
    } else if (this._phase !== 'placing' && droppedAt !== null && now - droppedAt >= DISCONNECT_GRACE_MS) {
      // 摆放阶段不判出局（评审 M3）
      out.push(...this.eliminateNow(player, now))
    }
    return out
  }

  // ---------------------------------------------------------------- 视图

  view(playerId: string): GameView {
    const you = this.players.get(playerId)
    if (you === undefined) throw new Error(`player ${playerId} 不在本局`)
    return {
      mode: 'melee',
      phase: this._phase,
      deadlineAt: this.deadlineAt,
      turn: null,
      round: this.round > 0 ? this.round : null,
      you: {
        planes: this.placing.planesOf(playerId) ?? [],
        planesDestroyed: you.destroyed.size,
        alive: you.eliminatedRound === null,
        shots: [...you.shots],
        incoming: [...you.incoming],
        submitted: this._phase === 'playing' && you.pending !== null,
        pendingShot: you.pending,
      },
      others: this.playerIds
        .filter((id) => id !== playerId)
        .map((id) => {
          const p = this.players.get(id)!
          return {
            playerId: id,
            connected: p.connected,
            alive: p.eliminatedRound === null,
            planesDestroyed: p.destroyed.size,
            submitted: this._phase === 'playing' && p.pending !== null,
          }
        }),
    }
  }
}

function push<T>(map: Map<string, T[]>, key: string, v: T): void {
  const list = map.get(key)
  if (list === undefined) map.set(key, [v])
  else list.push(v)
}
