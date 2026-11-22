/**
 * Hub：连接管理、身份校验、消息路由、牌桌表、多队列匹配（spec §九、§19.4、§19.7）。
 *
 * 所有投递都经回调，因此本类可在无真实 socket 的情况下测试。
 *
 * 身份：playerId 首次认证时由服务端签发 token；之后该 playerId 的任何认证
 * 都必须带同一个 token（评审 C2：否则对手可冒充你重连、拿到你的机头位置）。
 *
 * 一个玩家同一时刻至多在一张桌上或一个队列里：建房 / 加入 / 排队都会先离开
 * 当前的等候桌或队列（Review Focus #4）；对局中则一律 ALREADY_IN_ROOM。
 */

import { randomUUID } from 'node:crypto'
import { BOT_ID_PREFIX, COIN, dayKey, PRESETS, TICKETS, isNicknameAllowed, parseClientMessage, sanitizeNickname } from '@plane-duel/shared'
import type { Capacity, ClientMessage, ErrorCode, RankListEntry, RoomListEntry, RuleSet, ServerMessage, TicketId } from '@plane-duel/shared'
import type { Clock } from './clock'
import type { Outbound } from './engine'
import { BOT_FILL_AFTER_MS, Matchmaking, type MatchGroup } from './matchmaking'
import { MemoryProfileStore, type ProfileStore } from './profile'
import { Table } from './table'
import type { BotDifficulty, PresetId } from '@plane-duel/shared'

const DEFAULT_NICKNAME = '玩家'

/** 大厅列表每个专区最多推送的条目数（spec §20.6）。 */
export const ROOM_LIST_MAX = 50
/** 同一专区两次推送的最小间隔；期间的变化合并为一次（spec §20.6）。 */
export const ROOM_LIST_MIN_INTERVAL_MS = 1_000

/** 昵称口径（Task 2 裁定）：先清洗，再查屏蔽，命中即回退——服务端是唯一防线。 */
const acceptedNickname = (input: unknown, fallback: string): string => {
  const name = sanitizeNickname(input, fallback)
  return isNicknameAllowed(name) ? name : fallback
}

export type HubOptions = {
  clock: Clock
  devMode?: boolean
  /** 供测试注入确定性房间号 */
  makeRoomCode?: () => string
  /** 传给每张桌子的随机源（先手、自动摆放）；测试用于确定性 */
  rng?: () => number
  /** 匹配补位倒计时；默认 BOT_FILL_AFTER_MS（spec §20.5），显式传 null 关闭 */
  botFillMs?: number | Readonly<Record<Capacity, number>> | null
  /** 列表用的不透明 tableId 生成器；默认 16 位十六进制 */
  makeTableId?: () => string
  /** 玩家档案（P3）；默认内存实现，main.ts 传 JSON 文件实现 */
  profiles?: ProfileStore
}

/** 段位榜返回条数（spec §21.5）。 */
export const RANK_LIST_MAX = 50

type Session = {
  sessionId: string
  playerId: string
  send: (msg: ServerMessage) => void
  close: () => void
}

const randomRoomCode = (): string => Math.floor(100000 + Math.random() * 900000).toString()
const randomTableId = (): string => randomUUID().replace(/-/g, '').slice(0, 16)

export class Hub {
  private readonly clock: Clock
  private readonly makeRoomCode: () => string
  private readonly makeTableId: () => string
  private readonly rng?: () => number
  private readonly matchmaking: Matchmaking
  private readonly profiles: ProfileStore

  private readonly tables = new Map<string, Table>()
  private readonly tableByPlayer = new Map<string, string>()
  /** M5（spec §20.7）：桌 → 真人成员集合。sync 只遍历它，不再遍历全部玩家。 */
  private readonly membersByTable = new Map<string, Set<string>>()
  private readonly nicknames = new Map<string, string>()

  private readonly sessions = new Map<string, Session>()
  private readonly sessionByPlayer = new Map<string, string>()
  private readonly tokens = new Map<string, string>()

  // ---------------------------------------------------------- 大厅列表订阅（spec §20.6）
  /** 会话 → 订阅的专区。 */
  private readonly roomSubs = new Map<string, Capacity>()
  /** 有变化待推送的专区。 */
  private readonly roomDirty = new Set<Capacity>()
  /** 专区 → 上次推送的内容与时刻（合并推送的依据）。 */
  private readonly roomLast = new Map<Capacity, { json: string; at: number }>()

