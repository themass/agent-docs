import { describe, it, expect } from 'vitest'
import { PRESETS } from '@plane-duel/shared'
import { mkHub, RULES } from './hub-helpers'

describe('Hub v2：好友房', () => {
  it('建 2 人好友房 → 对手用房间号加入 → 双方准备 → 进入 placing，engine 为 duel', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    const code = h.createRoom('s1', 2, RULES)
    expect(code).toMatch(/^\d{6}$/)
    expect(h.tableOf('s1')).toMatchObject({ kind: 'friend', capacity: 2, rules: RULES, hostId: 'alice', phase: 'waiting' })
    h.send('s2', { type: 'joinRoom', roomCode: code })
    expect(h.tableOf('s2').seats.map((s: any) => s?.playerId)).toEqual(['alice', 'bob'])
    h.send('s1', { type: 'setReady', ready: true, rulesVersion: 0 })
    h.send('s2', { type: 'setReady', ready: true, rulesVersion: 0 })
    const t = h.hub.getTable(code)!
    expect(t.phase).toBe('inGame')
    expect(t.engine!.mode).toBe('duel')
    expect(t.engine!.phase).toBe('placing')
    expect(h.last('s2', 'state').game.mode).toBe('duel')
  })

  it('建 3 人好友房 → 另两人用房间号加入 → 全员准备 → 进入 placing，engine 为 melee', () => {
    const h = mkHub()
    for (const [sid, id] of [['s1', 'a'], ['s2', 'b'], ['s3', 'c']]) h.auth(sid!, id!)
    const code = h.createRoom('s1', 3)
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s3', { type: 'joinRoom', roomCode: code })
    for (const sid of ['s1', 's2']) h.send(sid, { type: 'setReady', ready: true, rulesVersion: 0 })
    expect(h.hub.getTable(code)!.phase).toBe('waiting')
    h.send('s3', { type: 'setReady', ready: true, rulesVersion: 0 })
    const t = h.hub.getTable(code)!
    expect(t.phase).toBe('inGame')
    expect(t.engine!.mode).toBe('melee')
    expect(t.engine!.phase).toBe('placing')
    for (const sid of ['s1', 's2', 's3']) expect(h.last(sid, 'state').game).toMatchObject({ mode: 'melee', phase: 'placing' })
  })

  it('加入不存在的房间返回 ROOM_NOT_FOUND', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.send('s1', { type: 'joinRoom', roomCode: '000000' })
    expect(h.last('s1', 'error')).toMatchObject({ code: 'ROOM_NOT_FOUND' })
  })

  it('第三人加入已满的 2 人房被拒，且不离开自己原来的桌', () => {
    const h = mkHub()
    h.auth('s1', 'a')
    h.auth('s2', 'b')
    h.auth('s3', 'c')
    const code = h.createRoom('s1')
    h.send('s2', { type: 'joinRoom', roomCode: code })
    const own = h.createRoom('s3')
    h.send('s3', { type: 'joinRoom', roomCode: code })
    expect(h.last('s3', 'error')).toMatchObject({ code: 'ROOM_FULL' })
    expect(h.hub.getTable(own)!.members).toEqual(['c'])
  })

  it('房间号不重复（生成器碰撞时重试）', () => {
    const seq = ['111111', '111111', '111111', '222222', '333333']
    const h = mkHub({ makeRoomCode: () => seq.shift() ?? '999999' })
    h.auth('s1', 'a')
    h.auth('s2', 'b')
    h.auth('s3', 'c')
    const codes = [h.createRoom('s1'), h.createRoom('s2'), h.createRoom('s3')]
    expect(codes).toEqual(['111111', '222222', '333333'])
  })

  it('重复加入自己所在的桌：只补发快照', () => {
    const h = mkHub()
    h.auth('s1', 'a')
    h.auth('s2', 'b')
    const code = h.createRoom('s1')
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s2', { type: 'joinRoom', roomCode: code })
    expect(h.last('s2', 'state').table.roomCode).toBe(code)
    expect(h.hub.getTable(code)!.members).toEqual(['a', 'b'])
  })

  it('房主改规则：其他人收到新规则', () => {
    const h = mkHub()
    h.auth('s1', 'a')
    h.auth('s2', 'b')
    const code = h.createRoom('s1')
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s1', { type: 'updateRules', rules: PRESETS.advanced })
    expect(h.tableOf('s2').rules).toEqual(PRESETS.advanced)
    h.send('s2', { type: 'updateRules', rules: PRESETS.beginner })
    expect(h.last('s2', 'error')).toMatchObject({ code: 'NOT_HOST' })
  })

  it('断线后用同一 playerId 重连能拿到 state 快照', () => {
    const h = mkHub()
    const { code, tb } = h.startDuel()
    h.hub.disconnect('s2')
    h.auth('s3', 'bob', tb)
    expect(h.last('s3', 'state').table.roomCode).toBe(code)
    expect(h.last('s3', 'state').game.mode).toBe('duel')
  })
})

