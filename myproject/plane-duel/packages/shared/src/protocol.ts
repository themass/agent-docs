/**
 * 协议编解码与入站校验（spec §九）。
 *
 * 不引入 zod 等校验库：类型已由 types.ts 定义，手写校验与类型同源，
 * 且省一个依赖。任何外部输入都必须先过一次这里，服务端不得直接信任 JSON。
 */

import { PRESETS, isCapacity, validateRuleSet } from './ruleset'
import type { PresetId, RuleSet } from './ruleset'
import { isTicketId } from './coins'
import type { TicketId } from './coins'
import { BOT_ID_PREFIX } from './types'
import type { ClientMessage, ItemId, ServerMessage } from './types'

export type ParseCode = 'BAD_JSON' | 'BAD_SHAPE' | 'UNKNOWN_TYPE' | 'UNSUPPORTED' | 'BAD_RULES'

export type ParseResult = { ok: true; msg: ClientMessage } | { ok: false; code: ParseCode }

const ITEM_IDS: readonly ItemId[] = ['scan', 'doubleShot', 'radar', 'shield', 'relocate']

function isPlainObject(v: unknown): v is Record<string, unknown> {
  return typeof v === 'object' && v !== null && !Array.isArray(v)
}

/** 坐标：必须是非负整数。上界交给房间判断，因为需要 boardSize。 */
function isCoord(v: unknown): v is number {
  return typeof v === 'number' && Number.isInteger(v) && v >= 0
}

function isCell(v: unknown): v is { row: number; col: number } {
  return isPlainObject(v) && isCoord(v.row) && isCoord(v.col)
}

function isPresetId(v: unknown): v is PresetId {
  return typeof v === 'string' && Object.prototype.hasOwnProperty.call(PRESETS, v)
}

/**
 * 校验 msg.rules。字段缺失 → BAD_SHAPE；字段存在但 validateRuleSet 不通过
 * （任何 reason，含 shape）→ BAD_RULES。
 */
function readRules(obj: Record<string, unknown>): { rules: RuleSet } | { code: ParseCode } {
  if (obj.rules === undefined) return { code: 'BAD_SHAPE' }
  const r = validateRuleSet(obj.rules)
  return r.ok ? { rules: r.rules } : { code: 'BAD_RULES' }
}

/** 非空字符串、长度 ≤ 64（tableId、kick.playerId）。 */
function isShortId(v: unknown): v is string {
  return typeof v === 'string' && v.length > 0 && v.length <= 64
}

function isRoomCode(v: unknown): v is string {
  return typeof v === 'string' && /^\d{6}$/.test(v)
}

const fail = (code: ParseCode): ParseResult => ({ ok: false, code })
const ok = (msg: ClientMessage): ParseResult => ({ ok: true, msg })

/**
 * 解析一条客户端文本帧。
 *
 * 调用方（Hub）必须在解析失败时回 error 并**保持连接**，
 * 不得因为一条坏消息断开整个 socket（Review Focus #4）。
 */