  // ---------------------------------------------------------- P4 门票（spec §廿二.3）
  /** 排队中已付门票的玩家 → 门票档；成局转 ticketByTable，离队退款，二者互斥 */
  private readonly ticketQueue = new Map<string, TicketId>()
  /** 门票桌 → 门票档与入座玩家；首局未打完就关桌要全额退款（评审 #2），连玩家一起记 */
  private readonly ticketByTable = new Map<string, { ticket: TicketId; ids: string[] }>()
  /** 门票账目幂等键的单调序号（评审 #1）：同一毫秒多笔账互不吞并 */
  private ticketSeq = 0

  constructor(opts: HubOptions) {
    this.clock = opts.clock
    this.makeRoomCode = opts.makeRoomCode ?? randomRoomCode
    this.makeTableId = opts.makeTableId ?? randomTableId
    // 注意不能用 ??：显式传 null 表示"关闭补位"，与"没传（用默认）"语义不同
    this.matchmaking = new Matchmaking({
      botFillMs: opts.botFillMs === undefined ? BOT_FILL_AFTER_MS : opts.botFillMs,
    })
    this.profiles = opts.profiles ?? new MemoryProfileStore(() => this.clock.now())
    if (opts.rng) this.rng = opts.rng
  }

  /** 测试与 main.ts 用：当前档案存储（跨季重置、榜单断言）。 */
  get profileStore(): ProfileStore {
    return this.profiles
  }

  // ============================================================ 连接

  connect(sessionId: string, send: (msg: ServerMessage) => void, close: () => void = () => {}): void {
    this.sessions.set(sessionId, { sessionId, playerId: '', send, close })
  }

  disconnect(sessionId: string): void {
    const session = this.sessions.get(sessionId)
    if (session === undefined) return
    this.sessions.delete(sessionId)

    this.roomSubs.delete(sessionId)
    const { playerId } = session
    // 被顶掉的旧会话断开：不影响新会话
    if (playerId === '' || this.sessionByPlayer.get(playerId) !== sessionId) return
    this.sessionByPlayer.delete(playerId)
    const now = this.clock.now()

    this.dropQueue(playerId)

    const table = this.tableOf(playerId)
    if (table !== undefined) this.dispatchTable(table, table.setConnected(playerId, false, now))
  }

  // ============================================================ 入站

  receive(sessionId: string, raw: string): void {
    const session = this.sessions.get(sessionId)
    if (session === undefined) return

    const parsed = parseClientMessage(raw)
    if (!parsed.ok) {
      session.send({ type: 'error', code: parsed.code, message: parsed.code })
      return
    }
    const msg = parsed.msg

    if (msg.type === 'auth') {
      this.authenticate(session, msg.playerId, msg.token, msg.nickname)
      return
    }
    if (session.playerId === '') {
      session.send({ type: 'error', code: 'NOT_AUTHED', message: '请先认证' })
      return
    }
    this.route(session, msg)
  }

  private authenticate(session: Session, playerId: string, token: string | undefined, nickname: string | undefined): void {
    const reject = () => session.send({ type: 'error', code: 'BAD_TOKEN', message: '身份校验失败' })

    // 同一 socket 不能改换身份（M7）
    if (session.playerId !== '' && session.playerId !== playerId) return reject()

    const known = this.tokens.get(playerId)
    if (known !== undefined && known !== token) return reject()
    const issued = known ?? randomUUID()
    this.tokens.set(playerId, issued)

    // 顶掉同一玩家的旧会话，并显式关闭旧 socket（否则旧连接成为无人理会的孤儿）
    const previous = this.sessionByPlayer.get(playerId)
    if (previous !== undefined && previous !== session.sessionId) {
      const old = this.sessions.get(previous)
      this.sessions.delete(previous)
      old?.close()
    }
    session.playerId = playerId
    this.sessionByPlayer.set(playerId, session.sessionId)

    const name = acceptedNickname(nickname, DEFAULT_NICKNAME)
    this.nicknames.set(playerId, name)
    session.send({ type: 'ready', playerId, token: issued, nickname: name })
    // P4 登录礼先入账（§廿二.2：每日一次），档案再带着新余额下发
    const gift = this.profiles.loginGrant(playerId, this.clock.now())
    // 进大厅即推档案（spec §21.9：客户端无需手动入口）；匿名档案自动创建
    session.send({ type: 'profile', profile: this.profiles.view(playerId, name, this.clock.now()) })
    if (gift.applied !== 0) {
      session.send({ type: 'coinsChanged', delta: gift.applied, reason: 'login', balance: gift.coins.balance })
    }

    // 回到桌上：一定补发快照，即使服务端认为他仍在线（I2：半开连接）
    const table = this.tableOf(playerId)
    if (table !== undefined) {
      this.dispatchTable(table, table.setConnected(playerId, true, this.clock.now()))
      // 离线期间改过名：以 auth 带来的昵称为准（评审 I7）
      if (nickname !== undefined && this.tableOf(playerId) === table) {
        const seat = table.view().seats.find((x) => x?.playerId === playerId)
        if (seat && seat.nickname !== name) this.dispatchTable(table, table.setNickname(playerId, name))
      }
      if (this.tableOf(playerId) === table) this.deliver(table.stateFor(playerId))
    }
  }