describe('Hub v2：Review Focus #4（换桌/出队）', () => {
  it('在 A 桌等候时加入 B 桌 → 自动离开 A，A 桌其余人收到 tableState（座位空出）', () => {
    const h = mkHub()
    for (const [sid, id] of [['s1', 'a'], ['s2', 'b'], ['s3', 'c']]) h.auth(sid!, id!)
    const A = h.createRoom('s1', 3)
    h.send('s2', { type: 'joinRoom', roomCode: A })
    const B = h.createRoom('s3')
    h.send('s2', { type: 'joinRoom', roomCode: B })
    expect(h.tableOf('s2').roomCode).toBe(B)
    expect(h.tableOf('s1')).toMatchObject({ roomCode: A })
    expect(h.tableOf('s1').seats[1]).toBeNull()
    expect(h.hub.getTable(A)!.members).toEqual(['a'])
    expect(h.hub.getTable(B)!.members).toEqual(['c', 'b'])
  })

  it('排队时加入好友房 → 自动出队', () => {
    const h = mkHub()
    for (const [sid, id] of [['s1', 'a'], ['s2', 'b'], ['s3', 'c']]) h.auth(sid!, id!)
    const code = h.createRoom('s1')
    h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s3', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    expect(h.last('s3', 'queueStatus')).toMatchObject({ waiting: 1 })
    expect(h.tableOf('s3')).toBeUndefined()
    expect(h.tableOf('s2').roomCode).toBe(code)
  })

  it('排队时建房 → 自动出队', () => {
    const h = mkHub()
    h.auth('s1', 'a')
    h.auth('s2', 'b')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    h.createRoom('s1')
    h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    expect(h.last('s2', 'queueStatus')).toMatchObject({ waiting: 1 })
  })

  it('对局中加入别的房间 → ALREADY_IN_ROOM；建房同样被拒', () => {
    const h = mkHub()
    const { code } = h.startDuel()
    h.auth('s3', 'carol')
    const other = h.createRoom('s3')
    h.send('s1', { type: 'joinRoom', roomCode: other })
    expect(h.last('s1', 'error')).toMatchObject({ code: 'ALREADY_IN_ROOM' })
    h.send('s1', { type: 'createRoom', capacity: 2, rules: RULES, listed: false })
    expect(h.last('s1', 'error')).toMatchObject({ code: 'ALREADY_IN_ROOM' })
    expect(h.hub.getTable(code)!.phase).toBe('inGame')
    expect(h.hub.getTable(other)!.members).toEqual(['carol'])
  })
})

describe('Hub v2：快速匹配', () => {
  it('4 人快速匹配：4 个会话 queueJoin {4, standard} → 同一张 match 桌、规则为 PRESETS.standard、自动开局', () => {
    const h = mkHub()
    const sids = ['s1', 's2', 's3', 's4']
    sids.forEach((sid, i) => h.auth(sid, `p${i + 1}`))
    for (const sid of sids.slice(0, 3)) h.send(sid, { type: 'queueJoin', capacity: 4, preset: 'standard' })
    expect(h.last('s1', 'queueStatus')).toEqual({
      type: 'queueStatus',
      capacity: 4,
      preset: 'standard',
      waiting: 3,
      botFillAt: null,
      humansNeeded: 0,
    })
    h.send('s4', { type: 'queueJoin', capacity: 4, preset: 'standard' })
    const code = h.tableOf('s1').roomCode
    expect(code).toMatch(/^\d{6}$/)
    for (const sid of sids) expect(h.tableOf(sid).roomCode).toBe(code)
    const t = h.hub.getTable(code)!
    expect(t.kind).toBe('match')
    expect(t.rules).toEqual(PRESETS.standard)
    expect(t.members).toEqual(['p1', 'p2', 'p3', 'p4'])
    expect(t.phase).toBe('inGame')
    expect(t.engine!.mode).toBe('melee')
    expect(h.tableOf('s1').hostId).toBeNull()
  })

  it('不同档位不会凑到一起', () => {
    const h = mkHub()
    h.auth('s1', 'a')
    h.auth('s2', 'b')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'expert' })
    expect(h.tableOf('s1')).toBeUndefined()
    expect(h.tableOf('s2')).toBeUndefined()
  })

  it('queueLeave / 排队时 leaveRoom：出队，队友收到新的人数；不在队列时 queueLeave → NOT_IN_QUEUE', () => {
    const h = mkHub()
    for (const [sid, id] of [['s1', 'a'], ['s2', 'b'], ['s3', 'c']]) h.auth(sid!, id!)
    for (const sid of ['s1', 's2', 's3']) h.send(sid, { type: 'queueJoin', capacity: 4, preset: 'beginner' })
    h.send('s1', { type: 'queueLeave' })
    expect(h.last('s3', 'queueStatus')).toMatchObject({ waiting: 2 })
    h.send('s2', { type: 'leaveRoom' })
    expect(h.last('s2', 'error')).toBeUndefined()
    expect(h.last('s3', 'queueStatus')).toMatchObject({ waiting: 1 })
    h.send('s1', { type: 'queueLeave' })
    expect(h.last('s1', 'error')).toMatchObject({ code: 'NOT_IN_QUEUE' })
  })

  it('排队者断线：出队', () => {
    const h = mkHub()
    h.auth('s1', 'a')
    h.auth('s2', 'b')
    h.auth('s3', 'c')
    h.send('s1', { type: 'queueJoin', capacity: 3, preset: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 3, preset: 'standard' })
    h.hub.disconnect('s1')
    expect(h.last('s2', 'queueStatus')).toMatchObject({ waiting: 1 })
    h.send('s3', { type: 'queueJoin', capacity: 3, preset: 'standard' })
    expect(h.tableOf('s3')).toBeUndefined()
  })

  it('等待 60 秒提示一次 queueTimeout', () => {
    const h = mkHub()
    h.auth('s1', 'a')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'advanced' })
    h.advance(60_000)
    h.advance(1_000)
    expect(h.recv('s1').filter((m) => m.type === 'queueTimeout')).toHaveLength(1)
  })
})

