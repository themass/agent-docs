import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { connectSocket, getVpnToken, shouldStopReconnectAsExpired } from '../src/net/socket'

class FakeWS {
  static OPEN = 1
  static instances: FakeWS[] = []
  readyState = 0
  sent: string[] = []
  onopen: (() => void) | null = null
  onmessage: ((ev: { data: string }) => void) | null = null
  onclose: ((ev: { code: number }) => void) | null = null
  onerror: (() => void) | null = null
  constructor(readonly url: string) {
    FakeWS.instances.push(this)
  }
  send(data: string) {
    this.sent.push(data)
  }
  close() {}
  open() {
    this.readyState = FakeWS.OPEN
    this.onopen?.()
  }
  /** 服务端 → 客户端一帧（v1 信封） */
  emit(evt: string, data: unknown, ref: number | null = null) {
    this.onmessage?.({ data: JSON.stringify({ v: 1, evt, seq: 0, ref, data }) })
  }
}

const stubEnv = () => {
  const store = new Map<string, string>()
  vi.stubGlobal('localStorage', {
    getItem: (k: string) => store.get(k) ?? null,
    setItem: (k: string, v: string) => void store.set(k, v),
    removeItem: (k: string) => void store.delete(k),
  })
  vi.stubGlobal('WebSocket', FakeWS)
}

