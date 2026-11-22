/**
 * WebSocket 连接：**Java 服务端（vvv-game）v1 协议适配层**。
 *
 * 对外仍是旧的 SocketHandle / send(ClientMessage) / onMessage(ServerMessage) 接口，
 * 视图层与 store 零改动；线上一律换成 docs/game/protocol.md 的信封协议：
 *
 *   → {v:1, cmd, seq, data}    ← {v:1, evt, seq, ref, data}
 *
 * 鉴权：浏览器 WebSocket 设不了 HTTP 头，握手用 `?vpnToken=` 查询参数
 * （GameHandshakeInterceptor 支持的两条路径之一）。token 来源优先级：
 * localStorage（正式登录页 login() 写入）→ 构建期 VITE_VPN_TOKEN（原生壳调试）。
 * 产品要求 token 绝不出现在 URL：地址栏 ?vpnToken= 一律不读。
 *
 * 身份：平台 userId（字符串形态即 playerId），不再有 auth/ready/token 往返——
 * 首次收到 profile.now 时合成一条 ready 喂给 store。
 *
 * 自动重连（1s 起指数退避到 8s）。Java 侧顶号用普通 1000 关闭，不区分 superseded。
 */

import { ref, type Ref } from 'vue'
import {
  sanitizeNickname,
  type ClientMessage,
  type ErrorCode,
  type ServerMessage,
  type TableView,
} from '@plane-duel/shared'
import { generateNickname } from '../nickname-gen'
import { getToken } from './auth'

export type SocketStatus = 'connecting' | 'open' | 'closed' | 'superseded'

export type SocketHandle = {
  send(msg: ClientMessage): void
  onMessage(cb: (m: ServerMessage) => void): void
  close(): void
  status: Ref<SocketStatus>
}

/** 兼容保留：旧版客户端身份；Java 版身份 = 平台 token 换出的 userId。 */
export function getPlayerId(): string {
  const KEY = 'plane-duel:playerId'
  let id = localStorage.getItem(KEY)
  if (!id) {
    id = crypto.randomUUID()
    localStorage.setItem(KEY, id)
  }
  return id
}

/** 昵称存 localStorage；没有（或不合法）就随机生成一个并保存。 */
export function getNickname(): string {
  const KEY = 'plane-duel:nickname'
  const stored = localStorage.getItem(KEY)
  const nick = sanitizeNickname(stored, '')
  if (nick) return nick
  const fresh = generateNickname()
  localStorage.setItem(KEY, fresh)
  return fresh
}

export function saveNickname(nickname: string): void {
  localStorage.setItem('plane-duel:nickname', nickname)
}

/**
 * 平台 token（Vpn-Token）。正式来源是登录页 login() 写入的 localStorage
 * （auth.ts，键 plane-duel:vpnToken）；VITE_VPN_TOKEN 只在原生壳调试时兜底。
 * 地址栏 ?vpnToken= 一律不读（产品要求 token 不出现在 URL：会进浏览历史 /
 * Referer / 服务器访问日志）。
 */
export function getVpnToken(): string {
  return getToken() || import.meta.env.VITE_VPN_TOKEN || ''
}

export function defaultWsUrl(): string {
  if (import.meta.env.VITE_WS_URL) return import.meta.env.VITE_WS_URL
  // 默认线上入口（nginx 的 /vvv 前缀 + WS Upgrade 块，deploy/nginx/snippets-vpn-routes.conf）
  return 'wss://api.ok123find.top/vvv/api/game/ws'
}

// ================================================================ 命令映射
// 旧 {type} → v1 {cmd, data}。data 形状对齐 GameHub 各命令的解析口径。

type Json = Record<string, unknown>

function toCmd(m: ClientMessage): { cmd: string; data: Json } | null {
  switch (m.type) {
    case 'auth':
      return null // Java 侧握手即鉴权，没有 auth 命令
    case 'setNickname':
      return { cmd: 'nickname.set', data: { nickname: m.nickname } }
    case 'createRoom':
      return { cmd: 'room.create', data: { capacity: m.capacity, rules: m.rules, listed: m.listed } }
    case 'joinRoom':
      return { cmd: 'room.join', data: { roomCode: m.roomCode } }
    case 'joinListed':
      // GameHub.joinRoomMaybeListed：room.join 带 tableId 走列表语义
      return { cmd: 'room.join', data: { tableId: m.tableId } }
    case 'updateRules':
      return { cmd: 'room.rules', data: { rules: m.rules } }
    case 'setReady':
      return { cmd: 'room.ready', data: { ready: m.ready, rulesVersion: m.rulesVersion } }
    case 'queueJoin':
      return {
        cmd: 'queue.join',
        data: m.ticket ? { capacity: m.capacity, preset: m.preset, ticket: m.ticket } : { capacity: m.capacity, preset: m.preset },
      }
    case 'queueLeave':
      return { cmd: 'queue.leave', data: {} }
    case 'createPractice':
      return { cmd: 'practice.create', data: { capacity: m.capacity, preset: m.preset } }
    case 'kick':
      // Java 同时收 playerId 与 seat，沿用 playerId
      return { cmd: 'room.kick', data: { playerId: m.playerId } }
    case 'setListed':
      return { cmd: 'room.listed', data: { listed: m.listed } }
    case 'roomListSubscribe':
      return { cmd: 'room.list', data: { subscribe: true, capacity: m.capacity } }
    case 'roomListUnsubscribe':
      return { cmd: 'room.list', data: { subscribe: false } }
    case 'placePlane':
      return { cmd: 'game.place', data: { planes: m.planes } }
    case 'fire':
      return { cmd: 'game.fire', data: { row: m.row, col: m.col } }
    case 'useItem':
      // Java 现网一律回 UNSUPPORTED（道具未开放），仍映射保持命令面完整
      return { cmd: 'game.item', data: { itemId: m.itemId } }
    case 'leaveRoom':
      return { cmd: 'room.leave', data: {} }
    case 'profileRequest':
      return { cmd: 'profile.get', data: {} }
    case 'rankListRequest':
      return { cmd: 'rank.list', data: {} }
    case 'coinRequest':
      return { cmd: 'coins.ledger', data: {} }
    case 'adRewardRequest':
      return { cmd: 'coin.adReward', data: { adRef: m.slot } }
  }
}