  private route(session: Session, msg: ClientMessage): void {
    const playerId = session.playerId
    const now = this.clock.now()
    const table = this.tableOf(playerId)

    switch (msg.type) {
      case 'setNickname': {
        const name = acceptedNickname(msg.nickname, this.nicknames.get(playerId) ?? DEFAULT_NICKNAME)
        this.nicknames.set(playerId, name)
        this.profiles.setNickname(playerId, name)
        // 段位卡上就是昵称：改完立刻补发档案，客户端不用手动重拉
        this.sendToPlayer(playerId, { type: 'profile', profile: this.profiles.view(playerId, name, now) })
        if (table !== undefined) this.dispatchTable(table, table.setNickname(playerId, name))
        return
      }

      case 'profileRequest': {
        session.send({ type: 'profile', profile: this.profiles.view(playerId, this.nicknameOf(playerId), now) })
        return
      }

      case 'rankListRequest': {
        const { season, entries } = this.profiles.leaderboard(RANK_LIST_MAX, now)
        const rows: RankListEntry[] = entries.map((e, i) => ({
          pos: i + 1,
          nickname: e.nickname,
          tier: e.tier,
          stars: e.stars,
          wins: e.wins,
        }))
        session.send({ type: 'rankList', season, entries: rows })
        return
      }

      // P4（spec §廿二.6）：账本快照按需拉取（profile 只带余额）
      case 'coinRequest': {
        const p = this.profiles.get(playerId, this.nicknameOf(playerId), now)
        session.send({ type: 'coins', balance: p.coins.balance, ledger: p.coins.ledger, daily: p.daily })
        return
      }

      case 'adRewardRequest': {
        // 接口就位、实现是 mock（§廿二.4）：每日 5 次 × 30 金币。
        // P5 接真实广告 SDK 时在此换 verifier——先验证再发币的时序不变。
        const p = this.profiles.get(playerId, this.nicknameOf(playerId), now)
        // 跨日后旧计数作废（coin() 里会翻转，这里先按新天读）
        const adToday = p.daily.day === dayKey(now) ? p.daily.adGrants : 0
        if (adToday >= COIN.AD_DAILY_MAX) {
          session.send({ type: 'error', code: 'AD_LIMIT', message: '今日广告奖励次数已用完' })
          return
        }
        const r = this.profiles.coin(playerId, { reason: 'ad', id: `ad:${dayKey(now)}:${adToday + 1}`, at: now, delta: COIN.AD_GRANT })
        if (r.applied !== 0) this.sendToPlayer(playerId, { type: 'coinsChanged', delta: r.applied, reason: 'ad', balance: r.coins.balance, ...(r.capped ? { capped: true } : {}) })
        return
      }

      case 'roomListSubscribe': {
        // 立即回一份当前快照；tick 里只推与这份内容不同的后续变化
        this.roomSubs.set(session.sessionId, msg.capacity)
        const entries = this.roomSnapshot(msg.capacity)
        session.send({ type: 'roomList', capacity: msg.capacity, entries })
        this.roomLast.set(msg.capacity, { json: JSON.stringify(entries), at: now })
        return
      }

      case 'roomListUnsubscribe':
        this.roomSubs.delete(session.sessionId)
        return

      case 'createRoom':
        if (!this.leaveCurrent(session)) return
        this.dropRoomSub(session)
        this.joinTable(this.newTable('friend', msg.capacity, msg.rules, msg.listed), [playerId])
        return

      case 'createPractice': {
        // 练习桌（spec §20.4）：自己一个真人 + capacity−1 个电脑，规则取档位预设
        if (!this.leaveCurrent(session)) return
        this.dropRoomSub(session)
        const table = this.newTable('practice', msg.capacity, PRESETS[msg.preset], false, msg.preset)
        this.joinTable(table, [playerId], msg.capacity - 1, msg.preset)
        return
      }

      case 'joinRoom':
        this.joinRoom(session, msg.roomCode)
        return

      case 'joinListed':
        this.joinListed(session, msg.tableId)
        return

      case 'queueJoin': {
        const ticket: TicketId = msg.ticket ?? 'free'
        // 同队列重复入队是 no-op（不重扣门票）
        const prev = this.matchmaking.queueOf(playerId)
        const sameQueue = prev !== null && prev.capacity === msg.capacity && prev.preset === msg.preset && (prev.ticket ?? 'free') === ticket
        if (sameQueue) return
        if (!this.leaveCurrent(session, { keepQueue: true })) return
        this.dropRoomSub(session)
        // 换队列：旧门票先退（§廿二.3 成局前退款）
        if (this.ticketQueue.has(playerId)) this.refundTicket(playerId)
        // P4 门票预付（§廿二.3）：付了才排队；日配额 20 场
        if (ticket !== 'free') {
          if (!this.profiles.canJoinTicket(playerId, now)) return this.error(session, 'DAILY_TICKET_LIMIT', '今日门票局场次已达上限')
          // 幂等键带单调序号（评审 #1）：同一毫秒内 standard↔advanced 互切时，
          // 只用 now 会让第二笔撞上前一笔的 id、被幂等吞成 applied=0——
          // 玩家白嫖高档入场，退出时按高档退款，退款又豁免净增上限 → 无限刷币
          const r = this.profiles.coin(playerId, { reason: 'ticket-fee', id: `ticket-fee:${playerId}:${now}:${++this.ticketSeq}`, at: now, delta: -TICKETS[ticket].fee })
          if (r.insufficient) return this.error(session, 'NOT_ENOUGH_COINS', '金币不足，无法支付门票')
          if (r.applied === 0) return this.error(session, 'NOT_ENOUGH_COINS', '门票扣费异常')
          this.sendToPlayer(playerId, { type: 'coinsChanged', delta: r.applied, reason: 'ticket-fee', balance: r.coins.balance })
          this.ticketQueue.set(playerId, ticket)
        }
        // 匹配按隐藏 MMR 分桶（spec §21.2）；档案在此顺带创建/跨季重置
        // v4 兼容：客户端没带 ticket 就沿用无 ticket 的旧队列键（queueStatus 也不带该字段）
        const mmr = this.profiles.get(playerId, this.nicknameOf(playerId), now).rank.mmr
        const qkey = msg.ticket !== undefined ? { capacity: msg.capacity, preset: msg.preset, ticket } : { capacity: msg.capacity, preset: msg.preset }
        const { out, group } = this.matchmaking.join(playerId, qkey, now, mmr)
        for (const o of out) this.deliver(o)
        if (group !== null) {
          const table = this.newTable('match', group.key.capacity, PRESETS[group.key.preset], false, group.key.preset)
          this.joinTable(table, group.playerIds, group.botSeats, group.key.preset)
          this.settleQueueIntoTable(group, table.roomCode)
        }
        return
      }

      case 'queueLeave':
        this.queueLeave(session)
        return

      case 'leaveRoom':
        if (table === undefined && this.matchmaking.queueOf(playerId) !== null) {
          this.queueLeave(session)
          return
        }
        break

      default:
        break
    }

    if (table === undefined) return this.error(session, 'NOT_IN_ROOM', '不在房间中')

    switch (msg.type) {
      case 'updateRules':
        this.dispatchTable(table, table.updateRules(playerId, msg.rules, now))
        return
      case 'setReady':
        this.dispatchTable(table, table.setReady(playerId, msg.ready, msg.rulesVersion, now))
        return
      case 'setListed':
        this.dispatchTable(table, table.setListed(playerId, msg.listed))
        return
      case 'kick':
        // kick 释放座位 → dispatchTable 末尾的 sync 依成员集合解除被踢者归属，
        // 这张桌之后的广播不会再投给他（kicked 本身在释放前送达）。
        this.dispatchTable(table, table.kick(playerId, msg.playerId, now))
        return
      case 'leaveRoom':
        this.leaveTable(table, playerId)
        return
      case 'placePlane':
      case 'fire':
        this.dispatchTable(table, table.handleGame(playerId, msg, now))
        return
      default:
        return
    }
  }

