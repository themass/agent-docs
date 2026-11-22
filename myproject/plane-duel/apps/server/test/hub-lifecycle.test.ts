/**
 * 评审发现的 Hub 层问题回归测试（P0 的 C2, I2, I3, I4），按 v2 牌桌语义改写（裁定 R3）。
 */
import { describe, it, expect } from 'vitest'
import { FRIEND_SEAT_GRACE_MS, MATCH_SEAT_GRACE_MS } from '../src/table'
import { mkHub } from './hub-helpers'

describe('C2：冒充他人 playerId', () => {
  it('不带 token 冒充已认证的玩家被拒，拿不到对方快照', () => {
    const h = mkHub()
    h.startDuel()
    h.auth('evil', 'alice')
    expect(h.last('evil', 'error')).toMatchObject({ code: 'BAD_TOKEN' })
    expect(h.recv('evil').some((m) => m.type === 'state' || m.type === 'ready')).toBe(false)
  })

  it('错误 token 同样被拒', () => {
    const h = mkHub()
    h.startDuel()
    h.auth('evil', 'alice', 'guessed-token')
    expect(h.last('evil', 'error')).toMatchObject({ code: 'BAD_TOKEN' })
    expect(h.recv('evil').some((m) => m.type === 'state' || m.type === 'ready')).toBe(false)
  })

  it('冒充失败不会改掉被冒充者的昵称', () => {
    const h = mkHub()
    h.auth('s1', 'alice', undefined, '爱丽丝')
    h.auth('evil', 'alice', 'guessed', '坏人')
    h.createRoom('s1')
    expect(h.tableOf('s1').seats[0].nickname).toBe('爱丽丝')
  })

  it('带正确 token 重连成功，旧 socket 被关闭', () => {
    const h = mkHub()
    const { ta } = h.startDuel()
    h.auth('s1b', 'alice', ta)
    expect(h.last('s1b', 'state').game.you.planes).toEqual([{ row: 3, col: 7 }])
    expect(h.closed.has('s1')).toBe(true)
  })

  it('旧 socket 被顶掉后再断开，不影响新会话（不会让对局暂停）', () => {
    const h = mkHub()
    const { code, ta } = h.startDuel()
    h.auth('s1b', 'alice', ta)
    h.hub.disconnect('s1')
    expect(h.hub.getTable(code)!.engine!.phase).toBe('playing')
    expect(h.hub.getTable(code)!.view().seats[0]!.connected).toBe(true)
  })

  it('同一 socket 不能改认证成另一个 playerId（M7）', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.send('s1', { type: 'auth', playerId: 'mallory' })
    expect(h.last('s1', 'error')).toMatchObject({ code: 'BAD_TOKEN' })
  })
})

describe('I2：在牌桌上时重新认证一定补发快照', () => {
  it('对局中未检测到断开（半开连接）就重连，也能拿到 state', () => {
    const h = mkHub()
    const { code, tb } = h.startDuel()
    h.auth('s2b', 'bob', tb) // 旧 s2 从未 disconnect
    const st = h.last('s2b', 'state')
    expect(st.table.roomCode).toBe(code)
    expect(st.game.you.planes).toEqual([{ row: 6, col: 2 }])
  })

  it('等候室里半开连接重连，同样拿到 state', () => {
    const h = mkHub()
    const ta = h.auth('s1', 'alice')!
    const code = h.createRoom('s1')
    h.auth('s1b', 'alice', ta)
    expect(h.last('s1b', 'state')).toMatchObject({ table: { roomCode: code, phase: 'waiting' }, game: null })
  })
})