export function parseClientMessage(raw: string): ParseResult {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    return fail('BAD_JSON')
  }

  if (!isPlainObject(parsed)) return fail('BAD_JSON')

  const type = parsed.type
  if (typeof type !== 'string') return fail('UNKNOWN_TYPE')

  switch (type) {
    case 'auth': {
      if (typeof parsed.playerId !== 'string' || parsed.playerId.length === 0) {
        return fail('BAD_SHAPE')
      }
      if (parsed.playerId.startsWith(BOT_ID_PREFIX)) return fail('BAD_SHAPE')
      if (parsed.token !== undefined && typeof parsed.token !== 'string') {
        return fail('BAD_SHAPE')
      }
      if (parsed.nickname !== undefined && typeof parsed.nickname !== 'string') {
        return fail('BAD_SHAPE')
      }
      const msg: ClientMessage = { type: 'auth', playerId: parsed.playerId }
      if (typeof parsed.token === 'string') msg.token = parsed.token
      if (typeof parsed.nickname === 'string') msg.nickname = parsed.nickname
      return ok(msg)
    }

    case 'setNickname': {
      if (typeof parsed.nickname !== 'string') return fail('BAD_SHAPE')
      return ok({ type: 'setNickname', nickname: parsed.nickname })
    }

    case 'createRoom': {
      if (!isCapacity(parsed.capacity)) return fail('BAD_SHAPE')
      if (typeof parsed.listed !== 'boolean') return fail('BAD_SHAPE')
      const r = readRules(parsed)
      if ('code' in r) return fail(r.code)
      return ok({ type: 'createRoom', capacity: parsed.capacity, rules: r.rules, listed: parsed.listed })
    }

    case 'updateRules': {
      const r = readRules(parsed)
      if ('code' in r) return fail(r.code)
      return ok({ type: 'updateRules', rules: r.rules })
    }

    case 'setReady': {
      if (typeof parsed.ready !== 'boolean') return fail('BAD_SHAPE')
      if (!isCoord(parsed.rulesVersion)) return fail('BAD_SHAPE')
      return ok({ type: 'setReady', ready: parsed.ready, rulesVersion: parsed.rulesVersion })
    }

    case 'joinRoom': {
      if (!isRoomCode(parsed.roomCode)) return fail('BAD_SHAPE')
      return ok({ type: 'joinRoom', roomCode: parsed.roomCode })
    }

    case 'queueJoin': {
      if (!isCapacity(parsed.capacity)) return fail('BAD_SHAPE')
      if (!isPresetId(parsed.preset)) return fail('BAD_SHAPE')
      // P4：门票档可选，缺省 free（v4 客户端不受影响）
      if (parsed.ticket !== undefined && !isTicketId(parsed.ticket)) return fail('BAD_SHAPE')
      return ok({ type: 'queueJoin', capacity: parsed.capacity, preset: parsed.preset, ...(parsed.ticket !== undefined ? { ticket: parsed.ticket as TicketId } : {}) })
    }

    case 'queueLeave':
      return ok({ type: 'queueLeave' })

    case 'createPractice': {
      if (!isCapacity(parsed.capacity)) return fail('BAD_SHAPE')
      if (!isPresetId(parsed.preset)) return fail('BAD_SHAPE')
      return ok({ type: 'createPractice', capacity: parsed.capacity, preset: parsed.preset })
    }

    case 'kick': {
      if (!isShortId(parsed.playerId)) return fail('BAD_SHAPE')
      return ok({ type: 'kick', playerId: parsed.playerId })
    }

    case 'setListed': {
      if (typeof parsed.listed !== 'boolean') return fail('BAD_SHAPE')
      return ok({ type: 'setListed', listed: parsed.listed })
    }

    case 'roomListSubscribe': {
      if (!isCapacity(parsed.capacity)) return fail('BAD_SHAPE')
      return ok({ type: 'roomListSubscribe', capacity: parsed.capacity })
    }

    case 'roomListUnsubscribe':
      return ok({ type: 'roomListUnsubscribe' })

    // P3（spec §21.6）：无参数请求
    case 'profileRequest':
      return ok({ type: 'profileRequest' })

    case 'rankListRequest':
      return ok({ type: 'rankListRequest' })

    // P4（spec §廿二.6）
    case 'coinRequest':
      return ok({ type: 'coinRequest' })

    case 'adRewardRequest': {
      if (parsed.slot !== 'coins') return fail('BAD_SHAPE')
      return ok({ type: 'adRewardRequest', slot: 'coins' })
    }

    case 'joinListed': {
      if (!isShortId(parsed.tableId)) return fail('BAD_SHAPE')
      return ok({ type: 'joinListed', tableId: parsed.tableId })
    }

    case 'placePlane': {
      const planes = parsed.planes
      if (!Array.isArray(planes) || planes.length === 0) return fail('BAD_SHAPE')
      if (!planes.every(isCell)) return fail('BAD_SHAPE')
      return ok({ type: 'placePlane', planes: planes.map((c) => ({ row: c.row, col: c.col })) })
    }

    case 'fire': {
      if (!isCoord(parsed.row) || !isCoord(parsed.col)) return fail('BAD_SHAPE')
      return ok({ type: 'fire', row: parsed.row, col: parsed.col })
    }

    case 'useItem': {
      // P0 不支持道具：形状合法则回 UNSUPPORTED，形状非法仍回 BAD_SHAPE。
      if (typeof parsed.itemId !== 'string') return fail('BAD_SHAPE')
      if (!ITEM_IDS.includes(parsed.itemId as ItemId)) return fail('BAD_SHAPE')
      return fail('UNSUPPORTED')
    }

    case 'leaveRoom':
      return ok({ type: 'leaveRoom' })

    default:
      return fail('UNKNOWN_TYPE')
  }
}

export function encodeServerMessage(msg: ServerMessage): string {
  return JSON.stringify(msg)
}
