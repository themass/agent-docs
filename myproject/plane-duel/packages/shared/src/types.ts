/**
 * 协议与领域类型。对应 spec §九（协议）与 §十（数据模型）。
 *
 * 硬约束（见 spec §八）：对方飞机的机头坐标任何时刻都不得下发到对手。
 * 因此所有"对手视角"的类型里都不允许出现 planes。
 */

import type { Capacity, PresetId, RuleSet } from './ruleset'
import type { CoinEntry, CoinReason, DailyState, TicketId } from './coins'

// ---------- 基础 ----------

export type Cell = { row: number; col: number }

/** 一架 3×3 飞机。机身 8 格由 head 推导，不落库。 */
export type Plane = { id: string; head: Cell }

export type ShotResult = 'miss' | 'body' | 'head'

/** P3 道具。P0 协议里存在但服务端返回 UNSUPPORTED。 */
export type ItemId = 'scan' | 'doubleShot' | 'radar' | 'shield' | 'relocate'

/** @deprecated P0 */
export type Phase = 'waiting' | 'placing' | 'playing' | 'finished' | 'paused'

export type Mode = 'duel' | 'melee'
export type TablePhase = 'waiting' | 'inGame'
export type GamePhase = 'placing' | 'playing' | 'paused' | 'finished'

/** 摆放超时自动落子，不判负，因此没有 placementTimeout。 */
export type GameOverReason = 'head' | 'allPlanes' | 'forfeit' | 'lastStanding'

export type ShotRecord = { row: number; col: number; result: ShotResult }

// ---------- 牌桌与对局视图 ----------

/** 机器人 playerId 的前缀。真人 auth 的 playerId 不得以此开头。 */
export const BOT_ID_PREFIX = 'bot:'

export type TableKind = 'friend' | 'match' | 'practice'
/** 机器人难度即规则预设 id，仅作类型别名，无运行时值。 */
export type BotDifficulty = PresetId

export type SeatView = {
  seat: number
  playerId: string
  nickname: string
  ready: boolean
  connected: boolean
  bot: boolean
}
export type RankEntry = { playerId: string; rank: number; eliminatedRound: number | null; hits: number }
export type GameResult = { ranking: RankEntry[]; reason: GameOverReason }
export type TableResult = GameResult & { botIds: string[] }
export type TableView = {
  roomCode: string
  kind: TableKind
  capacity: Capacity
  rules: RuleSet
  rulesVersion: number
  listed: boolean
  hostId: string | null
  phase: TablePhase
  seats: (SeatView | null)[]
  lastResult: TableResult | null
}
export type RoomListEntry = {
  tableId: string
  capacity: Capacity
  rules: RuleSet
  hostNickname: string
  seated: number
  seats: ({ seat: number; nickname: string } | null)[]
  createdAt: number
}
// ---------- P3 账号·段位·战绩·排行榜（spec §廿一） ----------

export type GameSummary = {
  /** 幂等键：tableId:gamesPlayed（spec §21.7） */
  id: string
  at: number
  mode: Mode
  preset: PresetId
  capacity: Capacity
  /** 我的最终名次（1 起） */
  rank: number
  /** 有电脑参与的局（练习/补位），一律不计段位 */
  withBots: boolean
  win: boolean
  hits: number
  /** 星数变化：+1/0/−1；不计分段为 0 */
  delta: number
}

export type RankSummary = { tier: number; stars: number; lossStreak: number }

export type ProfileView = {
  nickname: string
  /** 显示壳：段位级数 + 星数；元帅用星数排名 */
  rank: RankSummary
  /** 赛季编号（§21.3） */
  season: number
  stats: {
    wins: number
    losses: number
    totalHits: number
    /** 历史最高段位（tier, stars 当时的显示值） */
    bestTier: number
    bestStars: number
    /** 当前连胜 */
    streak: number
    scoringGames: number
  }
  recent: GameSummary[]
  /** P4（§廿二.6）：余额内嵌档案；明细走 coins 请求 */
  coins: number
}

export type RankListEntry = {
  /** 1 起 */
  pos: number
  nickname: string
  tier: number
  stars: number
  wins: number
}

export type TargetShot = { targetId: string; row: number; col: number; result: ShotResult; planeId: string }
export type IncomingShot = { by: string; row: number; col: number; result: ShotResult; planeId: string }
export type OtherPlayerView = {
  playerId: string
  connected: boolean
  alive: boolean
  planesDestroyed: number
  submitted: boolean
}
export type GameView = {
  mode: Mode
  phase: GamePhase
  deadlineAt: number | null
  /** duel：当前开炮者；melee：null */
  turn: string | null
  /** melee：当前轮次（从 1 起）；duel：null */
  round: number | null
  you: {
    planes: Cell[]
    planesDestroyed: number
    alive: boolean
    shots: TargetShot[]
    incoming: IncomingShot[]
    submitted: boolean
    pendingShot: Cell | null
  }
  others: OtherPlayerView[]
}

// ---------- 客户端 → 服务端 ----------

