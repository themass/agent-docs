/**
 * Hub 的 P2 路由（spec §20.4–§20.8）：练习、补位、踢人、公开列表加入、按桌成员集合。
 */
import { describe, it, expect } from 'vitest'
import { BOT_ID_PREFIX, PRESETS } from '@plane-duel/shared'
import { BOT_FILL_AFTER_MS } from '../src/matchmaking'
import { mkHub, RULES } from './hub-helpers'

const errorOf = (msgs: any[]) => {
  const m = [...msgs].reverse().find((x) => x.type === 'error')
  return m?.code ?? null
}

describe('Hub P2：人机练习（spec §20.4）', () => {
  it('createPractice {4, beginner}：真人入座、3 个电脑、立即进入 placing；tableState 中 kind=practice、3 个 bot 座位', () => {
    const h = mkHub()
    h.auth('s1', 'solo')
    h.send('s1', { type: 'createPractice', capacity: 4, preset: 'beginner' })

    const t = h.tableOf('s1')
    expect(t.kind).toBe('practice')
    expect(t.rules).toEqual(PRESETS.beginner)
    expect(t.hostId).toBeNull()
    expect(t.listed).toBe(false)
    const bots = t.seats.filter((s: any) => s?.bot)
    expect(bots).toHaveLength(3)
    expect(bots.every((s: any) => s.nickname.startsWith('电脑'))).toBe(true)

    const table = h.hub.getTable(t.roomCode)!
    expect(table.phase).toBe('inGame')
    expect(table.engine!.mode).toBe('melee')
    expect(h.last('s1', 'state')?.game?.phase).toBe('placing')
  })

  it('2 人练习桌用 duel 引擎；练习桌没有房主、不能改规则', () => {
    const h = mkHub()
    h.auth('s1', 'solo')
    h.send('s1', { type: 'createPractice', capacity: 2, preset: 'expert' })
    const t = h.tableOf('s1')
    expect(h.hub.getTable(t.roomCode)!.engine!.mode).toBe('duel')
    h.send('s1', { type: 'updateRules', rules: PRESETS.beginner })
    expect(errorOf(h.recv('s1'))).toBe('NOT_HOST')
  })

  it('练习桌不能用房间号加入 → ROOM_NOT_FOUND', () => {
    const h = mkHub()
    h.auth('s1', 'solo')
    h.send('s1', { type: 'createPractice', capacity: 2, preset: 'beginner' })
    const code = h.tableOf('s1').roomCode
    h.auth('s2', 'other')
    h.send('s2', { type: 'joinRoom', roomCode: code })
    expect(errorOf(h.recv('s2'))).toBe('ROOM_NOT_FOUND')
    expect(h.tableOf('s2')).toBeUndefined()
    // s1 还在自己的练习桌上
    expect(h.tableOf('s1').roomCode).toBe(code)
  })

  it('练习中真人离开 → 桌子关闭，不再空转', () => {
    const h = mkHub()
    h.auth('s1', 'solo')
    h.send('s1', { type: 'createPractice', capacity: 2, preset: 'beginner' })
    const code = h.tableOf('s1').roomCode
    h.send('s1', { type: 'leaveRoom' })
    // 对局中离开：引擎判电脑胜（forfeit），随后桌上无真人 → 桌子整个删除
    expect(h.hub.getTable(code)).toBeUndefined()
    expect(h.recv('s1').some((m: any) => m.type === 'gameOver')).toBe(true)
  })
})

