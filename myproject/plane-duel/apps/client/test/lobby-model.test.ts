import { describe, it, expect } from 'vitest'
import type { RoomListEntry, SeatView, TableView, RuleSet } from '@plane-duel/shared'
import { botFillText, canKick, hasBots, peerStatus, roomListRows, seatLabel } from '../src/lobby-model'
import { ruleSummary } from '../src/rule-editor-model'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }

const entry = (over: Partial<RoomListEntry> = {}): RoomListEntry => ({
  tableId: 't0001',
  capacity: 3,
  rules,
  hostNickname: '小明',
  seated: 2,
  seats: [{ seat: 0, nickname: '小明' }, { seat: 1, nickname: '小红' }, null],
  createdAt: 100,
  ...over,
})

const seat = (over: Partial<SeatView> = {}): SeatView => ({
  seat: 0,
  playerId: 'p1',
  nickname: '小明',
  ready: false,
  connected: true,
  bot: false,
  ...over,
})

const table = (seats: (SeatView | null)[]): TableView => ({
  roomCode: '123456',
  kind: 'friend',
  capacity: 3,
  rules,
  rulesVersion: 0,
  listed: false,
  hostId: 'p1',
  phase: 'waiting',
  seats,
  lastResult: null,
})

describe('roomListRows', () => {
  it('标题、摘要、座位数', () => {
    const rows = roomListRows([entry()])
    expect(rows[0]).toEqual({
      tableId: 't0001',
      title: '小明 的房间',
      summary: ruleSummary(rules),
      seatsText: '2/3',
      full: false,
    })
  })

  it('满座标记', () => {
    expect(roomListRows([entry({ seated: 3 })])[0]!.full).toBe(true)
  })

  it('保持输入顺序（排序是大厅/服务端的职责）', () => {
    const rows = roomListRows([entry({ tableId: 'b' }), entry({ tableId: 'a' })])
    expect(rows.map((r) => r.tableId)).toEqual(['b', 'a'])
  })
})

describe('botFillText', () => {
  it('未达最少真人：等待真人文案', () => {
    expect(botFillText({ waiting: 1, humansNeeded: 1, botFillAt: null }, 0)).toBe('等待真人 1/2')
  })

  it('补位关闭（botFillAt 为 null 且真人已足）：无文案', () => {
    expect(botFillText({ waiting: 2, humansNeeded: 0, botFillAt: null }, 0)).toBeNull()
  })

  it('倒计时向上取整：30 秒整、剩 1 毫秒', () => {
    expect(botFillText({ waiting: 2, humansNeeded: 0, botFillAt: 30_000 }, 0)).toBe(
      '30 秒后由电脑补位（对局会标注 🤖）',
    )
    expect(botFillText({ waiting: 3, humansNeeded: 0, botFillAt: 10_000 }, 9_999)).toBe(
      '1 秒后由电脑补位（对局会标注 🤖）',
    )
  })

  it('过点：正在补位', () => {
    expect(botFillText({ waiting: 2, humansNeeded: 0, botFillAt: 10_000 }, 12_000)).toBe('正在由电脑补位…')
    expect(botFillText({ waiting: 2, humansNeeded: 0, botFillAt: 10_000 }, 10_000)).toBe('正在由电脑补位…')
  })
})

describe('seatLabel / hasBots', () => {
  it('电脑座位带 🤖，真人不带', () => {
    expect(seatLabel(seat({ bot: true, nickname: '电脑新手' }))).toBe('🤖 电脑新手')
    expect(seatLabel(seat({ nickname: '小明' }))).toBe('小明')
  })

  it('hasBots：任一座位是电脑即为真', () => {
    expect(hasBots(table([seat(), seat({ seat: 1, bot: true, nickname: '电脑新手' })]))).toBe(true)
    expect(hasBots(table([seat(), null, seat({ seat: 2, nickname: '小红' })]))).toBe(false)
  })
})

describe('peerStatus（M2）', () => {
  it('出局优先于其它状态', () => {
    expect(peerStatus({ alive: false, submitted: true, connected: true })).toBe('出局')
    expect(peerStatus({ alive: false, submitted: false, connected: false })).toBe('出局')
  })

  it('✓ / 思考中 / 掉线', () => {
    expect(peerStatus({ alive: true, submitted: true, connected: true })).toBe('✓')
    expect(peerStatus({ alive: true, submitted: false, connected: true })).toBe('思考中')
    expect(peerStatus({ alive: true, submitted: false, connected: false })).toBe('掉线')
  })
})

describe('canKick', () => {
  const friendTable = (over: Partial<TableView> = {}): TableView => ({
    ...table([seat(), seat({ seat: 1, playerId: 'b', nickname: '小明' }), seat({ seat: 2, playerId: 'c', nickname: '小红' })]),
    kind: 'friend',
    hostId: 'p1',
    phase: 'waiting',
    ...over,
  })

  it('好友房房主、等候中：可移出自己以外、未准备、非电脑的座位', () => {
    const t = friendTable()
    const b = t.seats[1]!
    const c = { ...b, seat: 2, playerId: 'c', ready: true }
    expect(canKick(t, 'p1', b)).toBe(true)
    expect(canKick(t, 'p1', c)).toBe(false) // 已准备
    expect(canKick(t, 'p1', seat({ playerId: 'p1' }))).toBe(false) // 自己
    expect(canKick(t, 'p1', seat({ seat: 1, bot: true }))).toBe(false) // 电脑
  })

  it('非房主 / 非好友房 / 对局中一律为假', () => {
    const t = friendTable()
    const b = t.seats[1]!
    expect(canKick(t, 'b', b)).toBe(false)
    expect(canKick(friendTable({ kind: 'match' }), 'p1', b)).toBe(false)
    expect(canKick(friendTable({ phase: 'inGame' }), 'p1', b)).toBe(false)
  })
})
