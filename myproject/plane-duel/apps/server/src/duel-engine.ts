/**
 * 2 人对决引擎（spec §二、§九、§十；从 P0 Room 抽出）。
 *
 * 设计约束：本类不持有 socket、不调用 Date.now()、不直接调 Math.random()。
 * 时间与随机源都从参数进来，因此「回合到点」「谁先手」这类行为可以确定性测试。
 * 座位、准备、再来一局、关房都属于 Table；引擎只管一局之内的事。
 */

import {
  cellKey,
  isAllPlanesDestroyed,
  isRepeatShot,
  resolveShot,
  unshotCells,
  type Cell,
  type ClientMessage,
  type ErrorCode,
  type GameOverReason,
  type GamePhase,
  type GameResult,
  type GameView,
  type IncomingShot,
  type RuleSet,
  type ServerMessage,
  type TargetShot,
} from '@plane-duel/shared'
import { DISCONNECT_GRACE_MS, PlacingPhase, type Engine, type EngineOptions, type Outbound } from './engine'

type PlayerState = {
  playerId: string
  /** 被击落的飞机 id */
  destroyed: Set<string>
  /** 我打出去的炮，key = cellKey */
  shots: Map<string, TargetShot>
  /** 打在我棋盘上的炮 */
  incoming: IncomingShot[]
  /** 命中对方机身 + 机头的格数 */
  hits: number
  connected: boolean
  /** 掉线时刻；在线时为 null。宽限按人独立计算（I1） */
  disconnectedAt: number | null
}

/** 把摆放的机头数组转成带 id 的 Plane，供 resolveShot 使用。 */
const toPlaneRefs = (heads: readonly Cell[]) => heads.map((head, i) => ({ id: `p${i}`, head }))

export class DuelEngine implements Engine {
  readonly mode = 'duel' as const

  private readonly rules: RuleSet
  private readonly playerIds: [string, string]
  private readonly rng: () => number
  private readonly players: Map<string, PlayerState>
  private readonly placing: PlacingPhase
  private _phase: GamePhase = 'placing'
  private _result: GameResult | null = null
  private turnIndex: number
  /** playing 阶段的回合 deadline；placing 阶段以 PlacingPhase 为准 */
  private turnDeadlineAt: number | null = null
  private pausedAt: number | null = null
  private resumePhase: 'placing' | 'playing' | null = null

  constructor(opts: EngineOptions) {
    if (opts.playerIds.length !== 2) throw new Error(`DuelEngine needs exactly 2 players, got ${opts.playerIds.length}`)
    this.rules = opts.rules
    this.playerIds = [opts.playerIds[0]!, opts.playerIds[1]!]
    this.rng = opts.rng ?? Math.random

    this.players = new Map()
    for (const id of this.playerIds) {
      this.players.set(id, {
        playerId: id,
        destroyed: new Set(),
        shots: new Map(),
        incoming: [],
        hits: 0,
        connected: true,
        disconnectedAt: null,
      })
    }

    // rng 决定先手：< 0.5 取第一个玩家
    this.turnIndex = this.rng() < 0.5 ? 0 : 1
    this.placing = new PlacingPhase(this.rules, this.playerIds, opts.now, this.rng)
  }

  get phase(): GamePhase {
    return this._phase
  }

  get result(): GameResult | null {
    return this._result
  }

  private get deadlineAt(): number | null {
    if (this._phase === 'placing') return this.placing.deadlineAt
    if (this._phase === 'playing') return this.turnDeadlineAt
    return null
  }

  private get turnMs(): number {
    return this.rules.turnSeconds * 1000
  }

  private otherPlayerId(playerId: string): string {
    return this.playerIds[0] === playerId ? this.playerIds[1] : this.playerIds[0]
  }

  private get currentTurnPlayerId(): string {
    return this.playerIds[this.turnIndex]!
  }

  private error(to: string, code: ErrorCode, message?: string): Outbound {
    return { to, msg: { type: 'error', code, message: message ?? code } }
  }

  private broadcast(msg: ServerMessage): Outbound[] {
    return this.playerIds.map((to) => ({ to, msg }))
  }

  // ---------------------------------------------------------------- handle

  /** 只处理 placePlane / fire / leaveRoom；finished 之后一律忽略。 */
  handle(playerId: string, msg: ClientMessage, now: number): Outbound[] {
    const player = this.players.get(playerId)
    if (player === undefined || this._phase === 'finished') return []
    if (msg.type === 'leaveRoom') return this.forfeit(this.otherPlayerId(playerId))

    switch (this._phase) {
      case 'placing':
        return this.handlePlacing(player, msg, now)
      case 'playing':
        return this.handlePlaying(player, msg, now)
      case 'paused':
        return [this.error(playerId, 'PAUSED', '对手已掉线，等待重连')]
    }
  }

