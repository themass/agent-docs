/**
 * 牌桌：座位、准备、房主、规则与续局生命周期（spec §19.4）。
 * 桌子不懂对局细节，对局由注入的 Engine 负责；桌子只在引擎 finished 后回到 waiting。
 * P2：电脑也是一个座位（seat.bot 非空），由 tick 驱动；发给电脑的消息一律丢弃（spec §20.2）。
 */
import { BOT_ID_PREFIX, sanitizeNickname } from '@plane-duel/shared'
import type {
  BotDifficulty,
  Capacity,
  ClientMessage,
  ErrorCode,
  Mode,
  PresetId,
  RoomListEntry,
  RuleSet,
  TableKind,
  TablePhase,
  TableResult,
  TableView,
} from '@plane-duel/shared'
import { randomBytes } from 'node:crypto'
import { BotDriver } from './bot/driver'
import type { BotBrainLike } from './bot/driver'
import { createEngine } from './engine'
import type { Engine, EngineOptions, Outbound } from './engine'

/** 等候室掉线者是唯一在座者时（典型：房主切去微信发房间号），座位保留 5 分钟（裁定 R2）。 */
export const FRIEND_SEAT_GRACE_MS = 300_000
/** 等候室里还有别人在座时，掉线者的座位保留 60 秒（裁定 R2）。 */
export const MATCH_SEAT_GRACE_MS = 60_000

const randomTableId = (): string => randomBytes(8).toString('hex')

export type TableOptions = {
  roomCode: string
  kind: TableKind
  capacity: Capacity
  rules: RuleSet
  now: number
  /** 是否公开到大厅列表（spec §20.6）；只有好友房可以公开，默认 false */
  listed?: boolean
  /** 列表用的不透明 id；不传则随机生成（16 位十六进制） */
  tableId?: string
  engineFactory?: (o: EngineOptions) => Engine
  /** 电脑的驱动器；默认 BotDriver（spec §20.3）。每个电脑座位一个实例。 */
  botFactory?: (playerId: string, difficulty: BotDifficulty, rng: () => number) => BotBrainLike
  /** 传给引擎与电脑的随机源（先手、自动摆放、思考时间）；测试用于确定性 */
  rng?: () => number
  /** 匹配桌的规则档位（计分局档案里记录预设 id）；好友/自定义规则为 undefined */
  preset?: PresetId
}

type Seat = {
  playerId: string
  nickname: string
  ready: boolean
  connected: boolean
  /** 最近一次掉线的时间；在线时为 null */
  disconnectedAt: number | null
  /** 对局中已离开，座位保留到本局结束 */
  left: boolean
  /** 电脑的驱动器；真人为 null（spec §20.2） */
  bot: BotBrainLike | null
}

export class Table {
  readonly roomCode: string
  readonly kind: TableKind
  readonly capacity: Capacity

  private _rules: RuleSet
  /** 规则版本：每次成功 updateRules +1（spec §20.7 M4） */
  private _rulesVersion = 0
  private _phase: TablePhase = 'waiting'
  private _closed = false
  private _engine: Engine | null = null
  private _hostId: string | null = null
  private _lastResult: TableResult | null = null
  private gamesPlayed = 0
  /** 刚结束那局的稳定 id（tableId:gamesPlayed，spec §21.7 幂等键） */
  private _lastGameId: string | null = null
  /** 刚结束那局的引擎模式（计分档案记录 duel/melee） */
  private _lastMode: Mode | null = null
  /** 刚结束那局结束时还坐在桌边的真人（随后 close 会清空座位，Hub 计分要赶在前面） */
  private _lastHumans: string[] = []
  /** 被房主踢出本桌的 playerId：本桌关闭前不得再加入（spec §20.8） */
  private readonly banned = new Set<string>()
  /** 电脑 playerId 的递增序号，按本桌计（spec §20.2） */
  private botSeq = 0
  /** 本局电脑的 playerId（开局时快照），关桌后进 lastResult.botIds */
  private _botIds: string[] = []
  /** 大厅列表用的不透明 id（spec §20.6）：不含房间号，也不含 playerId */
  readonly tableId: string
  /** 匹配桌的规则档位（§21.4）；好友/自定义规则为 null */
  readonly preset: PresetId | null
  /** 是否公开到大厅列表；匹配房与练习房恒为 false */
  private _listed: boolean
  /** 建桌时刻，列表条目用于排序 */
  private readonly createdAt: number
  private readonly seats: (Seat | null)[]
  private readonly engineFactory: (o: EngineOptions) => Engine
  private readonly botFactory: (playerId: string, difficulty: BotDifficulty, rng: () => number) => BotBrainLike
  private readonly rng?: () => number