describe('I3（R3）：好友房等候室的生命周期', () => {
  it('房主在等人时离开房间：不报错，桌子关闭，房间号失效', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    const code = h.createRoom('s1')
    h.send('s1', { type: 'leaveRoom' })
    expect(h.last('s1', 'error')).toBeUndefined()
    expect(h.hub.getTable(code)).toBeUndefined()
    h.send('s2', { type: 'joinRoom', roomCode: code })
    expect(h.last('s2', 'error')).toMatchObject({ code: 'ROOM_NOT_FOUND' })
  })

  it('房主重复建房：自动离开旧桌，旧房间号作废', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    const old = h.createRoom('s1')
    const fresh = h.createRoom('s1')
    expect(fresh).not.toBe(old)
    h.send('s2', { type: 'joinRoom', roomCode: old })
    expect(h.last('s2', 'error')).toMatchObject({ code: 'ROOM_NOT_FOUND' })
  })

  it('等人时去快速匹配：空等候室作废', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    const code = h.createRoom('s1')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    expect(h.last('s1', 'queueStatus')).toMatchObject({ waiting: 1 })
    h.send('s2', { type: 'joinRoom', roomCode: code })
    expect(h.last('s2', 'error')).toMatchObject({ code: 'ROOM_NOT_FOUND' })
  })

  it('对局进行中不能去快速匹配', () => {
    const h = mkHub()
    h.startDuel()
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    expect(h.last('s1', 'error')).toMatchObject({ code: 'ALREADY_IN_ROOM' })
  })

  it('房主掉线时朋友加入：不开局（需全员准备），房主回来后拿到等候室快照', () => {
    const h = mkHub()
    const ta = h.auth('s1', 'alice')!
    h.auth('s2', 'bob')
    const code = h.createRoom('s1')
    h.hub.disconnect('s1')
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s2', { type: 'setReady', ready: true, rulesVersion: 0 })
    expect(h.hub.getTable(code)!.phase).toBe('waiting')
    expect(h.tableOf('s2').seats[0]).toMatchObject({ playerId: 'alice', connected: false })

    h.advance(20_000)
    h.auth('s1b', 'alice', ta)
    const st = h.last('s1b', 'state')
    expect(st.table).toMatchObject({ roomCode: code, phase: 'waiting', hostId: 'alice' })
    expect(st.table.seats[0].connected).toBe(true)
    expect(h.tableOf('s2').seats[0].connected).toBe(true)

    h.send('s1b', { type: 'setReady', ready: true, rulesVersion: 0 })
    expect(h.hub.getTable(code)!.phase).toBe('inGame')
  })

  it('房主掉线超过 5 分钟：座位释放，空桌关闭，房间号失效', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    const code = h.createRoom('s1')
    h.hub.disconnect('s1')
    h.advance(FRIEND_SEAT_GRACE_MS - 1)
    expect(h.hub.getTable(code)).toBeDefined()
    h.advance(1)
    expect(h.hub.getTable(code)).toBeUndefined()
    h.send('s2', { type: 'joinRoom', roomCode: code })
    expect(h.last('s2', 'error')).toMatchObject({ code: 'ROOM_NOT_FOUND' })
  })

  it('R2：房主掉线超过 60 秒而朋友在座：座位释放，房主转给朋友；房主回来不再在桌上', () => {
    const h = mkHub()
    const ta = h.auth('s1', 'alice')!
    h.auth('s2', 'bob')
    const code = h.createRoom('s1')
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.hub.disconnect('s1')
    h.advance(MATCH_SEAT_GRACE_MS - 1)
    expect(h.tableOf('s2')).toMatchObject({ hostId: 'alice' })
    h.advance(1)
    expect(h.tableOf('s2')).toMatchObject({ hostId: 'bob' })
    expect(h.tableOf('s2').seats[0]).toBeNull()
    h.auth('s1b', 'alice', ta)
    expect(h.last('s1b', 'state')).toBeUndefined()
    h.send('s1b', { type: 'setReady', ready: true, rulesVersion: 0 })
    expect(h.last('s1b', 'error')).toMatchObject({ code: 'NOT_IN_ROOM' })
  })
})

