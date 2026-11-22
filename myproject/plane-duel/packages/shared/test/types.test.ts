import { describe, it, expect } from 'vitest'
import type { ErrorCode, ServerMessage, TableKind } from '../src/index'
import { BOT_ID_PREFIX } from '../src/index'

describe('protocol types', () => {
  it('gameOver reason 只有 head / allPlanes / forfeit / lastStanding', () => {
    const reasons: Extract<ServerMessage, { type: 'gameOver' }>['result']['reason'][] = [
      'head',
      'allPlanes',
      'forfeit',
      'lastStanding',
    ]
    expect(reasons).toHaveLength(4)
  })

  it('placementTimeout 不是合法 reason（spec §二：摆放超时不判负）', () => {
    // @ts-expect-error 若 placementTimeout 被加进 GameOverReason，tsc 会报"未使用的 @ts-expect-error"
    const bad: Extract<ServerMessage, { type: 'gameOver' }>['result']['reason'] = 'placementTimeout'
    expect(bad).toBeDefined()
  })

  it('TableKind 三个值', () => {
    const kinds: TableKind[] = ['friend', 'match', 'practice']
    expect(kinds).toHaveLength(3)
  })

  it('v3 新增四个错误码', () => {
    const codes: ErrorCode[] = ['TARGET_NOT_FOUND', 'TARGET_READY', 'BANNED', 'STALE_RULES']
    expect(codes).toHaveLength(4)
  })

  it('BOT_ID_PREFIX', () => expect(BOT_ID_PREFIX).toBe('bot:'))
})