  // ============================================================ 牌桌

  private joinRoom(session: Session, roomCode: string): void {
    const playerId = session.playerId
    const current = this.tableOf(playerId)
    // 已在这张桌上：Table.join 只补发快照
    if (current !== undefined && current.roomCode === roomCode) {
      this.dispatchTable(current, current.join(playerId, this.nicknameOf(playerId), this.clock.now()))
      return
    }
    if (current !== undefined && current.phase === 'inGame') {
      return this.error(session, 'ALREADY_IN_ROOM', '对局进行中')
    }

    // 目标进不去时不要先把人从原来的桌上拉走
    const target = this.tables.get(roomCode)
    if (target === undefined || target.isClosed) return this.error(session, 'ROOM_NOT_FOUND', '房间不存在')
    const admit = target.canJoin(playerId)
    if (admit !== null) return this.error(session, admit, admit === 'BANNED' ? '已被房主移出房间' : '无法加入房间')

    if (!this.leaveCurrent(session)) return
    this.dropRoomSub(session)
    this.joinTable(target, [playerId])
  }

  /** 按列表条目加入（spec §20.6）：只认公开且可进的桌；失败时不动玩家现在的位置（RF#5）。 */
  private joinListed(session: Session, tableId: string): void {
    const playerId = session.playerId
    const target = [...this.tables.values()].find((t) => t.tableId === tableId)
    const current = this.tableOf(playerId)
    // 已经在这张桌上：只补发快照，不能走"离开再进"（房主会被自己触发让位）
    if (current !== undefined && current.tableId === tableId) {
      this.dispatchTable(current, current.join(playerId, this.nicknameOf(playerId), this.clock.now()))
      return
    }
    if (target === undefined || target.isClosed) return this.error(session, 'ROOM_NOT_FOUND', '房间不存在或已关闭')
    if (current !== undefined && current.phase === 'inGame') return this.error(session, 'ALREADY_IN_ROOM', '对局进行中')
    // listing() 为空且不是"满座/对局中"这种可理解的原因 → 桌不公开，等同不存在
    if (target.listing() === null && !(target.phase === 'inGame' || target.members.length >= target.capacity)) {
      return this.error(session, 'ROOM_NOT_FOUND', '房间不存在或已关闭')
    }
    const admit = target.canJoin(playerId)
    if (admit !== null) return this.error(session, admit, admit === 'ROOM_FULL' ? '房间已满' : '无法加入房间')

    if (!this.leaveCurrent(session)) return
    this.dropRoomSub(session)
    this.joinTable(target, [playerId])
  }