describe('Hub P2：匹配补位（spec §20.5）', () => {
  const fill = () => mkHub({ botFillMs: BOT_FILL_AFTER_MS })

  it('补位开启：两人排 {4, standard}，45 秒后进入 match 桌，空座 bot=true，规则为 PRESETS.standard', () => {
    const h = fill()
    h.auth('s1', 'p1')
    h.auth('s2', 'p2')
    h.send('s1', { type: 'queueJoin', capacity: 4, preset: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 4, preset: 'standard' })
    expect(h.tableOf('s1')).toBeUndefined()

    h.advance(44_999)
    expect(h.tableOf('s1')).toBeUndefined()

    h.advance(1)
    const t = h.tableOf('s1')
    expect(t.kind).toBe('match')
    expect(t.rules).toEqual(PRESETS.standard)
    expect(t.seats.filter((s: any) => s?.bot)).toHaveLength(2)
    expect(h.hub.getTable(t.roomCode)!.phase).toBe('inGame')
    // 断线重连语义之外的第二道保险：桌子成员里没有 bot 前缀之外的错位
    expect(h.tableOf('s2').roomCode).toBe(t.roomCode)
  })

  it('单人排 {4, standard} 等 120 秒也不建桌（不足 MIN_HUMANS）', () => {
    const h = fill()
    h.auth('s1', 'p1')
    h.send('s1', { type: 'queueJoin', capacity: 4, preset: 'standard' })
    h.advance(120_000)
    expect(h.tableOf('s1')).toBeUndefined()
    expect(h.recv('s1').some((m: any) => m.type === 'queueTimeout')).toBe(false)
    // 仍在队列里
    h.send('s1', { type: 'queueLeave' })
    expect(errorOf(h.recv('s1'))).not.toBe('NOT_IN_QUEUE')
  })

  it('Review Focus #4：排队时用房间号加入好友房 → 出队，60 秒后不被补位进第二张桌', () => {
    const h = fill()
    h.auth('s1', 'p1')
    h.auth('s2', 'host')
    h.send('s1', { type: 'queueJoin', capacity: 4, preset: 'standard' })
    const code = h.createRoom('s2', 4)
    h.send('s1', { type: 'joinRoom', roomCode: code })
    h.advance(60_000)
    expect(h.tableOf('s1').roomCode).toBe(code)
    expect(h.tableOf('s1').kind).toBe('friend')
  })

  it('Review Focus #4：排队者断线即出队（P0 语义）→ 队列回到单人，永不补位成桌', () => {
    const h = fill()
    h.auth('s1', 'p1')
    h.auth('s2', 'p2')
    h.send('s1', { type: 'queueJoin', capacity: 3, preset: 'standard' })
    h.send('s2', { type: 'queueJoin', capacity: 3, preset: 'standard' })
    // p2 掉线出队：p1 收到 waiting 回 1 的 queueStatus
    h.hub.disconnect('s2')
    expect(h.last('s1', 'queueStatus')).toMatchObject({ waiting: 1, botFillAt: null, humansNeeded: 1 })
    h.advance(30_001)
    expect(h.tableOf('s1')).toBeUndefined()
  })
})

describe('Hub P2：踢人（spec §20.8）', () => {
  it('Review Focus #3：房主踢人 → 被踢者收到 kicked；之后该桌的 tableState 不再投给被踢者', () => {
    const h = mkHub()
    h.auth('s1', 'host')
    h.auth('s2', 'guest')
    h.auth('s3', 'watch')
    const code = h.createRoom('s1', 3)
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s3', { type: 'joinRoom', roomCode: code })

    h.send('s1', { type: 'kick', playerId: 'guest' })
    expect(h.recv('s2').some((m: any) => m.type === 'kicked' && m.roomCode === code)).toBe(true)

    // 被踢者不再收到这张桌的后续广播；留下的人收到
    const s2Count = h.recv('s2').length
    const s3Count = h.recv('s3').length
    h.send('s1', { type: 'setNickname', nickname: '房主改名' })
    expect(h.recv('s2').length).toBe(s2Count)
    expect(h.recv('s3').length).toBeGreaterThan(s3Count)
    expect(h.recv('s3').some((m: any) => m.type === 'tableState' && m.table.seats.some((s: any) => s?.nickname === '房主改名'))).toBe(true)
  })

  it('Review Focus #3：被踢者用房间号再加入 → BANNED，且不会离开自己当前所在的桌', () => {
    const h = mkHub()
    h.auth('s1', 'host')
    h.auth('s2', 'guest')
    const code = h.createRoom('s1', 3)
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s1', { type: 'kick', playerId: 'guest' })

    // 被踢者先建了自己的桌
    const own = h.createRoom('s2', 2)
    h.send('s2', { type: 'joinRoom', roomCode: code })
    expect(errorOf(h.recv('s2'))).toBe('BANNED')
    expect(h.tableOf('s2').roomCode).toBe(own)
  })

  it('已准备的客人不能踢 → TARGET_READY；房主以外不能踢 → NOT_HOST', () => {
    const h = mkHub()
    h.auth('s1', 'host')
    h.auth('s2', 'guest')
    const code = h.createRoom('s1', 3)
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s2', { type: 'setReady', ready: true, rulesVersion: 0 })
    h.send('s1', { type: 'kick', playerId: 'guest' })
    expect(errorOf(h.recv('s1'))).toBe('TARGET_READY')

    h.send('s2', { type: 'kick', playerId: 'host' })
    expect(errorOf(h.recv('s2'))).toBe('NOT_HOST')
  })
})