// ================================================================ 事件映射
// v1 evt → 旧 ServerMessage（一条事件可能展开成多条，如 profile.now → ready+profile）。

type AnyJson = Record<string, any>

function mapErrorCode(code: string, message: string): ErrorCode {
  // protocol.md 的有意收敛：旧码表里没有的按语义映射回旧词表，视图文案不用改
  if (code === 'UNKNOWN_CMD') return 'UNKNOWN_TYPE'
  if (code === 'BALANCE_LOW') return 'NOT_ENOUGH_COINS'
  if (code === 'QUOTA_EXCEEDED') return message.includes('广告') ? 'AD_LIMIT' : 'DAILY_TICKET_LIMIT'
  return code as ErrorCode
}

/** auth 是每次连接的闭包状态：ready 只在该连接首见 profile.now 时合成一次。 */
function fromEvt(evt: string, d: AnyJson, auth: { authed: boolean }): ServerMessage[] {
  switch (evt) {
    case 'profile.now': {
      const out: ServerMessage[] = []
      const playerId = String(d.userId ?? '')
      if (!auth.authed && playerId) {
        // Java 没有 ready：首见档案即"认证完成"，合成一条喂 store（playerId=平台 userId）
        auth.authed = true
        out.push({ type: 'ready', playerId, token: '', nickname: d.nickname ?? '' })
      }
      const rank = d.rank ?? { tier: 0, stars: 0, lossStreak: 0 }
      out.push({
        type: 'profile',
        profile: {
          nickname: d.nickname ?? '',
          rank: { tier: rank.tier, stars: rank.stars, lossStreak: rank.lossStreak },
          season: d.season ?? 0,
          stats: {
            wins: rank.wins ?? 0,
            losses: rank.losses ?? 0,
            totalHits: rank.totalHits ?? 0,
            bestTier: rank.bestTier ?? 0,
            bestStars: rank.bestStars ?? 0,
            streak: rank.streak ?? 0,
            scoringGames: rank.scoringGames ?? 0,
          },
          // WS 的 profile.now 不带 recent（对局历史走 HTTP /matches/recent），视图按空列表渲染
          recent: [],
          coins: d.coins?.balance ?? 0,
        },
      })
      return out
    }
    case 'table.state':
      // 私有开局快照是 {table, game} 包装（HubOutbound.snapshotNode），其余为裸 TableView
      if (d.table !== undefined)
        return [{ type: 'state', table: d.table as TableView, game: d.game ?? null } as unknown as ServerMessage]
      return [{ type: 'tableState', table: d as unknown as TableView }]
    case 'table.kicked':
      return [{ type: 'kicked', roomCode: d.roomCode }]
    case 'table.closed':
      return [{ type: 'roomClosed' }]
    case 'queue.status':
      // data 字段名与旧 queueStatus 逐字对齐（GameHub queueStatusNode），整包透传
      return [{ type: 'queueStatus', ...(d as object) } as unknown as ServerMessage]
    case 'queue.timeout':
      return [{ type: 'queueTimeout' }]
    case 'room.list':
      return [{ type: 'roomList', capacity: d.capacity, entries: d.entries }]
    case 'phase.changed':
      return [{ type: 'phaseChanged', phase: d.phase, deadlineAt: d.deadlineAt, turn: d.turn, round: d.round }]
    case 'game.planeAccepted':
      return [{ type: 'planeAccepted', planes: d.planes }]
    case 'game.shot':
      return [{ type: 'shotResult', by: d.by, row: d.row, col: d.col, result: d.result, planeId: d.planeId, nextTurn: d.nextTurn }]
    case 'game.destroyed':
      return [{ type: 'planeDestroyed', ownerId: d.ownerId, planeId: d.planeId }]
    case 'game.over':
      return [{ type: 'gameOver', result: { ranking: d.ranking, reason: d.reason } }]
    case 'game.submitted':
      return [{ type: 'submitted', playerId: d.playerId, round: d.round }]
    case 'game.roundResult':
      // data 字段名与旧 roundResult 逐字对齐（EngineEventCodec.RoundResult），整包透传
      return [{ type: 'roundResult', ...(d as object) } as unknown as ServerMessage]
    case 'game.playerOut':
      return [{ type: 'playerOut', playerId: d.playerId, round: d.round }]
    case 'player.presence':
      return [{ type: 'presence', playerId: d.playerId, connected: d.connected }]
    case 'rank.changed':
      return [{ type: 'rankChanged', delta: d.delta, rank: d.rank, reason: d.reason }]
    case 'rank.list':
      return [{ type: 'rankList', season: d.season, entries: d.entries }]
    case 'coins.now':
      return [{ type: 'coinsChanged', delta: d.delta, reason: d.reason, balance: d.balance, ...(d.capped ? { capped: true } : {}) }]
    case 'coins.ledger': {
      // Java 条目 {entryKey,reason,delta,atMs} → 旧 CoinEntry；WS 不下发当日配额（daily=null，CoinSheet 有判空）
      const ledger = (d.ledger ?? []).map((e: AnyJson) => ({ id: e.entryKey, at: e.atMs, delta: e.delta, reason: e.reason }))
      return [{ type: 'coins', balance: d.balance, ledger, daily: null } as unknown as ServerMessage]
    }
    case 'error':
      return [{ type: 'error', code: mapErrorCode(d.code, d.message ?? ''), message: d.message }]
    default:
      console.warn('未映射的服务端事件', evt, d)
      return []
  }
}