export type ClientMessage =
  | { type: 'auth'; playerId: string; token?: string; nickname?: string }
  | { type: 'setNickname'; nickname: string }
  | { type: 'createRoom'; capacity: Capacity; rules: RuleSet; listed: boolean }
  | { type: 'joinRoom'; roomCode: string }
  | { type: 'updateRules'; rules: RuleSet }
  | { type: 'setReady'; ready: boolean; rulesVersion: number }
  | { type: 'queueJoin'; capacity: Capacity; preset: PresetId; ticket?: TicketId }
  | { type: 'queueLeave' }
  | { type: 'createPractice'; capacity: Capacity; preset: PresetId }
  | { type: 'kick'; playerId: string }
  | { type: 'setListed'; listed: boolean }
  | { type: 'roomListSubscribe'; capacity: Capacity }
  | { type: 'roomListUnsubscribe' }
  | { type: 'joinListed'; tableId: string }
  | { type: 'placePlane'; planes: Cell[] }
  | { type: 'fire'; row: number; col: number }
  | { type: 'useItem'; itemId: ItemId }
  | { type: 'leaveRoom' }
  // P3（spec §21.6）
  | { type: 'profileRequest' }
  | { type: 'rankListRequest' }
  // P4（spec §廿二.6）
  | { type: 'coinRequest' }
  | { type: 'adRewardRequest'; slot: 'coins' }

export type ClientMessageType = ClientMessage['type']

// ---------- 服务端 → 客户端 ----------

export type ServerMessage =
  | { type: 'ready'; playerId: string; token: string; nickname: string }
  | { type: 'tableState'; table: TableView }
  | { type: 'queueStatus'; capacity: Capacity; preset: PresetId; waiting: number; botFillAt: number | null; humansNeeded: number; ticket?: TicketId }
  | { type: 'queueTimeout' }
  | { type: 'roomList'; capacity: Capacity; entries: RoomListEntry[] }
  | { type: 'kicked'; roomCode: string }
  | { type: 'playerOut'; playerId: string; round: number }
  | { type: 'phaseChanged'; phase: GamePhase; deadlineAt: number | null; turn?: string; round?: number }
  | { type: 'planeAccepted'; planes: Cell[] }
  /** duel */
  | { type: 'shotResult'; by: string; row: number; col: number; result: ShotResult; planeId: string; nextTurn: string }
  /** melee，无坐标 */
  | { type: 'submitted'; playerId: string; round: number }
  /** melee，按人私有 */
  | {
      type: 'roundResult'
      round: number
      shots: TargetShot[]
      incoming: IncomingShot[]
      destroyed: { playerId: string; planesDestroyed: number }[]
      eliminated: string[]
    }
  /** duel */
  | { type: 'planeDestroyed'; ownerId: string; planeId: string }
  | { type: 'presence'; playerId: string; connected: boolean }
  | { type: 'gameOver'; result: GameResult }
  | { type: 'roomClosed' }
  | { type: 'state'; table: TableView; game: GameView | null }
  | { type: 'error'; code: ErrorCode; message: string }
  // P3（spec §21.6）
  | { type: 'profile'; profile: ProfileView }
  /** 计分局结算后推给本人；收到即刷新段位卡 */
  | { type: 'rankChanged'; delta: number; rank: RankSummary; reason: 'scoring' | 'season-reset' }
  | { type: 'rankList'; season: number; entries: RankListEntry[] }
  // P4（spec §廿二.6）
  | { type: 'coins'; balance: number; ledger: CoinEntry[]; daily: DailyState }
  /** 每次加/扣钱即时推；balance 是推后的新余额 */
  | { type: 'coinsChanged'; delta: number; reason: CoinReason; balance: number; capped?: boolean }

export type ServerMessageType = ServerMessage['type']

/**
 * 服务端错误码。新增时同步更新 error 类型，两者一起由测试锁定。
 */
export type ErrorCode =
  | 'BAD_JSON'
  | 'BAD_SHAPE'
  | 'UNKNOWN_TYPE'
  | 'UNSUPPORTED'
  | 'NOT_AUTHED'
  | 'NOT_IN_ROOM'
  | 'ROOM_NOT_FOUND'
  | 'ROOM_FULL'
  | 'WRONG_PHASE'
  | 'NOT_YOUR_TURN'
  | 'REPEAT_SHOT'
  | 'OUT_OF_RANGE'
  | 'INVALID_PLACEMENT'
  | 'PAUSED'
  | 'ALREADY_IN_ROOM'
  | 'BAD_TOKEN'
  | 'NOT_HOST'
  | 'ROOM_IN_GAME'
  | 'BAD_RULES'
  | 'NOT_IN_QUEUE'
  | 'TARGET_NOT_FOUND'
  | 'TARGET_READY'
  | 'BANNED'
  | 'STALE_RULES'
  // P4（spec §廿二）
  | 'NOT_ENOUGH_COINS'
  | 'DAILY_TICKET_LIMIT'
  | 'AD_LIMIT'