describe('Hub v2：昵称', () => {
  it('昵称清洗：auth 带 13 字昵称 → ready.nickname 为回退值', () => {
    const h = mkHub()
    h.auth('s1', 'a', undefined, '一二三四五六七八九十一二三')
    expect(h.last('s1', 'ready').nickname).toBe('玩家')
  })

  it('auth 的合法昵称去掉首尾空白，并用作座位昵称', () => {
    const h = mkHub()
    h.auth('s1', 'a', undefined, '  敏捷的海鸥 ')
    expect(h.last('s1', 'ready').nickname).toBe('敏捷的海鸥')
    h.createRoom('s1')
    expect(h.tableOf('s1').seats[0].nickname).toBe('敏捷的海鸥')
  })

  it('setNickname：在桌上时同桌的人看到新昵称；之后建房也用新昵称', () => {
    const h = mkHub()
    h.auth('s1', 'a', undefined, '甲')
    h.auth('s2', 'b', undefined, '乙')
    const code = h.createRoom('s1')
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s1', { type: 'setNickname', nickname: '沉默的狐狸' })
    expect(h.tableOf('s2').seats[0].nickname).toBe('沉默的狐狸')
    h.send('s2', { type: 'leaveRoom' })
    h.send('s2', { type: 'setNickname', nickname: '丙' })
    h.createRoom('s2')
    expect(h.tableOf('s2').seats[0].nickname).toBe('丙')
  })
})

describe('Hub v2：身份与错误', () => {
  it('冒充（无 token / 错 token）仍被拒（P0 C2 回归）', () => {
    const h = mkHub()
    h.startDuel()
    h.auth('e1', 'alice')
    h.auth('e2', 'bob', 'nope')
    for (const sid of ['e1', 'e2']) {
      expect(h.last(sid, 'error')).toMatchObject({ code: 'BAD_TOKEN' })
      expect(h.recv(sid).some((m) => m.type === 'ready' || m.type === 'state' || m.type === 'tableState')).toBe(false)
    }
  })

  it('未认证发消息 → NOT_AUTHED', () => {
    const h = mkHub()
    h.open('s1')
    h.send('s1', { type: 'createRoom', capacity: 2, rules: RULES, listed: false })
    expect(h.last('s1', 'error')).toMatchObject({ code: 'NOT_AUTHED' })
  })

  it('不在桌上时 setReady / updateRules / fire / leaveRoom → NOT_IN_ROOM', () => {
    const h = mkHub()
    h.auth('s1', 'a')
    for (const msg of [
      { type: 'setReady', ready: true, rulesVersion: 0 },
      { type: 'updateRules', rules: RULES },
      { type: 'fire', row: 0, col: 0 },
      { type: 'placePlane', planes: [{ row: 3, col: 3 }] },
      { type: 'leaveRoom' },
    ]) {
      const before = h.recv('s1').length
      h.send('s1', msg)
      expect(h.recv('s1').slice(before)).toEqual([expect.objectContaining({ type: 'error', code: 'NOT_IN_ROOM' })])
    }
  })
})