describe('Hub P2：公开列表加入（spec §20.6）', () => {
  it('joinListed：按 tableId 加入成功；未公开 → ROOM_NOT_FOUND；满座 → ROOM_FULL', () => {
    const h = mkHub()
    h.auth('s1', 'host')
    const code = h.createRoom('s1', 3)
    const table = h.hub.getTable(code)!

    // 未公开
    h.auth('s2', 'joiner')
    h.send('s2', { type: 'joinListed', tableId: table.tableId })
    expect(errorOf(h.recv('s2'))).toBe('ROOM_NOT_FOUND')

    h.send('s1', { type: 'setListed', listed: true })
    expect(h.last('s1', 'tableState').table.listed).toBe(true)

    h.send('s2', { type: 'joinListed', tableId: table.tableId })
    expect(h.tableOf('s2').roomCode).toBe(code)

    // 第三个位置留给别人，第四个就满座了
    h.auth('s3', 'third')
    h.send('s3', { type: 'joinRoom', roomCode: code })
    h.auth('s4', 'fourth')
    h.send('s4', { type: 'joinListed', tableId: table.tableId })
    expect(errorOf(h.recv('s4'))).toBe('ROOM_FULL')
  })

  it('joinListed 不存在的 tableId → ROOM_NOT_FOUND', () => {
    const h = mkHub()
    h.auth('s1', 'joiner')
    h.send('s1', { type: 'joinListed', tableId: 'ffffffffffffffff' })
    expect(errorOf(h.recv('s1'))).toBe('ROOM_NOT_FOUND')
  })

  it('评审：对自己已在的桌再 joinListed → 只补发快照，不离开再进（房主不会因自己让位）', () => {
    const h = mkHub()
    h.auth('s1', 'host')
    const code = h.createRoom('s1', 3)
    h.send('s1', { type: 'setListed', listed: true })
    const table = h.hub.getTable(code)!
    const before = h.recv('s1').length
    h.send('s1', { type: 'joinListed', tableId: table.tableId })
    expect(h.tableOf('s1').roomCode).toBe(code)
    // 还是房主、还在 0 号座位；只多收到补发的消息，没有离开/重进的连环广播
    const ts = h.last('s1', 'tableState')
    expect(ts.table.hostId).toBe('host')
    expect(ts.table.seats[0]?.playerId).toBe('host')
    expect(h.recv('s1').length).toBeGreaterThan(before)
  })

  it('Review Focus #5：joinListed 失败时玩家仍坐在原桌（座位与归属不变）', () => {
    const h = mkHub()
    h.auth('s1', 'a')
    h.auth('s2', 'b')
    h.auth('s3', 'c')
    const own = h.createRoom('s1', 2)
    h.send('s2', { type: 'joinRoom', roomCode: own })

    // 另一张 2 人桌，公开并坐满 → joinListed 必然 ROOM_FULL
    const other = h.createRoom('s3', 2)
    const otherTable = h.hub.getTable(other)!
    h.send('s3', { type: 'setListed', listed: true })
    h.auth('s4', 'd')
    h.send('s4', { type: 'joinRoom', roomCode: other })
    h.send('s2', { type: 'joinListed', tableId: otherTable.tableId })
    expect(errorOf(h.recv('s2'))).toBe('ROOM_FULL')

    // s2 还在原桌上：座位表未变
    const t = h.tableOf('s2')
    expect(t.roomCode).toBe(own)
    expect(t.seats.filter((s: any) => s !== null)).toHaveLength(2)
  })
})