  constructor(opts: TableOptions) {
    this.roomCode = opts.roomCode
    this.kind = opts.kind
    this.capacity = opts.capacity
    this._rules = { ...opts.rules }
    this.seats = Array.from({ length: opts.capacity }, () => null)
    this.engineFactory = opts.engineFactory ?? createEngine
    this.botFactory = opts.botFactory ?? ((id, d, rng) => new BotDriver(id, d, rng))
    if (opts.rng) this.rng = opts.rng
    this.tableId = opts.tableId ?? randomTableId()
    this.preset = opts.preset ?? null
    // 只有好友房可以公开（spec §20.6）
    this._listed = opts.listed === true && opts.kind === 'friend'
    this.createdAt = opts.now
  }

  get rules(): RuleSet {
    return this._rules
  }
  get rulesVersion(): number {
    return this._rulesVersion
  }
  get listed(): boolean {
    return this._listed
  }
  get phase(): TablePhase {
    return this._phase
  }
  get isClosed(): boolean {
    return this._closed
  }
  /** 占着座位的 playerId（对局中已离开但座位未释放者也在内）。 */
  get members(): string[] {
    return this.seated().map((s) => s.playerId)
  }
  /**
   * 还在桌上的真人（电脑不算；对局中已离开、座位未释放的也不算）。
   * 与 members 不同：电脑不参与"有人"的判断（spec §20.4/§20.5）。
   */
  get humanMembers(): string[] {
    return this.active()
      .filter((s) => s.bot === null)
      .map((s) => s.playerId)
  }
  /** 桌上还有没有真人；没有就该关桌，不让电脑之间空转（spec §20.5）。 */
  get hasHumans(): boolean {
    return this.humanMembers.length > 0
  }
  get engine(): Engine | null {
    return this._engine
  }
  /** 刚结束那局的计分信息（Hub 在 gameOver 后立刻读；无结果为 null，spec §21.7） */
  get lastGame(): { id: string; mode: Mode; preset: PresetId | null; result: TableResult; humans: string[] } | null {
    if (this._lastResult === null || this._lastGameId === null || this._lastMode === null) return null
    return { id: this._lastGameId, mode: this._lastMode, preset: this.preset, result: this._lastResult, humans: [...this._lastHumans] }
  }
  /** 当前在座的真人 playerId（对局中已离开者不含） */
  humanIds(): string[] {
    return this.humanMembers
  }

  join(playerId: string, nickname: string, now: number): Outbound[] {
    const existing = this.find(playerId)
    if (existing && !existing.left) return [this.stateFor(playerId)]
    const code = this.admitError(playerId)
    if (code !== null) return [this.errFor(playerId, code)]

    const index = this.seats.indexOf(null)
    this.seats[index] = {
      playerId,
      nickname: sanitizeNickname(nickname, `玩家${index + 1}`),
      ready: false,
      connected: true,
      disconnectedAt: null,
      left: false,
      bot: null,
    }
    if (this.kind === 'friend' && this._hostId === null) this._hostId = playerId
    return this.afterSeat(now)
  }

  /**
   * 外人能不能凭房间号 / 列表加入本桌（Hub 的预检用）：null = 可以。
   * 练习桌没有外来入口（spec §20.4），被踢者在本桌关闭前不得再加入（spec §20.8）。
   */
  canJoin(playerId: string): ErrorCode | null {
    if (this.kind === 'practice') return 'ROOM_NOT_FOUND'
    return this.admitError(playerId)
  }