  /**
   * 离开当前的等候桌与队列；对局中返回 false 并回 ALREADY_IN_ROOM。
   * keepQueue：排队时由 Matchmaking 自己处理换队列。
   */
  private leaveCurrent(session: Session, opts: { keepQueue?: boolean } = {}): boolean {
    const playerId = session.playerId
    const table = this.tableOf(playerId)
    if (table !== undefined) {
      if (table.phase === 'inGame') {
        this.error(session, 'ALREADY_IN_ROOM', '对局进行中')
        return false
      }
      this.leaveTable(table, playerId)
    }
    if (!opts.keepQueue) {
      this.dropQueue(playerId)
    }
    return true
  }

  private leaveTable(table: Table, playerId: string): void {
    this.dispatchTable(table, table.leave(playerId, this.clock.now()))
    if (this.tableByPlayer.get(playerId) === table.roomCode) this.tableByPlayer.delete(playerId)
  }

  private queueLeave(session: Session): void {
    if (this.matchmaking.queueOf(session.playerId) === null) {
      return this.error(session, 'NOT_IN_QUEUE', '不在队列中')
    }
    this.dropQueue(session.playerId)
  }

  /** 离开队列并退还在付门票（§廿二.3：成局前退款；断线/换队/主动退都走这里）。 */
  private dropQueue(playerId: string): void {
    for (const o of this.matchmaking.leave(playerId, this.clock.now())) this.deliver(o)
    this.refundTicket(playerId)
  }

  private refundTicket(playerId: string): void {
    const ticket = this.ticketQueue.get(playerId)
    if (ticket === undefined) return
    this.ticketQueue.delete(playerId)
    this.creditTicketRefund(playerId, ticket)
  }

  /** 退款一笔（§廿二.3）：调用方已从 ticketQueue/ticketByTable 认领过这张票，防重复退 */
  private creditTicketRefund(playerId: string, ticket: TicketId): void {
    const now = this.clock.now()
    // 退款豁免净增上限（纯函数里 NET_EXEMPT）；幂等键带单调序号（评审 #1）——
    // 同一毫秒的两笔退款各退各的票，不互相吞；防重复退靠的是调用方的 Map delete
    const r = this.profiles.coin(playerId, {
      reason: 'ticket-refund',
      id: `ticket-refund:${playerId}:${now}:${++this.ticketSeq}`,
      at: now,
      delta: TICKETS[ticket].fee,
    })
    // applied=0 不推空账变（评审 #6）：否则结算页出现"+0"闪条并覆盖有效提示
    if (r.applied === 0) return
    this.sendToPlayer(playerId, { type: 'coinsChanged', delta: r.applied, reason: 'ticket-refund', balance: r.coins.balance })
  }

  /**
   * 队列成组 → 入座后的门票结算（§廿二.3）：
   * 补位局（有电脑）退款；纯真人局门票记在桌上，首局 gameOver 时按胜负发奖。
   */
  private settleQueueIntoTable(group: MatchGroup, roomCode: string): void {
    const ticket = group.key.ticket
    if (ticket === undefined || ticket === 'free') return
    if (group.playerIds.length < group.key.capacity) {
      // 补位成局：门票全额退款、不给奖励（电脑局不产金币奖励）
      for (const id of group.playerIds) {
        if (this.ticketQueue.get(id) === ticket) this.refundTicket(id)
      }
      return
    }
    for (const id of group.playerIds) {
      if (this.ticketQueue.get(id) !== ticket) continue
      this.ticketQueue.delete(id)
      this.profiles.countTicketPlay(id, this.clock.now())
    }
    this.ticketByTable.set(roomCode, { ticket, ids: [...group.playerIds] })
  }

