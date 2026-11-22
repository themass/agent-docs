import { describe, it, expect } from 'vitest'
import { parseClientMessage, PRESETS } from '../src/index'

const toRaw = (m: string | object) => (typeof m === 'string' ? m : JSON.stringify(m))
const parse = (m: string | object) => parseClientMessage(toRaw(m))
const bad = (m: string | object) => {
  const r = parse(m)
  expect(r.ok).toBe(false)
  return r.ok === false ? r.code : null
}

describe('parseClientMessage 拒绝畸形输入', () => {
  it('非 JSON', () => expect(bad('not json')).toBe('BAD_JSON'))
  it('非对象', () => expect(bad('42')).toBe('BAD_JSON'))
  it('null', () => expect(bad('null')).toBe('BAD_JSON'))
  it('缺 type 字段', () => expect(bad('{}')).toBe('UNKNOWN_TYPE'))
  it('未知 type', () => expect(bad('{"type":"hack"}')).toBe('UNKNOWN_TYPE'))
  it('fire 缺 col', () => expect(bad('{"type":"fire","row":3}')).toBe('BAD_SHAPE'))
  it('row 为负', () => expect(bad('{"type":"fire","row":-1,"col":3}')).toBe('BAD_SHAPE'))
  it('row 为小数', () => expect(bad('{"type":"fire","row":1.5,"col":3}')).toBe('BAD_SHAPE'))
  it('row 为字符串', () => expect(bad('{"type":"fire","row":"3","col":3}')).toBe('BAD_SHAPE'))
  it('joinRoom 房间号非 6 位数字', () =>
    expect(bad('{"type":"joinRoom","roomCode":"abc"}')).toBe('BAD_SHAPE'))
  it('placePlane 空数组', () => expect(bad('{"type":"placePlane","planes":[]}')).toBe('BAD_SHAPE'))
  it('placePlane 元素缺 row', () =>
    expect(bad('{"type":"placePlane","planes":[{"col":1}]}')).toBe('BAD_SHAPE'))
})

describe('parseClientMessage 接受合法输入', () => {
  it('fire', () => {
    const r = parseClientMessage('{"type":"fire","row":3,"col":4}')
    expect(r).toEqual({ ok: true, msg: { type: 'fire', row: 3, col: 4 } })
  })

  it('auth 无 token', () => {
    const r = parseClientMessage('{"type":"auth","playerId":"abc"}')
    expect(r.ok).toBe(true)
  })

})

describe('useItem 在 P0 被标记为不支持', () => {
  it('返回 UNSUPPORTED 而非 BAD_SHAPE', () => {
    expect(bad('{"type":"useItem","itemId":"scan"}')).toBe('UNSUPPORTED')
  })
})

describe('协议 v2', () => {
  it('createRoom 需要合法 capacity 与 rules', () => {
    expect(parse({ type: 'createRoom', capacity: 3, rules: PRESETS.advanced, listed: true })).toMatchObject({ ok: true })
    expect(bad({ type: 'createRoom', capacity: 5, rules: PRESETS.standard, listed: true })).toBe('BAD_SHAPE')
    expect(bad({ type: 'createRoom', capacity: 2, rules: { ...PRESETS.standard, planeCount: 9 }, listed: true })).toBe('BAD_RULES')
  })
  it('queueJoin 需要合法 capacity 与 preset', () => {
    expect(parse({ type: 'queueJoin', capacity: 4, preset: 'expert' })).toMatchObject({ ok: true })
    expect(bad({ type: 'queueJoin', capacity: 4, preset: 'godmode' })).toBe('BAD_SHAPE')
  })
  it('auth 的 nickname 可选、为字符串', () => {
    expect(parse({ type: 'auth', playerId: 'p', nickname: '海鸥' })).toMatchObject({ ok: true })
    expect(bad({ type: 'auth', playerId: 'p', nickname: 3 })).toBe('BAD_SHAPE')
  })
  it('setReady / updateRules / setNickname', () => {
    expect(parse({ type: 'setReady', ready: true, rulesVersion: 0 })).toMatchObject({ ok: true })
    expect(bad({ type: 'setReady', ready: 'yes', rulesVersion: 0 })).toBe('BAD_SHAPE')
    expect(parse({ type: 'updateRules', rules: PRESETS.beginner })).toMatchObject({ ok: true })
    expect(parse({ type: 'setNickname', nickname: '狐狸' })).toMatchObject({ ok: true })
  })
  it('rematchRequest 已移除', () => expect(bad({ type: 'rematchRequest' })).toBe('UNKNOWN_TYPE'))
})