  /**
   * 补一个电脑到最小的空座（spec §20.2/§20.5）：等候中且有空座才生效，否则返回 []。
   * 与 join 共用开局判定（match / practice 首局人满即开）。
   */
  addBot(difficulty: BotDifficulty, now: number): Outbound[] {
    if (this._closed) return []
    if (this._phase !== 'waiting') return []
    const index = this.seats.indexOf(null)
    if (index < 0) return []
    const playerId = `${BOT_ID_PREFIX}${this.roomCode}:${index}:${++this.botSeq}`
    this.seats[index] = {
      playerId,
      // 电脑不走 sanitizeNickname：昵称由服务端直接赋值（spec §20.2）
      nickname: `电脑${index + 1}`,
      ready: true,
      connected: true,
      disconnectedAt: null,
      left: false,
      bot: this.botFactory(playerId, difficulty, this.rng ?? Math.random),
    }
    return this.afterSeat(now)
  }

  leave(playerId: string, now: number): Outbound[] {
    if (this._closed) return []
    const seat = this.find(playerId)
    if (!seat || seat.left) return []
    if (this._phase === 'inGame') return this.leaveInGame(seat, now)
    return this.release(seat)
  }

  /**
   * 准备 / 取消准备。带规则版本（spec §20.7 M4）：房主改规则会 +1，
   * 携带旧版本的准备说明本人还没看过新规则，拒绝并补发本人当前状态。
   * 已准备者再发 setReady(true) 是幂等重复，照常广播。
   */
  setReady(playerId: string, ready: boolean, rulesVersion: number, now: number): Outbound[] {
    const seat = this.find(playerId)
    if (!seat || seat.left) return [this.err(playerId, 'NOT_IN_ROOM', '不在房间中')]
    if (this._phase !== 'waiting') return [this.err(playerId, 'WRONG_PHASE', '对局进行中')]
    if (rulesVersion !== this._rulesVersion) {
      return [this.err(playerId, 'STALE_RULES', '规则已更新，请重试'), this.tableStateTo(playerId)]
    }
    seat.ready = ready
    if (this.isFull() && this.seated().every((s) => s.ready)) {
      this.startGame(now)
      return this.broadcastStart()
    }
    return this.broadcastTable()
  }

  updateRules(playerId: string, rules: RuleSet, _now: number): Outbound[] {
    const seat = this.find(playerId)
    if (!seat || seat.left) return [this.err(playerId, 'NOT_IN_ROOM', '不在房间中')]
    // 练习房没有房主，因此谁都不能改规则（spec §20.4）
    if (this.kind !== 'friend' || playerId !== this._hostId) {
      return [this.err(playerId, 'NOT_HOST', '只有房主可以修改规则')]
    }
    if (this._phase === 'inGame') return [this.err(playerId, 'ROOM_IN_GAME', '对局进行中')]
    this._rules = { ...rules }
    this._rulesVersion++
    this.resetReady()
    return this.broadcastTable()
  }

  /**
   * 房主踢人（spec §20.8）：仅在好友房的等候室里，踢一个未准备的真人在座者。
   * 已准备者不能踢——他就在开局倒计时的路上，桌子会自己把他带进对局（用户裁定）。
   * 被踢者收到 kicked、座位立即释放、本桌关闭前不得再加入。
   */
  kick(hostId: string, targetId: string, _now: number): Outbound[] {
    const actor = this.find(hostId)
    if (!actor || actor.left) return [this.err(hostId, 'NOT_IN_ROOM', '不在房间中')]
    // 匹配房、练习房没有房主，也就没有人可以踢（spec §20.8）
    if (this.kind !== 'friend' || hostId !== this._hostId) {
      return [this.err(hostId, 'NOT_HOST', '只有房主可以踢人')]
    }
    if (this._phase === 'inGame') return [this.err(hostId, 'ROOM_IN_GAME', '对局进行中')]
    const target = this.find(targetId)
    if (!target || target.left || target.playerId === hostId || target.bot !== null) {
      return [this.err(hostId, 'TARGET_NOT_FOUND', '目标不在房间中')]
    }
    if (target.ready) return [this.err(hostId, 'TARGET_READY', '对方已准备，无法踢出')]

    this.banned.add(target.playerId)
    // kicked 先于释放：release 只把 tableState 发给剩下的人
    return this.out([{ to: target.playerId, msg: { type: 'kicked', roomCode: this.roomCode } }, ...this.release(target)])
  }

