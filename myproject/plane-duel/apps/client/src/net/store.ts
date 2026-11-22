/**
 * 响应式状态仓库（协议 v3）。apply 是纯归约：消息进、状态改，不碰网络，因此可以单测。
 *
 * 开局时服务端会先发 tableState、再发 state（牌桌 + 对局视图）。state 是权威快照，
 * 整体替换 table 与 game；其余消息只对 game 做增量维护。
 */

import { reactive } from 'vue'
import type {
  Capacity,
  CoinEntry,
  CoinReason,
  DailyState,
  GameView,
  PresetId,
  ProfileView,
  RankListEntry,
  RoomListEntry,
  ServerMessage,
  TableView,
  TicketId,
} from '@plane-duel/shared'

export type GameState = {
  playerId: string | null
  nickname: string
  table: TableView | null
  /** 由 phaseChanged/shotResult/roundResult/submitted/presence 增量维护，由 state 整体替换 */
  game: GameView | null
  queue: { capacity: Capacity; preset: PresetId; waiting: number; botFillAt: number | null; humansNeeded: number; ticket?: TicketId } | null
  queueTimedOut: boolean
  /** 大厅公开列表（当前订阅的专区）；null = 尚未收到快照 */
  roomList: { capacity: Capacity; entries: RoomListEntry[] } | null
  /** 被房主踢出；进新牌桌时清除 */
  kicked: boolean
  /** 结算页是否已关闭（table.lastResult 变化时重置为 false） */
  resultDismissed: boolean
  roomClosed: boolean
  error: string | null
  // ---------- P3（spec §21.6） ----------
  /** 本人档案；auth 起服务端自动推送，v3 服务端没有它则为 null */
  profile: ProfileView | null
  /** 段位榜缓存（at 用于 30 秒自刷判定，§21.5） */
  rankList: { season: number; entries: RankListEntry[]; at: number } | null
  /** 计分局结算后的星数变化提示；新一局的 tableState 到达时清除 */
  rankFlash: { delta: number; tier: number; stars: number } | null
  // ---------- P4（spec §廿二.6） ----------
  /** 金币余额（profile.coins 镜像 + coinsChanged 增量，两路都会更新） */
  coins: number
  /** 账本明细缓存（coinRequest 响应）；null = 尚未拉取 */
  coinLedger: { balance: number; entries: CoinEntry[]; daily: DailyState; at: number } | null
  /** 结算页金币提示（完成局 +5 / 门票 +80 等）；新一局清除 */
  coinFlash: { delta: number; reason: CoinReason } | null
}

const initial = (): GameState => ({
  playerId: null,
  nickname: '',
  table: null,
  game: null,
  queue: null,
  queueTimedOut: false,
  roomList: null,
  kicked: false,
  resultDismissed: false,
  roomClosed: false,
  error: null,
  profile: null,
  rankList: null,
  rankFlash: null,
  coins: 0,
  coinLedger: null,
  coinFlash: null,
})

const ERROR_TEXT: Record<string, string> = {
  ROOM_NOT_FOUND: '房间不存在',
  ROOM_FULL: '房间已满',
  REPEAT_SHOT: '这一格已经打过了',
  INVALID_PLACEMENT: '飞机必须完整放在棋盘内',
  PAUSED: '对手掉线中，请稍候',
  ALREADY_IN_ROOM: '对局进行中，不能再开新局',
  BAD_TOKEN: '身份校验失败，请刷新页面',
  NOT_HOST: '只有房主可以修改规则',
  ROOM_IN_GAME: '对局进行中',
  NOT_IN_QUEUE: '你不在排队中',
  BAD_RULES: '规则不合法',
  OUT_OF_RANGE: '超出棋盘范围',
  WRONG_PHASE: '现在不能这样操作',
  NOT_IN_ROOM: '你不在房间中',
  TARGET_NOT_FOUND: '该玩家不在房间中',
  TARGET_READY: '对方已准备，不能移出',
  BANNED: '你已被移出该房间，不能再加入',
  STALE_RULES: '房主刚修改了规则，请确认后再准备',
  NOT_ENOUGH_COINS: '金币不足，先打一局攒点吧',
  DAILY_TICKET_LIMIT: '今天门票局次数已用完',
  AD_LIMIT: '今天的广告奖励次数已用完',
}