describe('I4：桌子清理与出站过滤', () => {
  it('结束后双方都离线：座位宽限过后桌子被删除', () => {
    const h = mkHub()
    const { code } = h.startDuel()
    h.finishDuel(code)
    expect(h.hub.getTable(code)!.phase).toBe('waiting')
    h.hub.disconnect('s1')
    h.hub.disconnect('s2')
    h.advance(FRIEND_SEAT_GRACE_MS)
    expect(h.hub.getTable(code)).toBeUndefined()
  })

  it('结束后在结算页直接建新房：自动离开旧桌，对方看到座位空出并成为房主', () => {
    const h = mkHub()
    const { code } = h.startDuel()
    h.finishDuel(code)
    const fresh = h.createRoom('s1')
    expect(h.last('s1', 'error')).toBeUndefined()
    expect(fresh).not.toBe(code)
    expect(h.tableOf('s2')).toMatchObject({ roomCode: code, hostId: 'bob' })
    expect(h.tableOf('s2').seats[0]).toBeNull()
  })

  it('中途离开后去了新桌：旧桌的后续消息不会发给他', () => {
    const h = mkHub()
    const { code } = h.startDuel()
    h.send('s1', { type: 'leaveRoom' })
    expect(h.last('s2', 'gameOver')).toBeDefined()
    const fresh = h.createRoom('s1')
    const before = h.recv('s1').length
    h.send('s2', { type: 'setReady', ready: true, rulesVersion: 0 })
    h.hub.disconnect('s2')
    h.advance(FRIEND_SEAT_GRACE_MS)
    expect(h.hub.getTable(code)).toBeUndefined()
    const later = h.recv('s1').slice(before)
    expect(later.every((m) => !('table' in m) || (m as any).table.roomCode === fresh)).toBe(true)
    expect(later.some((m) => m.type === 'roomClosed' || m.type === 'presence')).toBe(false)
  })

  it('匹配房有人离开：解散，其余人收到 roomClosed，桌子被删除，之后不再有消息', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    const code = h.tableOf('s1').roomCode
    expect(h.hub.getTable(code)!.kind).toBe('match')
    h.send('s1', { type: 'placePlane', planes: [{ row: 3, col: 7 }] })
    h.send('s2', { type: 'placePlane', planes: [{ row: 6, col: 2 }] })
    h.finishDuel(code)
    h.send('s1', { type: 'leaveRoom' })
    expect(h.last('s2', 'roomClosed')).toBeDefined()
    expect(h.hub.getTable(code)).toBeUndefined()
    const before = h.recv('s2').length
    h.advance(120_000)
    expect(h.recv('s2').length).toBe(before)
    h.send('s2', { type: 'setReady', ready: true, rulesVersion: 0 })
    expect(h.last('s2', 'error')).toMatchObject({ code: 'NOT_IN_ROOM' })
  })
})

describe('整分支评审 C1：对局因离开而结束、桌子随之关闭', () => {
  it('匹配房 2 人对局中一方离开 → 留下的人在 roomClosed 之前收到带 lastResult 的 tableState', () => {
    const h = mkHub()
    h.auth('s1', 'alice')
    h.auth('s2', 'bob')
    h.send('s1', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 2, preset: 'standard' })
    h.send('s1', { type: 'placePlane', planes: [{ row: 3, col: 7 }] })
    h.send('s2', { type: 'placePlane', planes: [{ row: 6, col: 2 }] })
    const before = h.recv('s2').length
    h.send('s1', { type: 'leaveRoom' })
    const after = h.recv('s2').slice(before)
    const types = after.map((m) => m.type)
    expect(types).toContain('gameOver')
    const iState = after.findIndex((m) => m.type === 'tableState' && (m as any).table.lastResult !== null)
    const iClosed = types.indexOf('roomClosed')
    expect(iState).toBeGreaterThanOrEqual(0)
    expect(iClosed).toBeGreaterThan(iState)
    const table = (after[iState] as any).table
    expect(table.phase).toBe('waiting')
    expect(table.lastResult.ranking.map((r: any) => r.playerId)).toContain('bob')
  })
})

describe('整分支评审 I7：重连时 auth 带的昵称更新座位昵称', () => {
  it('等候室里改名后重连：座位昵称为 auth 带来的新名字', () => {
    const h = mkHub()
    const ta = h.auth('s1', 'alice', undefined, '爱丽丝')!
    h.auth('s2', 'bob', undefined, '鲍勃')
    const code = h.createRoom('s1')
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.hub.disconnect('s1')
    h.auth('s1b', 'alice', ta, '新名字')
    expect(h.hub.getTable(code)!.view().seats[0]!.nickname).toBe('新名字')
    expect(h.last('s1b', 'state').table.seats[0].nickname).toBe('新名字')
    expect(h.tableOf('s2').seats[0].nickname).toBe('新名字')
  })

  it('对局中重连带新昵称同样更新座位', () => {
    const h = mkHub()
    const { code, ta } = h.startDuel()
    h.auth('s1b', 'alice', ta, '改名了')
    expect(h.hub.getTable(code)!.view().seats[0]!.nickname).toBe('改名了')
  })
})