describe('Java v1 协议适配层', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWS.instances = []
    stubEnv()
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('握手 URL 带 vpnToken 查询参数；连接即发 profile.get', () => {
    localStorage.setItem('plane-duel:vpnToken', 'TKN')
    const sock = connectSocket({ url: 'ws://x/api/game/ws', playerId: 'p1', nickname: () => 'nick' })
    expect(FakeWS.instances[0]!.url).toBe('ws://x/api/game/ws?vpnToken=TKN')
    FakeWS.instances[0]!.open()
    expect(JSON.parse(FakeWS.instances[0]!.sent[0]!)).toMatchObject({ v: 1, cmd: 'profile.get', seq: 1, data: {} })
    sock.close()
  })

  it('token 只从 localStorage 取：URL ?vpnToken= 一律不读、不持久化（产品要求）', () => {
    // node（vitest）环境本来没有 location；这里额外钉死旧行为不再回来：
    // getVpnToken 不引用 location.search，token 缺失时握手参数为空串
    expect(getVpnToken()).toBe('')
    const sock = connectSocket({ url: 'ws://x', playerId: 'p1', nickname: () => 'nick' })
    expect(FakeWS.instances[0]!.url).toBe('ws://x?vpnToken=')
    sock.close()
  })

  it('命令映射：旧 type → v1 cmd/seq 自增', () => {
    const sock = connectSocket({ url: 'ws://x', playerId: 'p1', nickname: () => 'nick' })
    FakeWS.instances[0]!.open() // seq=1 profile.get
    sock.send({ type: 'fire', row: 3, col: 4 })
    sock.send({ type: 'placePlane', planes: [{ row: 0, col: 0 }] })
    sock.send({ type: 'auth', playerId: 'p1' }) // 无对应命令，静默丢弃
    const frames = FakeWS.instances[0]!.sent.map((s) => JSON.parse(s))
    expect(frames[1]).toMatchObject({ v: 1, cmd: 'game.fire', seq: 2, data: { row: 3, col: 4 } })
    expect(frames[2]).toMatchObject({ v: 1, cmd: 'game.place', seq: 3, data: { planes: [{ row: 0, col: 0 }] } })
    expect(frames).toHaveLength(3)
    sock.close()
  })

  it('profile.now → ready（合成，playerId=userId）+ profile（含 coins.balance）', () => {
    const sock = connectSocket({ url: 'ws://x', playerId: 'p1', nickname: () => 'nick' })
    FakeWS.instances[0]!.open()
    const got: unknown[] = []
    sock.onMessage((m) => got.push(m))
    FakeWS.instances[0]!.emit('profile.now', {
      userId: 42,
      nickname: '大鸟',
      rank: { tier: 2, stars: 3, lossStreak: 0, wins: 5, losses: 1, totalHits: 30, bestTier: 2, bestStars: 3, streak: 2, scoringGames: 6 },
      coins: { balance: 120 },
      season: 1,
    })
    expect(got).toMatchObject([
      { type: 'ready', playerId: '42', nickname: '大鸟' },
      { type: 'profile', profile: { nickname: '大鸟', rank: { tier: 2, stars: 3 }, coins: 120, recent: [] } },
    ])
    // 再推一次只出 profile，不再合成 ready
    got.length = 0
    FakeWS.instances[0]!.emit('profile.now', { userId: 42, nickname: '大鸟', season: 1 })
    expect(got).toMatchObject([{ type: 'profile' }])
    sock.close()
  })

  it('table.state 双形态：裸桌子 → tableState；{table,game} 快照 → state', () => {
    const sock = connectSocket({ url: 'ws://x', playerId: 'p1', nickname: () => 'nick' })
    FakeWS.instances[0]!.open()
    const got: unknown[] = []
    sock.onMessage((m) => got.push(m))
    FakeWS.instances[0]!.emit('table.state', { roomCode: 'ABCD', phase: 'waiting' })
    FakeWS.instances[0]!.emit('table.state', { table: { roomCode: 'ABCD', phase: 'inGame' }, game: { phase: 'placing' } })
    expect(got).toMatchObject([
      { type: 'tableState', table: { roomCode: 'ABCD' } },
      { type: 'state', table: { roomCode: 'ABCD' }, game: { phase: 'placing' } },
    ])
    sock.close()
  })

  it('错误码收敛映射：QUOTA_EXCEEDED 按 message 分广告/门票，BALANCE_LOW → NOT_ENOUGH_COINS', () => {
    const sock = connectSocket({ url: 'ws://x', playerId: 'p1', nickname: () => 'nick' })
    FakeWS.instances[0]!.open()
    const got: { type: string; code?: string }[] = []
    sock.onMessage((m) => got.push(m as { type: string; code?: string }))
    FakeWS.instances[0]!.emit('error', { code: 'QUOTA_EXCEEDED', message: '今日广告奖励次数已用完' })
    FakeWS.instances[0]!.emit('error', { code: 'QUOTA_EXCEEDED', message: '今天门票局次数已用完' })
    FakeWS.instances[0]!.emit('error', { code: 'BALANCE_LOW', message: '金币不足' })
    expect(got.map((g) => g.code)).toEqual(['AD_LIMIT', 'DAILY_TICKET_LIMIT', 'NOT_ENOUGH_COINS'])
    sock.close()
  })

  it('重连退避与 ready 重新合成（评审 I7 的新协议等价物）', () => {
    const sock = connectSocket({ url: 'ws://x', playerId: 'p1', nickname: () => 'nick' })
    FakeWS.instances[0]!.open()
    const got: unknown[] = []
    sock.onMessage((m) => got.push(m))
    FakeWS.instances[0]!.emit('profile.now', { userId: 42, nickname: '甲', season: 1 })
    expect(got[0]).toMatchObject({ type: 'ready' })

    FakeWS.instances[0]!.onclose!({ code: 1006 })
    vi.advanceTimersByTime(1000)
    expect(FakeWS.instances).toHaveLength(2)
    FakeWS.instances[1]!.open()
    got.length = 0
    FakeWS.instances[1]!.emit('profile.now', { userId: 42, nickname: '甲', season: 1 })
    expect(got[0]).toMatchObject({ type: 'ready' }) // 重连后再合成一次
    sock.close()
  })

  it('过期判定纯函数：从未认证成功 + 尝试 ≥3 才停；成功过就永远重连', () => {
    expect(shouldStopReconnectAsExpired(false, 0)).toBe(false)
    expect(shouldStopReconnectAsExpired(false, 2)).toBe(false)
    expect(shouldStopReconnectAsExpired(false, 3)).toBe(true)
    expect(shouldStopReconnectAsExpired(true, 99)).toBe(false)
    expect(shouldStopReconnectAsExpired(false, 5, 5)).toBe(true) // threshold 可配
  })

  it('从未认证成功：第 3 次重连尝试失败后放 onExpired 并停止重连', () => {
    const onExpired = vi.fn()
    const sock = connectSocket({ url: 'ws://x', playerId: 'p1', nickname: () => 'nick', onExpired })
    // 首连失败 → 依次安排重连 1/2/3（退避 1s/2s/4s）；第 3 次仍失败 → 放弃
    FakeWS.instances[0]!.onclose!({ code: 1006 })
    vi.advanceTimersByTime(1000)
    expect(onExpired).not.toHaveBeenCalled()
    FakeWS.instances[1]!.onclose!({ code: 1006 })
    vi.advanceTimersByTime(2000)
    expect(onExpired).not.toHaveBeenCalled()
    FakeWS.instances[2]!.onclose!({ code: 1006 })
    vi.advanceTimersByTime(4000)
    expect(FakeWS.instances).toHaveLength(4) // 第 3 次重连已发起
    expect(onExpired).not.toHaveBeenCalled()
    FakeWS.instances[3]!.onclose!({ code: 1006 }) // 第 3 次重连也失败 → 触顶
    expect(onExpired).toHaveBeenCalledTimes(1)
    // 已停止：不再安排第 4 次连接
    vi.advanceTimersByTime(60000)
    expect(FakeWS.instances).toHaveLength(4)
    expect(onExpired).toHaveBeenCalledTimes(1)
    sock.close()
  })

  it('认证成功过一次的连接：无限重连，绝不触发 onExpired', () => {
    const onExpired = vi.fn()
    const sock = connectSocket({ url: 'ws://x', playerId: 'p1', nickname: () => 'nick', onExpired })
    FakeWS.instances[0]!.open()
    FakeWS.instances[0]!.emit('profile.now', { userId: 42, nickname: '甲', season: 1 })
    for (let i = 0; i < 6; i++) {
      FakeWS.instances[i]!.onclose!({ code: 1006 })
      vi.advanceTimersByTime(8000)
    }
    expect(FakeWS.instances).toHaveLength(7) // 一直在重连
    expect(onExpired).not.toHaveBeenCalled()
    sock.close()
  })
})