  setNickname(playerId: string, nickname: string): Outbound[] {
    const seat = this.find(playerId)
    if (!seat || seat.left) return [this.err(playerId, 'NOT_IN_ROOM', '不在房间中')]
    seat.nickname = sanitizeNickname(nickname, seat.nickname)
    return this.broadcastTable()
  }

  handleGame(playerId: string, msg: ClientMessage, now: number): Outbound[] {
    const seat = this.find(playerId)
    if (!seat || seat.left) return [this.err(playerId, 'NOT_IN_ROOM', '不在房间中')]
    if (!this._engine) return [this.err(playerId, 'WRONG_PHASE', '对局未开始')]
    if (msg.type === 'leaveRoom') return this.leave(playerId, now)
    const out = this._engine.handle(playerId, msg, now)
    return this.out([...out, ...this.afterEngine(now)])
  }

  tick(now: number): Outbound[] {
    if (this._closed) return []
    if (!this._engine) return this.out(this.releaseExpired(now))
    const out = [...this._engine.tick(now), ...this.afterEngine(now)]
    if (this._engine) this.pollBots(now, out)
    return this.out(out)
  }

  setConnected(playerId: string, connected: boolean, now: number): Outbound[] {
    if (this._closed) return []
    const seat = this.find(playerId)
    // 电脑永远在线，掉线状态对它没有意义（spec §20.2）
    if (!seat || seat.left || seat.bot !== null) return []
    seat.connected = connected
    seat.disconnectedAt = connected ? null : now
    if (this._engine) {
      const out = this._engine.setConnected(playerId, connected, now)
      const after = this.afterEngine(now)
      // 引擎结束时 afterEngine 已经广播过桌子状态
      if (this._engine === null) return this.out([...out, ...after])
      return this.out([...out, ...after, ...this.broadcastTable()])
    }
    return this.out(this.broadcastTable())
  }

  view(): TableView {
    return {
      roomCode: this.roomCode,
      kind: this.kind,
      capacity: this.capacity,
      rules: this._rules,
      rulesVersion: this._rulesVersion,
      listed: this._listed,
      hostId: this._hostId,
      phase: this._phase,
      seats: this.seats.map((s, i) =>
        s
          ? {
              seat: i,
              playerId: s.playerId,
              nickname: s.nickname,
              ready: s.ready,
              connected: s.connected,
              bot: s.bot !== null,
            }
          : null,
      ),
      lastResult: this._lastResult,
    }
  }

  stateFor(playerId: string): Outbound {
    return {
      to: playerId,
      msg: { type: 'state', table: this.view(), game: this._engine ? this._engine.view(playerId) : null },
    }
  }

  /**
   * 大厅列表的投影（spec §20.6）：只有"好友房 + 已公开 + 等候中 + 有空座"才出现。
   * 条目里没有房间号、没有 playerId、没有准备状态；电脑座位也只露 { seat, nickname }。
   */
  listing(): RoomListEntry | null {
    if (this._closed) return null
    if (this.kind !== 'friend' || !this._listed) return null
    if (this._phase !== 'waiting') return null
    if (this.isFull()) return null

    const hostNickname = this._hostId === null ? '' : (this.find(this._hostId)?.nickname ?? '')
    return {
      tableId: this.tableId,
      capacity: this.capacity,
      rules: this._rules,
      hostNickname,
      seated: this.seated().length,
      seats: this.seats.map((s, i) => (s === null ? null : { seat: i, nickname: s.nickname })),
      createdAt: this.createdAt,
    }
  }

  /** 房主开关"公开到大厅列表"（spec §20.6）。 */
  setListed(playerId: string, listed: boolean): Outbound[] {
    const actor = this.find(playerId)
    if (!actor || actor.left) return [this.err(playerId, 'NOT_IN_ROOM', '不在房间中')]
    if (this.kind !== 'friend' || playerId !== this._hostId) {
      return [this.err(playerId, 'NOT_HOST', '只有房主可以修改公开设置')]
    }
    if (this._phase === 'inGame') return [this.err(playerId, 'ROOM_IN_GAME', '对局进行中')]
    this._listed = listed
    return this.out(this.broadcastTable())
  }

  // ---------- 内部 ----------

  private seated(): Seat[] {
    return this.seats.filter((s): s is Seat => s !== null)
  }

  private active(): Seat[] {
    return this.seated().filter((s) => !s.left)
  }

