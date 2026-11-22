/**
 * 公开房间列表的订阅与推送（spec §20.6）：专区快照、合并推送、自动退订。
 */
import { describe, it, expect } from 'vitest'
import { ROOM_LIST_MAX } from '../src/hub'
import { mkHub } from './hub-helpers'

type Hub = ReturnType<typeof mkHub>

const roomLists = (h: Hub, sid: string) => h.recv(sid).filter((m: any) => m.type === 'roomList') as any[]

/** 开一个已公开的 3 人好友房（昵称与 playerId 相同），返回房间号。 */
function hostRoom(h: Hub, sid: string, nickname: string, capacity: 2 | 3 | 4 = 3): string {
  h.auth(sid, nickname, undefined, nickname)
  const code = h.createRoom(sid, capacity)
  h.send(sid, { type: 'setListed', listed: true })
  return code
}

describe('公开房间列表（Hub 侧）', () => {
  it('订阅立即收到快照；只含本专区', () => {
    const h = mkHub()
    hostRoom(h, 'h2', 'host2', 2)
    hostRoom(h, 'h3', 'host3', 3)
    h.auth('sub', 'sub')
    h.send('sub', { type: 'roomListSubscribe', capacity: 2 })

    const lists = roomLists(h, 'sub')
    expect(lists).toHaveLength(1)
    expect(lists[0].capacity).toBe(2)
    expect(lists[0].entries).toHaveLength(1)
    expect(lists[0].entries[0].capacity).toBe(2)
    expect(lists[0].entries[0].hostNickname).toBe('host2')
  })

  it('Review Focus #5：快照只含"公开 + 等候中 + 有空座"的好友房', () => {
    const h = mkHub()
    const good1 = hostRoom(h, 'g1h', '好房1')
    const good2 = hostRoom(h, 'g2h', '好房2')
    // 对局中的公开桌（3 人坐满并准备）
    const busy = hostRoom(h, 'bh', '对局中房')
    h.auth('b2', 'b2')
    h.auth('b3', 'b3')
    h.send('b2', { type: 'joinRoom', roomCode: busy })
    h.send('b3', { type: 'joinRoom', roomCode: busy })
    for (const sid of ['bh', 'b2', 'b3']) h.ready(sid)
    // 满座的公开桌
    const full = hostRoom(h, 'fh', '满座房', 2)
    h.auth('f2', 'f2')
    h.send('f2', { type: 'joinRoom', roomCode: full })
    // 未公开桌
    h.auth('uh', '未公开')
    h.createRoom('uh', 3)
    // 匹配房与练习房（capacity 3）
    for (const sid of ['m1', 'm2', 'm3']) {
      h.auth(sid, `匹配${sid}`)
      h.send(sid, { type: 'queueJoin', capacity: 3, preset: 'standard' })
    }
    h.auth('pr', '练家子')
    h.send('pr', { type: 'createPractice', capacity: 3, preset: 'standard' })

    h.auth('sub', 'sub')
    h.send('sub', { type: 'roomListSubscribe', capacity: 3 })
    const entries = roomLists(h, 'sub').at(-1).entries
    const ids = entries.map((e: any) => e.hostNickname).sort()
    expect(ids).toEqual(['好房1', '好房2'])
    expect(good1).toBeTruthy()
    expect(good2).toBeTruthy()
  })

  it('有人入座 → 1 秒内收到新快照；不足 1 秒的变化合并到同一次推送', () => {
    const h = mkHub()
    const code = hostRoom(h, 'hh', '房主', 4)
    h.auth('sub', 'sub')
    h.send('sub', { type: 'roomListSubscribe', capacity: 4 })
    expect(roomLists(h, 'sub').at(-1).entries[0].seated).toBe(1)

    // 同一秒内两次变化（两人先后入座），只在满 1 秒时合并推送一次
    h.auth('j1', 'j1')
    h.send('j1', { type: 'joinRoom', roomCode: code })
    h.advance(400)
    h.auth('j2', 'j2')
    h.send('j2', { type: 'joinRoom', roomCode: code })
    h.advance(599) // 距上次推送 999ms → 还没到
    expect(roomLists(h, 'sub')).toHaveLength(1)

    h.advance(1) // 满 1000ms → 推一次，两条变化都在
    const lists = roomLists(h, 'sub')
    expect(lists).toHaveLength(2)
    expect(lists[1].entries[0].seated).toBe(3)
  })

  it('内容未变（对局中的桌在打）不推送', () => {
    const h = mkHub()
    hostRoom(h, 'hh', '房主')
    h.auth('sub', 'sub')
    h.send('sub', { type: 'roomListSubscribe', capacity: 3 })
    // 反复 tick：每张好友桌的派发都会标脏，但内容没变 → 不推送
    for (let i = 0; i < 10; i++) h.advance(1_000)
    expect(roomLists(h, 'sub')).toHaveLength(1)
  })

  it(`排序：在座多者在前，同数新建者在前；最多 ${ROOM_LIST_MAX} 条`, () => {
    const h = mkHub()
    const codes: string[] = []
    for (let i = 0; i < 52; i++) {
      codes.push(hostRoom(h, `h${i}`, `host-${i}`, 3))
      h.advance(100)
    }
    h.auth('x1', 'x1')
    h.send('x1', { type: 'joinRoom', roomCode: codes[0]! })
    h.advance(100)
    h.auth('x2', 'x2')
    h.send('x2', { type: 'joinRoom', roomCode: codes[1]! })

    h.auth('sub', 'sub')
    h.send('sub', { type: 'roomListSubscribe', capacity: 3 })
    const entries = roomLists(h, 'sub').at(-1).entries
    expect(entries).toHaveLength(ROOM_LIST_MAX)
    expect(entries[0]).toMatchObject({ seated: 2, hostNickname: 'host-1' }) // 同数取新
    expect(entries[1]).toMatchObject({ seated: 2, hostNickname: 'host-0' })
    expect(entries[2]).toMatchObject({ seated: 1, hostNickname: 'host-51' })
    expect(entries[49].hostNickname).toBe('host-4') // 最旧的两个 1 座房被截掉
  })

  it('建房 / 排队 / 断线 → 自动退订，之后不再收到 roomList', () => {
    const h = mkHub()
    const code = hostRoom(h, 'hh', '房主')

    h.auth('sub1', 'sub1')
    h.send('sub1', { type: 'roomListSubscribe', capacity: 3 })
    h.createRoom('sub1', 2) // 建房（createRoom 辅助已认证 sub1？否——sub1 已认证，createRoom 直接用）

    h.auth('sub2', 'sub2')
    h.send('sub2', { type: 'roomListSubscribe', capacity: 3 })
    h.send('sub2', { type: 'queueJoin', capacity: 2, preset: 'standard' }) // 排队

    h.auth('sub3', 'sub3')
    h.send('sub3', { type: 'roomListSubscribe', capacity: 3 })
    h.hub.disconnect('sub3') // 断线

    // 触发一次列表变化
    h.auth('j1', 'j1')
    h.send('j1', { type: 'joinRoom', roomCode: code })
    h.advance(1_000)

    expect(roomLists(h, 'sub1')).toHaveLength(1) // 只有订阅时的即时快照
    expect(roomLists(h, 'sub2')).toHaveLength(1)
    expect(roomLists(h, 'sub3')).toHaveLength(1)
  })

  it('Review Focus #5：被屏蔽昵称的房主 → 条目 hostNickname 为回退值', () => {
    const h = mkHub()
    h.open('hh')
    h.send('hh', { type: 'auth', playerId: 'hh', nickname: 'gm001' }) // "gm" 是保留前缀
    expect(h.last('hh', 'ready').nickname).toBe('玩家')
    h.send('hh', { type: 'createRoom', capacity: 3, rules: { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: false }, listed: false })
    h.send('hh', { type: 'setListed', listed: true })

    h.auth('sub', 'sub')
    h.send('sub', { type: 'roomListSubscribe', capacity: 3 })
    expect(roomLists(h, 'sub').at(-1).entries[0].hostNickname).toBe('玩家')
  })

  it('roomListUnsubscribe 后不再收到推送', () => {
    const h = mkHub()
    const code = hostRoom(h, 'hh', '房主')
    h.auth('sub', 'sub')
    h.send('sub', { type: 'roomListSubscribe', capacity: 3 })
    h.send('sub', { type: 'roomListUnsubscribe' })

    h.auth('j1', 'j1')
    h.send('j1', { type: 'joinRoom', roomCode: code })
    h.advance(1_000)
    expect(roomLists(h, 'sub')).toHaveLength(1)
    // 未订阅时再退订：静默无错误
    const before = h.recv('sub').length
    h.send('sub', { type: 'roomListUnsubscribe' })
    expect(h.recv('sub').length).toBe(before)
  })
})