  private newTable(
    kind: 'friend' | 'match' | 'practice',
    capacity: Capacity,
    rules: RuleSet,
    listed = false,
    preset?: PresetId,
  ): Table {
    const table = new Table({
      roomCode: this.uniqueRoomCode(),
      kind,
      capacity,
      rules,
      now: this.clock.now(),
      listed,
      tableId: this.makeTableId(),
      ...(preset !== undefined ? { preset } : {}),
      ...(this.rng ? { rng: this.rng } : {}),
    })
    this.tables.set(table.roomCode, table)
    this.membersByTable.set(table.roomCode, new Set())
    return table
  }

  /**
   * 按顺序入座；入座成功才登记归属（机器人 id 不进归属表）。
   * botSeats > 0 时补电脑座位；练习/补位都按真人入座的同一难度（spec §20.4/§20.5）。
   */
  private joinTable(table: Table, playerIds: string[], botSeats = 0, botDifficulty: BotDifficulty = 'beginner'): void {
    for (const id of playerIds) {
      const out = table.join(id, this.nicknameOf(id), this.clock.now())
      if (table.members.includes(id)) {
        this.tableByPlayer.set(id, table.roomCode)
        this.membersByTable.get(table.roomCode)?.add(id)
      }
      this.dispatchTable(table, out)
    }
    for (let i = 0; i < botSeats; i++) this.dispatchTable(table, table.addBot(botDifficulty, this.clock.now()))
  }

  private uniqueRoomCode(): string {
    for (let i = 0; i < 100; i++) {
      const code = this.makeRoomCode()
      if (!this.tables.has(code)) return code
    }
    throw new Error('无法生成唯一房间号')
  }

  private tableOf(playerId: string): Table | undefined {
    const code = this.tableByPlayer.get(playerId)
    return code === undefined ? undefined : this.tables.get(code)
  }

  private nicknameOf(playerId: string): string {
    return this.nicknames.get(playerId) ?? DEFAULT_NICKNAME
  }

  /** 让出座位的人解除归属；关闭的桌子整个删除（I4）。M5：只遍历本桌成员集合。 */
  private sync(table: Table): void {
    const members = table.isClosed ? [] : table.humanMembers
    const set = this.membersByTable.get(table.roomCode)
    if (set !== undefined) {
      for (const id of [...set]) {
        if (!members.includes(id)) {
          set.delete(id)
          if (this.tableByPlayer.get(id) === table.roomCode) this.tableByPlayer.delete(id)
        }
      }
    } else {
      // 兜底：集合丢失时退回全表扫描（不应发生，但归属错误比扫描昂贵更糟）
      for (const [id, code] of [...this.tableByPlayer]) {
        if (code === table.roomCode && !members.includes(id)) this.tableByPlayer.delete(id)
      }
    }
    if (table.isClosed) {
      this.membersByTable.delete(table.roomCode)
      if (this.tables.get(table.roomCode) === table) this.tables.delete(table.roomCode)
      // 评审 #2：门票桌首局没打完就关了（等人时全员离席/中途弃局无 gameOver）——
      // 座位快照已没意义，按入座名单全额退款（§廿二.3 中途流局退款）
      const booked = this.ticketByTable.get(table.roomCode)
      if (booked !== undefined) {
        this.ticketByTable.delete(table.roomCode)
        for (const id of booked.ids) this.creditTicketRefund(id, booked.ticket)
      }
    }
  }

  // ============================================================ 出站

  /**
   * 牌桌产生的消息只投给仍属于该桌的玩家（I4：防止旧桌的消息
   * 打进玩家正在进行的新对局）。桌子刚关闭时的告别消息例外。
   * 投递之后同步归属并清理关闭的桌子。
   */
  private dispatchTable(table: Table, out: Outbound[]): void {
    let ended = false
    for (const o of out) {
      const code = this.tableByPlayer.get(o.to)
      if (code === table.roomCode || (code === undefined && table.isClosed)) this.deliver(o)
      if (o.msg.type === 'gameOver') ended = true
    }
    // P3 计分（spec §21.2）：结算放在投递之后、sync 之前——留下的人此刻还挂在归属表上
    if (ended) this.scoreTable(table)
    this.sync(table)
    // 好友桌的入座/规则/公开/开关与建关都影响大厅列表；标脏后由 tick 合并推送
    if (table.kind === 'friend') this.roomDirty.add(table.capacity)
  }