  private find(playerId: string): Seat | undefined {
    return this.seated().find((s) => s.playerId === playerId)
  }

  private isFull(): boolean {
    return this.seats.every((s) => s !== null)
  }

  private err(to: string, code: ErrorCode, message: string): Outbound {
    return { to, msg: { type: 'error', code, message } }
  }

  /** 加入类错误的文案；错误码本身才是协议语义，这里只是给人看的一句话。 */
  private errFor(to: string, code: ErrorCode): Outbound {
    const messages: Partial<Record<ErrorCode, string>> = {
      ROOM_NOT_FOUND: '房间不存在',
      BANNED: '已被房主移出房间',
      ROOM_IN_GAME: '对局进行中',
      ROOM_FULL: '房间已满',
    }
    return this.err(to, code, messages[code] ?? '无法加入房间')
  }

  /** 外人加入本桌的准入判定（join 与 canJoin 共用）：null = 可以加入。 */
  private admitError(playerId: string): ErrorCode | null {
    if (this._closed) return 'ROOM_NOT_FOUND'
    if (this.banned.has(playerId)) return 'BANNED'
    if (this._phase === 'inGame') return 'ROOM_IN_GAME'
    if (this.isFull()) return 'ROOM_FULL'
    return null
  }
  /** 只发给一个人（含最新规则版本）。 */
  private tableStateTo(playerId: string): Outbound {
    return { to: playerId, msg: { type: 'tableState', table: this.view() } }
  }

  /** 丢弃发给电脑的出站消息：电脑没有 socket，也不缓存（spec §20.2）。 */
  private out(out: Outbound[]): Outbound[] {
    return out.filter((o) => !o.to.startsWith(BOT_ID_PREFIX))
  }

  private broadcastTable(): Outbound[] {
    return this.out(this.active().map((s) => this.tableStateTo(s.playerId)))
  }

  /** 开局：桌子状态之外，给每位在座者发含引擎视图（摆放 deadlineAt）的完整 state。 */
  private broadcastStart(): Outbound[] {
    return this.out([...this.broadcastTable(), ...this.active().map((s) => this.stateFor(s.playerId))])
  }

  /**
   * 裁定 R2：掉线者是唯一的真人时保留 5 分钟，否则 60 秒（只数真人，电脑不算有人等，spec §20.4）。
   */
  private seatGraceMs(seat: Seat): number {
    return this.humanMembers.length === 1 && this.humanMembers[0] === seat.playerId
      ? FRIEND_SEAT_GRACE_MS
      : MATCH_SEAT_GRACE_MS
  }

  /** 清空准备；电脑永远已准备，立即恢复（spec §20.2）。 */
  private resetReady(): void {
    for (const s of this.seated()) s.ready = s.bot !== null
  }

  /** 入座之后的开局判定：match / practice 首局人满即开，否则广播。 */
  private afterSeat(now: number): Outbound[] {
    const autoStart = this.kind === 'match' || this.kind === 'practice'
    if (autoStart && this.gamesPlayed === 0 && this.isFull()) {
      this.startGame(now)
      return this.broadcastStart()
    }
    return this.broadcastTable()
  }

  /** 同步新建引擎，规则取开局这一刻的值。 */
  private startGame(now: number): void {
    const seats = this.seated()
    this.resetReady()
    this._lastResult = null
    this._botIds = seats.filter((s) => s.bot !== null).map((s) => s.playerId)
    this._phase = 'inGame'
    this._engine = this.engineFactory({
      rules: { ...this._rules },
      playerIds: seats.map((s) => s.playerId),
      now,
      ...(this.rng ? { rng: this.rng } : {}),
    })
    // 引擎默认全员在线；开局这一刻已掉线的座位要告诉它（评审 I1）。
    // 其输出不转发：紧随其后的 broadcastStart 快照已反映掉线状态。
    for (const s of seats) {
      if (!s.connected) this._engine.setConnected(s.playerId, false, now)
    }
  }