  private handlePlacing(player: PlayerState, msg: ClientMessage, now: number): Outbound[] {
    if (msg.type !== 'placePlane') return [this.error(player.playerId, 'WRONG_PHASE', '当前是摆放阶段')]
    const out = this.placing.place(player.playerId, msg.planes)
    if (this.placing.allPlaced) out.push(...this.startPlaying(now))
    return out
  }

  private handlePlaying(player: PlayerState, msg: ClientMessage, now: number): Outbound[] {
    if (msg.type !== 'fire') return [this.error(player.playerId, 'WRONG_PHASE', '当前不能执行该操作')]
    if (this.currentTurnPlayerId !== player.playerId) return [this.error(player.playerId, 'NOT_YOUR_TURN')]

    const size = this.rules.boardSize
    if (
      !Number.isInteger(msg.row) ||
      !Number.isInteger(msg.col) ||
      msg.row < 0 ||
      msg.row >= size ||
      msg.col < 0 ||
      msg.col >= size
    ) {
      return [this.error(player.playerId, 'OUT_OF_RANGE')]
    }

    const cell = { row: msg.row, col: msg.col }
    if (isRepeatShot(new Set(player.shots.keys()), cell)) return [this.error(player.playerId, 'REPEAT_SHOT')]

    return this.applyShot(player, cell, now)
  }

  private startPlaying(now: number): Outbound[] {
    this._phase = 'playing'
    this.turnDeadlineAt = now + this.turnMs
    return this.broadcast({
      type: 'phaseChanged',
      phase: 'playing',
      deadlineAt: this.turnDeadlineAt,
      turn: this.currentTurnPlayerId,
    })
  }

  /** 结算一炮。正常开炮与超时代打共用此路径。 */
  private applyShot(shooter: PlayerState, cell: Cell, now: number): Outbound[] {
    const target = this.players.get(this.otherPlayerId(shooter.playerId))!
    const targetPlanes = toPlaneRefs(this.placing.planesOf(target.playerId) ?? [])
    const resolution = resolveShot(targetPlanes, cell)
    const result = resolution.result
    const planeId = resolution.result === 'miss' ? 'p0' : resolution.planeId

    shooter.shots.set(cellKey(cell), { targetId: target.playerId, row: cell.row, col: cell.col, result, planeId })
    target.incoming.push({ by: shooter.playerId, row: cell.row, col: cell.col, result, planeId })
    if (result !== 'miss') shooter.hits++
    if (result === 'head') target.destroyed.add(planeId)

    // 先换手（若对局未结束），再广播，这样 nextTurn 是最终值
    const allDestroyed = isAllPlanesDestroyed(targetPlanes, [...target.destroyed])
    if (!allDestroyed) {
      this.turnIndex = this.turnIndex === 0 ? 1 : 0
      this.turnDeadlineAt = now + this.turnMs
    }

    const out: Outbound[] = this.broadcast({
      type: 'shotResult',
      by: shooter.playerId,
      row: cell.row,
      col: cell.col,
      result,
      planeId,
      nextTurn: this.currentTurnPlayerId,
    })
    if (result === 'head') {
      out.push(...this.broadcast({ type: 'planeDestroyed', ownerId: target.playerId, planeId }))
    }
    if (allDestroyed) {
      out.push(...this.finish(shooter.playerId, this.rules.planeCount === 1 ? 'head' : 'allPlanes'))
    }
    return out
  }

  private finish(winnerId: string, reason: GameOverReason): Outbound[] {
    const loserId = this.otherPlayerId(winnerId)
    this._phase = 'finished'
    this.turnDeadlineAt = null
    this.pausedAt = null
    this.resumePhase = null
    this._result = {
      reason,
      ranking: [
        { playerId: winnerId, rank: 1, eliminatedRound: null, hits: this.players.get(winnerId)!.hits },
        { playerId: loserId, rank: 2, eliminatedRound: null, hits: this.players.get(loserId)!.hits },
      ],
    }
    return this.broadcast({ type: 'gameOver', result: this._result })
  }

  private forfeit(winnerId: string): Outbound[] {
    return this.finish(winnerId, 'forfeit')
  }

  // ---------------------------------------------------------------- tick

  /** 推进计时。纯同步，时间从参数进来。 */
  tick(now: number): Outbound[] {
    if (this._phase === 'paused') {
      const expired = this.firstExpiredPlayer(now)
      return expired === null ? [] : this.forfeit(this.otherPlayerId(expired))
    }

    if (this._phase === 'placing') {
      if (now < this.placing.deadlineAt) return []
      // 摆放超时：为未摆放者随机落子，不判负（spec §二）
      const out = this.placing.autoPlaceMissing()
      if (this.placing.allPlaced) out.push(...this.startPlaying(now))
      return out
    }

    if (this._phase === 'playing') {
      if (this.turnDeadlineAt !== null && now >= this.turnDeadlineAt) return this.autoFire(now)
    }

    return []
  }