  /**
   * 对局结束后的档案接线（spec §21.2/§21.4）：
   * - 好友桌完全不记（私密对局不进档案）
   * - 匹配桌与练习桌记战绩；有电脑参与（补位/练习）只记结果不动段位
   * - 计分局（匹配成局且无电脑）逐人 applyOutcome，并按名次 1 判胜负（P3 首版）
   * 幂等：game.id = tableId:gamesPlayed（§21.7），重放不重复加星。
   */
  private scoreTable(table: Table): void {
    if (table.kind === 'friend') return
    const game = table.lastGame
    if (game === null) return
    const now = this.clock.now()
    // 中途离开者不在快照里：不计分也不记战绩（P3 首版口径）。
    // 用 afterEngine 时刻的快照而非现读座位——match 桌有人离开会立刻关桌清座。
    const humans = game.humans
    if (humans.length === 0) return
    const withBots = table.kind === 'practice' || game.result.botIds.length > 0
    const mmrOf = new Map<string, number>()
    for (const id of humans) mmrOf.set(id, this.profiles.get(id, this.nicknameOf(id), now).rank.mmr)
    let sum = 0
    for (const m of mmrOf.values()) sum += m

    // 先记全部账（战绩 + 完成局 + 门票胜负），再统一推送——
    // profile 必须带最终余额，客户端只认档案里的 coins 字段
    type Pending = { rankChanged?: ServerMessage; coinMsgs: ServerMessage[] }
    const pend = new Map<string, Pending>()

    for (const id of humans) {
      const entry = game.result.ranking.find((r) => r.playerId === id)
      if (entry === undefined) continue
      const mine = mmrOf.get(id)!
      // 对手基准：同桌其他真人 MMR 均值；单人参照自己（Elo 差 0）
      const opponentMmr = mmrOf.size > 1 ? Math.round((sum - mine) / (mmrOf.size - 1)) : mine
      const res = this.profiles.record(id, {
        id: game.id,
        at: now,
        mode: game.mode,
        preset: game.preset ?? 'standard',
        capacity: table.capacity,
        rank: entry.rank,
        hits: entry.hits,
        withBots,
        opponentMmr,
      })
      const p: Pending = { coinMsgs: [] }
      if (!withBots) {
        p.rankChanged = {
          type: 'rankChanged',
          delta: res.delta,
          rank: { tier: res.profile.rank.tier, stars: res.profile.rank.stars, lossStreak: res.profile.rank.lossStreak },
          reason: 'scoring',
        }
      }
      // P4 完成对局金币（§廿二.2）：真实打完就算（电脑局也算），日限 20 局与净增封顶在纯函数里
      const g = this.profiles.coin(id, { reason: 'game', id: `game:${game.id}:${id}`, at: now, delta: COIN.GAME_GRANT })
      if (g.applied !== 0) p.coinMsgs.push({ type: 'coinsChanged', delta: g.applied, reason: 'game', balance: g.coins.balance, ...(g.capped ? { capped: true } : {}) })
      pend.set(id, p)
    }

    // P4 门票结算（§廿二.3）：门票桌首局按胜负——胜者拿固定奖励，败者只损失已付门票。
    // 首局即结算：再来一局不重复收门票也不重复发奖；rematch 局是普通免费局。
    const booked = this.ticketByTable.get(table.roomCode)
    if (booked !== undefined) {
      this.ticketByTable.delete(table.roomCode)
      const reward = TICKETS[booked.ticket].reward
      for (const id of humans) {
        const entry = game.result.ranking.find((r) => r.playerId === id)
        if (entry === undefined || entry.rank !== 1) continue
        const r = this.profiles.coin(id, { reason: 'ticket-win', id: `ticket-win:${game.id}:${id}`, at: now, delta: reward })
        if (r.applied !== 0) {
          pend.get(id)?.coinMsgs.push({ type: 'coinsChanged', delta: r.applied, reason: 'ticket-win', balance: r.coins.balance, ...(r.capped ? { capped: true } : {}) })
        }
      }
    }

    for (const id of humans) {
      const p = pend.get(id)
      if (p === undefined) continue
      this.sendToPlayer(id, { type: 'profile', profile: this.profiles.view(id, this.nicknameOf(id), now) })
      if (p.rankChanged !== undefined) this.sendToPlayer(id, p.rankChanged)
      for (const m of p.coinMsgs) this.sendToPlayer(id, m)
    }
  }

  /** 向某玩家当前会话单点投递（无会话则丢弃——档案改动不丢，上线时补发）。 */
  private sendToPlayer(playerId: string, msg: ServerMessage): void {
    const sid = this.sessionByPlayer.get(playerId)
    if (sid === undefined) return
    this.sessions.get(sid)?.send(msg)
  }