describe('Hub P2：协议 v3 回归', () => {
  it('M4：setReady 带旧 rulesVersion → STALE_RULES，并补发当前 tableState', () => {
    const h = mkHub()
    h.auth('s1', 'host')
    h.auth('s2', 'guest')
    const code = h.createRoom('s1', 3)
    h.send('s2', { type: 'joinRoom', roomCode: code })
    h.send('s1', { type: 'updateRules', rules: PRESETS.advanced })
    h.send('s2', { type: 'setReady', ready: true, rulesVersion: 0 })
    expect(errorOf(h.recv('s2'))).toBe('STALE_RULES')
    expect(h.last('s2', 'tableState').table.rulesVersion).toBe(1)
  })

  it('P0 回归：auth playerId=bot:… → BAD_SHAPE（协议层拒，不建会话身份）', () => {
    const h = mkHub()
    h.open('s1')
    h.send('s1', { type: 'auth', playerId: `${BOT_ID_PREFIX}fake` })
    expect(errorOf(h.recv('s1'))).toBe('BAD_SHAPE')
    h.send('s1', { type: 'createRoom', capacity: 2, rules: RULES, listed: false })
    expect(errorOf(h.recv('s1'))).toBe('NOT_AUTHED')
  })

  it('不在桌上时 setListed / kick → NOT_IN_ROOM', () => {
    const h = mkHub()
    h.auth('s1', 'lonely')
    h.send('s1', { type: 'setListed', listed: true })
    expect(errorOf(h.recv('s1'))).toBe('NOT_IN_ROOM')
    h.send('s1', { type: 'kick', playerId: 'x' })
    expect(errorOf(h.recv('s1'))).toBe('NOT_IN_ROOM')
  })
})

describe('Hub P2：M5 按桌成员集合', () => {
  it('一张桌的成员变化只影响该桌成员的归属（其它桌的玩家不受影响）', () => {
    const h = mkHub()
    h.auth('s1', 'a1')
    h.auth('s2', 'a2')
    h.auth('s3', 'b1')
    const codeA = h.createRoom('s1', 3)
    h.send('s2', { type: 'joinRoom', roomCode: codeA })
    const codeB = h.createRoom('s3', 2)

    // A 桌成员变化：s2 离开后，A 桌之后的广播不再投给他
    h.send('s2', { type: 'leaveRoom' })
    const s2Count = h.recv('s2').length
    h.send('s1', { type: 'setNickname', nickname: '改名' })
    expect(h.recv('s2').length).toBe(s2Count)

    // A 桌整桌关闭（无真人 → 静默关闭）不影响 B 桌：s3 仍能收到自己桌的广播
    h.send('s1', { type: 'leaveRoom' })
    expect(h.hub.getTable(codeA)).toBeUndefined()
    const s3Count = h.recv('s3').length
    h.send('s3', { type: 'setNickname', nickname: 'B房主' })
    expect(h.recv('s3').length).toBeGreaterThan(s3Count)
    expect(
      h.recv('s3').some(
        (m: any) => m.type === 'tableState' && m.table.roomCode === codeB && m.table.seats[0]?.nickname === 'B房主',
      ),
    ).toBe(true)
  })
})