// ================================================================ 连接

/**
 * 重连放弃判定（纯函数，便于单测）：整个 SocketHandle 生命周期内从未认证成功
 * （一次 profile.now 都没收到过）且重连尝试已达 threshold 次 → 认为 token 已失效，
 * 停止重连、回登录页。只要认证成功过一次就照常无限重连（顶号/断网都能自愈）。
 */
export function shouldStopReconnectAsExpired(everAuthed: boolean, reconnectAttempts: number, threshold = 3): boolean {
  return !everAuthed && reconnectAttempts >= threshold
}

export function connectSocket(opts: {
  url: string
  playerId: string
  nickname: () => string
  /** 登录过期（从未认证成功 + 重连触顶）时触发；App 层清空内存态并弹回登录。 */
  onExpired?: () => void
}): SocketHandle {
  const status = ref<SocketStatus>('connecting')
  const listeners: ((m: ServerMessage) => void)[] = []
  let ws: WebSocket | null = null
  let delay = 1000
  let stopped = false
  let seq = 0
  const auth = { authed: false }
  /** 本 handle 生命周期内是否认证成功过（profile.now 至少来过一次） */
  let everAuthed = false
  /** 本 handle 生命周期内累计的重连尝试次数 */
  let reconnects = 0

  const open = () => {
    status.value = 'connecting'
    auth.authed = false // 重连后 ready 要重新合成（playerId 理论不变，store 重复应用无害）
    const token = getVpnToken()
    const url = `${opts.url}${opts.url.includes('?') ? '&' : '?'}vpnToken=${encodeURIComponent(token)}`
    ws = new WebSocket(url)
    ws.onopen = () => {
      status.value = 'open'
      delay = 1000
      // 服务端连接即建档并推 profile.now；这里再要一次作兜底（重复推送 store 幂等）
      sendRaw({ cmd: 'profile.get', data: {} })
    }
    ws.onmessage = (ev) => {
      let m: AnyJson
      try {
        m = JSON.parse(String(ev.data))
      } catch {
        console.warn('无法解析的服务端消息', ev.data)
        return
      }
      if (typeof m.evt !== 'string') return
      for (const out of fromEvt(m.evt, m.data ?? {}, auth)) for (const l of listeners) l(out)
      if (auth.authed) everAuthed = true
    }
    ws.onclose = () => {
      // Java 顶号/超限都是普通关闭码，统一走重连；桌子在服务端保留，重连自动恢复
      status.value = 'closed'
      if (stopped) return
      if (shouldStopReconnectAsExpired(everAuthed, reconnects)) {
        stopped = true // 不再重连；等用户在登录页重登后整条链路重建
        opts.onExpired?.()
        return
      }
      reconnects += 1
      setTimeout(open, delay)
      delay = Math.min(delay * 2, 8000)
    }
    ws.onerror = () => ws?.close()
  }

  const sendRaw = (c: { cmd: string; data: Json }) => {
    if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ v: 1, cmd: c.cmd, seq: ++seq, data: c.data }))
  }

  open()

  return {
    status,
    send(msg) {
      const c = toCmd(msg)
      if (c) sendRaw(c)
    },
    onMessage(cb) {
      listeners.push(cb)
    },
    close() {
      stopped = true
      ws?.close()
    },
  }
}