describe('协议 v3', () => {
  it('auth：playerId 以 bot: 开头被拒', () => expect(bad({ type: 'auth', playerId: 'bot:123456:1:1' })).toBe('BAD_SHAPE'))
  it('M5：形状正确但规则不合法 → BAD_RULES', () => {
    expect(bad({ type: 'createRoom', capacity: 2, rules: { ...PRESETS.standard, planeCount: 9 }, listed: true })).toBe('BAD_RULES')
    expect(bad({ type: 'updateRules', rules: { ...PRESETS.standard, boardSize: 30 } })).toBe('BAD_RULES')
    expect(bad({ type: 'createRoom', capacity: 5, rules: PRESETS.standard, listed: true })).toBe('BAD_SHAPE')
  })
  it('rules 缺失 → BAD_SHAPE', () => {
    expect(bad({ type: 'createRoom', capacity: 2, listed: true })).toBe('BAD_SHAPE')
    expect(bad({ type: 'updateRules' })).toBe('BAD_SHAPE')
  })
  it('createRoom 需要布尔 listed', () => {
    expect(parse({ type: 'createRoom', capacity: 3, rules: PRESETS.advanced, listed: false })).toMatchObject({ ok: true })
    expect(bad({ type: 'createRoom', capacity: 3, rules: PRESETS.advanced })).toBe('BAD_SHAPE')
  })
  it('M4：setReady 必带非负整数 rulesVersion', () => {
    expect(parse({ type: 'setReady', ready: true, rulesVersion: 0 })).toMatchObject({ ok: true })
    expect(bad({ type: 'setReady', ready: true })).toBe('BAD_SHAPE')
    expect(bad({ type: 'setReady', ready: true, rulesVersion: -1 })).toBe('BAD_SHAPE')
    expect(bad({ type: 'setReady', ready: true, rulesVersion: 1.5 })).toBe('BAD_SHAPE')
  })
  it('createPractice 需要合法 capacity 与 preset', () => {
    expect(parse({ type: 'createPractice', capacity: 4, preset: 'beginner' })).toMatchObject({ ok: true })
    expect(bad({ type: 'createPractice', capacity: 1, preset: 'beginner' })).toBe('BAD_SHAPE')
    expect(bad({ type: 'createPractice', capacity: 4, preset: 'godmode' })).toBe('BAD_SHAPE')
  })
  it('kick / setListed / joinListed / roomListSubscribe / roomListUnsubscribe', () => {
    expect(parse({ type: 'kick', playerId: 'p2' })).toMatchObject({ ok: true })
    expect(bad({ type: 'kick', playerId: '' })).toBe('BAD_SHAPE')
    expect(bad({ type: 'kick', playerId: 'x'.repeat(65) })).toBe('BAD_SHAPE')
    expect(parse({ type: 'setListed', listed: true })).toMatchObject({ ok: true })
    expect(bad({ type: 'setListed', listed: 'yes' })).toBe('BAD_SHAPE')
    expect(parse({ type: 'joinListed', tableId: '0123456789abcdef' })).toMatchObject({ ok: true })
    expect(bad({ type: 'joinListed', tableId: 'x'.repeat(65) })).toBe('BAD_SHAPE')
    expect(bad({ type: 'joinListed', tableId: '' })).toBe('BAD_SHAPE')
    expect(parse({ type: 'roomListSubscribe', capacity: 3 })).toMatchObject({ ok: true })
    expect(bad({ type: 'roomListSubscribe', capacity: 7 })).toBe('BAD_SHAPE')
    expect(parse({ type: 'roomListUnsubscribe' })).toMatchObject({ ok: true })
  })
  it('P3：profileRequest / rankListRequest 是无参数请求', () => {
    expect(parse({ type: 'profileRequest' })).toMatchObject({ ok: true, msg: { type: 'profileRequest' } })
    expect(parse({ type: 'rankListRequest' })).toMatchObject({ ok: true, msg: { type: 'rankListRequest' } })
  })
})