  private deliver(o: Outbound): void {
    const sid = this.sessionByPlayer.get(o.to)
    const session = sid === undefined ? undefined : this.sessions.get(sid)
    session?.send(o.msg)
  }

  private error(session: Session, code: ErrorCode, message: string): void {
    session.send({ type: 'error', code, message })
  }

  // ============================================================ 大厅列表（spec §20.6）

  /** 专区快照：同人数且 listing() 非空的桌，在座多者在前、同数新建者在前，截断到上限。 */
  private roomSnapshot(capacity: Capacity): RoomListEntry[] {
    const entries: RoomListEntry[] = []
    for (const table of this.tables.values()) {
      if (table.capacity !== capacity) continue
      const e = table.listing()
      if (e !== null) entries.push(e)
    }
    entries.sort((a, b) => b.seated - a.seated || b.createdAt - a.createdAt)
    return entries.length > ROOM_LIST_MAX ? entries.slice(0, ROOM_LIST_MAX) : entries
  }

  /**
   * 合并推送：脏专区距上次推送 ≥ ROOM_LIST_MIN_INTERVAL_MS 才检查内容；
   * 内容没变不算脏（直接清掉），变了才推送并记时刻；没到间隔保持脏，下次再试。
   */
  private pushRoomLists(now: number): void {
    if (this.roomDirty.size === 0) return
    for (const capacity of [...this.roomDirty]) {
      const prev = this.roomLast.get(capacity)
      if (prev !== undefined && now - prev.at < ROOM_LIST_MIN_INTERVAL_MS) continue
      const entries = this.roomSnapshot(capacity)
      const json = JSON.stringify(entries)
      this.roomDirty.delete(capacity)
      if (prev !== undefined && prev.json === json) continue
      this.roomLast.set(capacity, { json, at: now })
      for (const [sid, sub] of this.roomSubs) {
        if (sub !== capacity) continue
        this.sessions.get(sid)?.send({ type: 'roomList', capacity, entries })
      }
    }
  }

  /** 进入桌或队列即视为离开大厅：退订该会话（列表页已不在前台）。 */
  private dropRoomSub(session: Session): void {
    this.roomSubs.delete(session.sessionId)
  }

  // ============================================================ tick

  /**
   * 优雅停机（spec §廿三.1.1，P4 已知限制 1 的根治）：把在付的全部门票清退——
   * 排队中的走 refundTicket，已记桌的按入座名单退（与 sync() 关桌兜底同一路径）。
   * 幂等：退过的票 Map 里已删，重复调用是 no-op。在途对局不恢复（§九 既定）。
   * 调用方负责随后的 profiles.flush() 与断连。
   */
  shutdown(): void {
    for (const playerId of [...this.ticketQueue.keys()]) this.refundTicket(playerId)
    for (const [roomCode, booked] of [...this.ticketByTable]) {
      this.ticketByTable.delete(roomCode)
      for (const id of booked.ids) this.creditTicketRefund(id, booked.ticket)
    }
  }

  tick(): void {
    const now = this.clock.now()
    this.resetSeasons(now)
    for (const table of [...this.tables.values()]) this.dispatchTable(table, table.tick(now))
    const { out, groups } = this.matchmaking.tick(now)
    for (const o of out) this.deliver(o)
    for (const g of groups) {
      // 补位成组（spec §20.5）：真人先入座，缺的座位按档位难度补电脑
      const table = this.newTable('match', g.key.capacity, PRESETS[g.key.preset], false, g.key.preset)
      this.joinTable(table, g.playerIds, g.botSeats, g.key.preset)
      // P4 门票结算（§廿二.3）：补位局退款；纯真人满局记在桌上，首局按胜负发奖
      this.settleQueueIntoTable(g, table.roomCode)
    }
    this.pushRoomLists(now)
  }

  /**
   * 跨季重置（spec §21.3）：tick 里检测赛季编号变化，全部档案 resetSeason；
   * 在线玩家推 rankChanged(season-reset) + 新档案，让段位卡自己刷新。
   */
  private resetSeasons(now: number): void {
    const touched = this.profiles.resetSeasonAll(now)
    for (const id of touched) {
      this.sendToPlayer(id, { type: 'profile', profile: this.profiles.view(id, this.nicknameOf(id), now) })
      const p = this.profiles.get(id, '', now)
      this.sendToPlayer(id, {
        type: 'rankChanged',
        delta: 0,
        rank: { tier: p.rank.tier, stars: p.rank.stars, lossStreak: p.rank.lossStreak },
        reason: 'season-reset',
      })
    }
  }

  getTable(roomCode: string): Table | undefined {
    return this.tables.get(roomCode)
  }
}