const resultKey = (t: TableView | null): string => JSON.stringify(t?.lastResult ?? null)

export function createGameStore() {
  const state = reactive<GameState>(initial())

  function errorText(code: string): string {
    if (code === 'NOT_YOUR_TURN') return state.game?.mode === 'melee' ? '本轮你已开过炮' : '还没轮到你'
    return ERROR_TEXT[code] ?? '操作失败'
  }

  function apply(m: ServerMessage): void {
    switch (m.type) {
      case 'ready':
        state.playerId = m.playerId
        state.nickname = m.nickname
        return
      case 'tableState': {
        const prev = state.table
        // 内容相同的 lastResult（每次解析出的都是新对象）不算变化
        if (resultKey(prev) !== resultKey(m.table)) state.resultDismissed = false
        // 换了牌桌：旧牌桌的对局视图不再适用
        if (prev && prev.roomCode !== m.table.roomCode) state.game = null
        // 新一局开始：上一局的升星/金币提示不再适用
        if (m.table.phase === 'inGame') {
          state.rankFlash = null
          state.coinFlash = null
        }
        state.table = m.table
        state.queue = null
        state.queueTimedOut = false
        state.roomClosed = false
        state.kicked = false
        return
      }
      case 'state':
        if (resultKey(state.table) !== resultKey(m.table)) state.resultDismissed = false
        state.table = m.table
        state.game = m.game
        state.queue = null
        state.queueTimedOut = false
        state.roomClosed = false
        state.kicked = false
        return
      case 'queueStatus':
        state.queue = {
          capacity: m.capacity,
          preset: m.preset,
          waiting: m.waiting,
          botFillAt: m.botFillAt,
          humansNeeded: m.humansNeeded,
          // v4 服务端不带 ticket；新服务端只在客户端指定了门票档时回显
          ...(m.ticket !== undefined ? { ticket: m.ticket } : {}),
        }
        state.queueTimedOut = false
        return
      case 'queueTimeout':
        state.queue = null
        state.queueTimedOut = true
        return
      case 'roomList':
        state.roomList = { capacity: m.capacity, entries: m.entries }
        return
      case 'kicked':
        // 服务端已释放座位：本地回大厅，并留下"被移出"的提示
        resetToLobby()
        state.kicked = true
        state.error = '你已被房主移出房间'
        return
      case 'playerOut': {
        // 中途出局（掉线判负/离开）：立即标死并清掉"已开炮"，避免卡在等待态
        const g = state.game
        if (!g) return
        const o = g.others.find((x) => x.playerId === m.playerId)
        if (o) {
          o.alive = false
          o.submitted = false
        }
        return
      }
      case 'phaseChanged': {
        const g = state.game
        if (!g) return
        g.phase = m.phase
        g.deadlineAt = m.deadlineAt
        if (m.turn !== undefined) g.turn = m.turn
        if (m.round !== undefined) g.round = m.round
        return
      }
      case 'planeAccepted':
        if (state.game) state.game.you.planes = m.planes
        return
      case 'shotResult': {
        const g = state.game
        if (!g) return
        if (m.by === state.playerId) {
          const targetId = g.others[0]?.playerId
          if (targetId !== undefined) {
            g.you.shots.push({ targetId, row: m.row, col: m.col, result: m.result, planeId: m.planeId })
          }
        } else {
          g.you.incoming.push({ by: m.by, row: m.row, col: m.col, result: m.result, planeId: m.planeId })
        }
        g.turn = m.nextTurn
        return
      }
      case 'planeDestroyed': {
        const g = state.game
        if (!g) return
        if (m.ownerId === state.playerId) g.you.planesDestroyed += 1
        else {
          const o = g.others.find((x) => x.playerId === m.ownerId)
          if (o) o.planesDestroyed += 1
        }
        return
      }
      case 'submitted': {
        // 服务端把"谁提交了"广播给全桌，包括自己——自己的那条写进 you，
        // 这样"已开炮"状态不依赖本地乐观标记，刷新/重连后仍然正确（M1）。
        if (state.game) {
          if (m.playerId === state.playerId) state.game.you.submitted = true
          const o = state.game.others.find((x) => x.playerId === m.playerId)
          if (o) o.submitted = true
        }
        return
      }
      case 'roundResult': {
        const g = state.game
        if (!g) return
        g.you.shots.push(...m.shots)
        g.you.incoming.push(...m.incoming)
        for (const d of m.destroyed) {
          if (d.playerId === state.playerId) g.you.planesDestroyed = d.planesDestroyed
          else {
            const o = g.others.find((x) => x.playerId === d.playerId)
            if (o) o.planesDestroyed = d.planesDestroyed
          }
        }
        for (const id of m.eliminated) {
          if (id === state.playerId) g.you.alive = false
          else {
            const o = g.others.find((x) => x.playerId === id)
            if (o) o.alive = false
          }
        }
        for (const o of g.others) o.submitted = false
        // 整轮结算 = 新一轮开始：本人的"已开炮"同样清零，
        // 否则 canFire 永远为 false，第二轮起再也打不出去（评审 B1）
        g.you.submitted = false
        return
      }
      case 'presence': {
        const o = state.game?.others.find((x) => x.playerId === m.playerId)
        if (o) o.connected = m.connected
        const seat = state.table?.seats.find((x) => x?.playerId === m.playerId)
        if (seat) seat.connected = m.connected
        return
      }
      case 'gameOver':
        // 排名随后由 tableState.lastResult 带来；这里只收尾对局视图
        if (state.game) {
          state.game.phase = 'finished'
          state.game.deadlineAt = null
        }
        return
      case 'roomClosed':
        state.roomClosed = true
        return
      case 'profile':
        state.profile = m.profile
        // 档案是余额的权威来源（coinsChanged 只是增量提示）
        state.coins = m.profile.coins
        return
      case 'rankChanged': {
        // 档案可能紧随其后（服务端顺序：profile → rankChanged）；这里只记提示，
        // 段位数值以 profile 为准，rankChanged 负责"这局发生了什么"
        if (m.reason === 'scoring') {
          state.rankFlash = { delta: m.delta, tier: m.rank.tier, stars: m.rank.stars }
        } else {
          // 赛季重置：直接提示文案走 error toast 之外的段位卡，提示后不常驻
          state.rankFlash = null
        }
        return
      }
      case 'rankList':
        state.rankList = { season: m.season, entries: m.entries, at: Date.now() }
        return
      // ---------- P4（spec §廿二.6） ----------
      case 'coins':
        state.coins = m.balance
        state.coinLedger = { balance: m.balance, entries: m.ledger, daily: m.daily, at: Date.now() }
        return
      case 'coinsChanged':
        // 增量推余额；档案里的 coins 稍后由 profile 消息带来，两路都写同一个值
        state.coins = m.balance
        // 账本页开着时同步余额，否则页头与大厅金币条互相矛盾（评审 #7）；
        // 当日配额计数仍以快照为准，靠"刷新"按钮重拉
        if (state.coinLedger !== null) state.coinLedger.balance = m.balance
        if (m.reason === 'ticket-win' || m.reason === 'game' || m.reason === 'ticket-fee' || m.reason === 'ticket-refund') {
          state.coinFlash = { delta: m.delta, reason: m.reason }
        }
        return
      case 'error':
        state.error = errorText(m.code)
        return
    }
  }

  /** 离开等待中的牌桌时服务端不回消息，客户端自行复位。 */
  function resetToLobby() {
    // P3/P4：档案、榜单与金币跟着玩家走，不随牌桌复位（否则回大厅卡片瞬间空白）
    const { playerId, nickname, profile, rankList, coins, coinLedger } = state
    Object.assign(state, initial())
    state.playerId = playerId
    state.nickname = nickname
    state.profile = profile
    state.rankList = rankList
    state.coins = coins
    state.coinLedger = coinLedger
  }

  /** 关闭结算页，回到等候室 */
  function dismissResult() {
    state.resultDismissed = true
  }

  return { state, apply, resetToLobby, dismissResult }
}

export type GameStore = ReturnType<typeof createGameStore>