  /**
   * 依座位顺序让每个电脑做一次决策（spec §20.2）：输入只有 engine.view(自己) 与 rules，
   * 动作走引擎的公开入口。引擎一结束就停止本轮轮询。
   */
  private pollBots(now: number, out: Outbound[]): void {
    for (const seat of this.seated()) {
      const engine = this._engine
      if (!engine || engine.phase === 'finished') return
      if (seat.bot === null) continue
      const msg = seat.bot.poll(engine.view(seat.playerId), this._rules, now)
      if (msg === null) continue
      out.push(...engine.handle(seat.playerId, msg, now))
      out.push(...this.afterEngine(now))
    }
  }

  /** 房主离开后转给最小座位号的在座者。 */
  private fixHost(): void {
    if (this.kind !== 'friend') return
    if (this._hostId !== null && this.active().some((s) => s.playerId === this._hostId)) return
    this._hostId = this.active()[0]?.playerId ?? null
  }

  private clearSeat(seat: Seat): void {
    const i = this.seats.indexOf(seat)
    if (i >= 0) this.seats[i] = null
  }

  private close(notify: boolean): Outbound[] {
    const out: Outbound[] = notify
      ? this.active().map((s) => ({ to: s.playerId, msg: { type: 'roomClosed' } }))
      : []
    this._closed = true
    this._hostId = null
    this._engine = null
    this._botIds = []
    for (let i = 0; i < this.seats.length; i++) this.seats[i] = null
    return this.out(out)
  }

  /** 等候中释放座位（leave 与掉线超时共用）。 */
  private release(seat: Seat): Outbound[] {
    this.clearSeat(seat)
    // 桌上没有真人就关桌，不让电脑之间空转（spec §20.5）
    if (!this.hasHumans) return this.close(false)
    if (this.kind === 'match' && this.gamesPlayed > 0) return this.close(true)
    this.fixHost()
    return this.out(this.broadcastTable())
  }

  private releaseExpired(now: number): Outbound[] {
    const out: Outbound[] = []
    for (const seat of [...this.seated()]) {
      if (this._closed) break
      if (seat.connected || seat.disconnectedAt === null) continue
      if (now - seat.disconnectedAt >= this.seatGraceMs(seat)) out.push(...this.release(seat))
    }
    return out
  }

  private leaveInGame(seat: Seat, now: number): Outbound[] {
    const out = this._engine ? this._engine.handle(seat.playerId, { type: 'leaveRoom' }, now) : []
    seat.left = true
    this.fixHost()
    out.push(...this.afterEngine(now))
    // 没有真人了就关桌，不广播（spec §20.5）
    if (!this.hasHumans) return this.out([...out, ...this.close(false)])
    // 引擎结束时 afterEngine 已经广播过桌子状态
    if (this._engine !== null) out.push(...this.broadcastTable())
    return this.out(out)
  }

  /** 引擎调用之后检查是否结束；结束则记录结果、释放离开者的座位、应用匹配房规则。 */
  private afterEngine(now: number): Outbound[] {
    const engine = this._engine
    if (!engine || engine.phase !== 'finished') return []
    this._lastResult = engine.result ? { ...engine.result, botIds: this._botIds } : null
    // 计分局档案用（spec §21.7）：id = tableId:gamesPlayed，重复 gameOver 重放不加星
    this._lastGameId = engine.result ? `${this.tableId}:${this.gamesPlayed}` : null
    this._lastMode = engine.result ? engine.mode : null
    this._botIds = []
    // close()/release() 可能在本轮就把座位清空（match 桌有人离开即关桌），
    // 所以此刻就把还坐在桌边的真人快照下来，交给 Hub 计分
    this._lastHumans = this.humanMembers
    this._engine = null
    this._phase = 'waiting'
    this.gamesPlayed++

    let someoneLeft = false
    for (const seat of [...this.seated()]) {
      if (seat.left) {
        someoneLeft = true
        this.clearSeat(seat)
      } else if (!seat.connected) {
        // 等候室的掉线宽限从本局结束时重新计时
        seat.disconnectedAt = now
      }
    }
    // 桌上没有真人就关桌，不让电脑之间空转（spec §20.5）
    if (!this.hasHumans) return this.close(false)
    // 关桌前先把结果发给留下的人，否则他们只收到 gameOver + roomClosed，看不到排名（评审 C1）
    if (this.kind === 'match' && someoneLeft) return this.out([...this.broadcastTable(), ...this.close(true)])
    this.fixHost()
    return this.out(this.broadcastTable())
  }
}