  /** 宽限已过的掉线玩家中，最早掉线的那位（双方都超时时判先掉线者负）。 */
  private firstExpiredPlayer(now: number): string | null {
    let found: PlayerState | null = null
    for (const p of this.players.values()) {
      if (p.disconnectedAt === null || now - p.disconnectedAt < DISCONNECT_GRACE_MS) continue
      if (found === null || p.disconnectedAt < found.disconnectedAt!) found = p
    }
    return found?.playerId ?? null
  }

  /** 回合超时：在对方棋盘上随机挑一个未打过的格子代打。 */
  private autoFire(now: number): Outbound[] {
    const shooter = this.players.get(this.currentTurnPlayerId)!
    const pool = unshotCells(this.rules.boardSize, new Set(shooter.shots.keys()))
    if (pool.length === 0) return []
    const pick = pool[Math.floor(this.rng() * pool.length)] ?? pool[0]!
    return this.applyShot(shooter, pick, now)
  }

  // ---------------------------------------------------------------- 连接

  /**
   * 掉线：通知对手 presence，未暂停则进入 paused。
   * 重连：不发快照（state 由 Table 发送），宽限已过则判负，否则顺延 deadline 并恢复。
   */
  setConnected(playerId: string, connected: boolean, now: number): Outbound[] {
    const player = this.players.get(playerId)
    if (player === undefined) return []
    const other = this.otherPlayerId(playerId)

    if (!connected) {
      if (!player.connected) return []
      player.connected = false
      player.disconnectedAt = now
      if (this._phase === 'finished') return []

      const out: Outbound[] = [{ to: other, msg: { type: 'presence', playerId, connected: false } }]
      if (this._phase !== 'paused') {
        this.pausedAt = now
        this.resumePhase = this._phase
        this._phase = 'paused'
        // 在线方也要知道进入暂停（I5/C3），否则倒计时继续走、界面不变
        out.push({ to: other, msg: { type: 'phaseChanged', phase: 'paused', deadlineAt: null } })
      }
      return out
    }

    // ---- 重连 ----
    const wasOffline = !player.connected
    const droppedAt = player.disconnectedAt
    player.connected = true
    player.disconnectedAt = null

    // 已在线又来一次（半开连接后的新 socket，I2）或对局已结束：快照由 Table 补发
    if (!wasOffline || this._phase === 'finished') return []

    // 宽限已过但 tick 还没来得及判（C1）：在这里判掉线方负
    if (droppedAt !== null && now - droppedAt >= DISCONNECT_GRACE_MS) return this.forfeit(other)

    const out: Outbound[] = [{ to: other, msg: { type: 'presence', playerId, connected: true } }]

    // 对方也还掉线着：保持暂停（I1）
    if (!this.players.get(other)!.connected) return out

    if (this._phase === 'paused' && this.pausedAt !== null) {
      const paused = now - this.pausedAt
      const resume = this.resumePhase ?? 'playing'
      if (resume === 'placing') this.placing.extend(paused)
      else if (this.turnDeadlineAt !== null) this.turnDeadlineAt += paused
      this._phase = resume
      this.pausedAt = null
      this.resumePhase = null
      out.push(
        ...this.broadcast(
          resume === 'playing'
            ? { type: 'phaseChanged', phase: resume, deadlineAt: this.deadlineAt, turn: this.currentTurnPlayerId }
            : { type: 'phaseChanged', phase: resume, deadlineAt: this.deadlineAt },
        ),
      )
    }
    return out
  }

  // ---------------------------------------------------------------- 视图

  view(playerId: string): GameView {
    const you = this.players.get(playerId)
    if (you === undefined) throw new Error(`player ${playerId} 不在本局`)
    const opp = this.players.get(this.otherPlayerId(playerId))!
    const alive = (p: PlayerState) => p.destroyed.size < this.rules.planeCount

    return {
      mode: 'duel',
      phase: this._phase,
      deadlineAt: this.deadlineAt,
      turn: this.currentTurnPlayerId,
      round: null,
      you: {
        planes: this.placing.planesOf(playerId) ?? [],
        planesDestroyed: you.destroyed.size,
        alive: alive(you),
        shots: [...you.shots.values()],
        incoming: [...you.incoming],
        // 轮流制没有「本轮已提交」：一炮即结算（评审 M1）
        submitted: false,
        pendingShot: null,
      },
      others: [
        {
          playerId: opp.playerId,
          connected: opp.connected,
          alive: alive(opp),
          planesDestroyed: opp.destroyed.size,
          submitted: false,
        },
      ],
    }
  }
}
