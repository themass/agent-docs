import { describe, it, expect } from 'vitest'
import type { GameView, RoomListEntry, RuleSet, ServerMessage, TableView, TableResult } from '@plane-duel/shared'
import { createGameStore } from '../src/net/store'

const rules: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: true }

const mkTable = (over: Partial<TableView> = {}): TableView => ({
  roomCode: '123456',
  kind: 'friend',
  capacity: 2,
  rules,
  rulesVersion: 0,
  listed: false,
  hostId: 'me',
  phase: 'waiting',
  seats: [
    { seat: 0, playerId: 'me', nickname: '我', ready: false, connected: true, bot: false },
    { seat: 1, playerId: 'op', nickname: '他', ready: false, connected: true, bot: false },
  ],
  lastResult: null,
  ...over,
})

const result = (winner: string): TableResult => ({
  reason: 'head',
  botIds: [],
  ranking: [
    { playerId: winner, rank: 1, eliminatedRound: null, hits: 3 },
    { playerId: winner === 'me' ? 'op' : 'me', rank: 2, eliminatedRound: null, hits: 1 },
  ],
})

const duelGame = (over: Partial<GameView> = {}): GameView => ({
  mode: 'duel',
  phase: 'playing',
  deadlineAt: 100,
  turn: 'me',
  round: null,
  you: { planes: [{ row: 3, col: 3 }], planesDestroyed: 0, alive: true, shots: [], incoming: [], submitted: false, pendingShot: null },
  others: [{ playerId: 'op', connected: true, alive: true, planesDestroyed: 0, submitted: false }],
  ...over,
})

const meleeGame = (over: Partial<GameView> = {}): GameView => ({
  mode: 'melee',
  phase: 'playing',
  deadlineAt: 100,
  turn: null,
  round: 1,
  you: { planes: [{ row: 3, col: 3 }], planesDestroyed: 0, alive: true, shots: [], incoming: [], submitted: false, pendingShot: null },
  others: ['a', 'b', 'c'].map((id) => ({
    playerId: id, connected: true, alive: true, planesDestroyed: 0, submitted: false,
  })),
  ...over,
})

const withGame = (game: GameView, table: TableView = mkTable({ phase: 'inGame' })) => {
  const s = createGameStore()
  s.apply({ type: 'ready', playerId: 'me', token: 't', nickname: '我' })
  s.apply({ type: 'state', table, game })
  return s
}

describe('store v2', () => {
  it('ready 记录 playerId 与昵称', () => {
    const s = createGameStore()
    s.apply({ type: 'ready', playerId: 'me', token: 't', nickname: '勇敢的海鸥' })
    expect(s.state.playerId).toBe('me')
    expect(s.state.nickname).toBe('勇敢的海鸥')
  })

  it('tableState 替换 table；lastResult 变化时 resultDismissed 重置', () => {
    const s = createGameStore()
    s.apply({ type: 'tableState', table: mkTable() })
    expect(s.state.table?.roomCode).toBe('123456')
    s.apply({ type: 'tableState', table: mkTable({ lastResult: result('me') }) })
    expect(s.state.resultDismissed).toBe(false)
    s.state.resultDismissed = true
    // 内容相同的 lastResult（新对象）不重置
    s.apply({ type: 'tableState', table: mkTable({ lastResult: result('me') }) })
    expect(s.state.resultDismissed).toBe(true)
    // lastResult 变化 → 重置
    s.apply({ type: 'tableState', table: mkTable({ lastResult: result('op') }) })
    expect(s.state.resultDismissed).toBe(false)
  })

  it('duel：shotResult 写入 game.you.shots（targetId=对手）或 game.you.incoming，并更新 turn', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'shotResult', by: 'me', row: 1, col: 1, result: 'miss', planeId: 'p0', nextTurn: 'op' })
    expect(s.state.game!.you.shots).toEqual([{ targetId: 'op', row: 1, col: 1, result: 'miss', planeId: 'p0' }])
    expect(s.state.game!.you.incoming).toEqual([])
    expect(s.state.game!.turn).toBe('op')
    s.apply({ type: 'shotResult', by: 'op', row: 2, col: 2, result: 'body', planeId: 'p0', nextTurn: 'me' })
    expect(s.state.game!.you.incoming).toEqual([{ by: 'op', row: 2, col: 2, result: 'body', planeId: 'p0' }])
    expect(s.state.game!.you.shots).toHaveLength(1)
    expect(s.state.game!.turn).toBe('me')
  })

  it('duel：planeDestroyed 累加被击落一方的 planesDestroyed', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'planeDestroyed', ownerId: 'op', planeId: 'p0' })
    expect(s.state.game!.others[0]!.planesDestroyed).toBe(1)
    s.apply({ type: 'planeDestroyed', ownerId: 'me', planeId: 'p0' })
    expect(s.state.game!.you.planesDestroyed).toBe(1)
  })

  it('melee：roundResult 追加本人的 shots/incoming，更新 others 的 planesDestroyed 与 alive，清空所有 submitted', () => {
    const s = withGame(meleeGame())
    s.apply({ type: 'submitted', playerId: 'a', round: 1 })
    s.apply({ type: 'submitted', playerId: 'b', round: 1 })
    const msg: ServerMessage = {
      type: 'roundResult',
      round: 1,
      shots: [{ targetId: 'a', row: 4, col: 4, result: 'body', planeId: 'p0' }],
      incoming: [{ by: 'b', row: 3, col: 3, result: 'miss', planeId: 'p0' }],
      destroyed: [{ playerId: 'a', planesDestroyed: 1 }],
      eliminated: ['a'],
    }
    s.apply(msg)
    const g = s.state.game!
    expect(g.you.shots).toHaveLength(1)
    expect(g.you.incoming).toHaveLength(1)
    const a = g.others.find((o) => o.playerId === 'a')!
    expect(a.planesDestroyed).toBe(1)
    expect(a.alive).toBe(false)
    expect(g.others.find((o) => o.playerId === 'b')!.alive).toBe(true)
    expect(g.others.every((o) => !o.submitted)).toBe(true)
    // 第二轮继续追加
    s.apply({ ...msg, round: 2, destroyed: [], eliminated: [] } as ServerMessage)
    expect(s.state.game!.you.shots).toHaveLength(2)
  })

  it('melee：自己被淘汰时 you.alive=false', () => {
    const s = withGame(meleeGame())
    s.apply({ type: 'roundResult', round: 1, shots: [], incoming: [], destroyed: [], eliminated: ['me'] })
    expect(s.state.game!.you.alive).toBe(false)
  })

  it('melee：submitted 只把对应玩家标记为已开炮', () => {
    const s = withGame(meleeGame())
    s.apply({ type: 'submitted', playerId: 'b', round: 1 })
    const sub = s.state.game!.others.map((o) => [o.playerId, o.submitted])
    expect(sub).toEqual([['a', false], ['b', true], ['c', false]])
  })

  it('presence 更新 others[i].connected', () => {
    const s = withGame(meleeGame())
    s.apply({ type: 'presence', playerId: 'c', connected: false })
    expect(s.state.game!.others[2]!.connected).toBe(false)
    expect(s.state.game!.others[0]!.connected).toBe(true)
    s.apply({ type: 'presence', playerId: 'c', connected: true })
    expect(s.state.game!.others[2]!.connected).toBe(true)
  })

  it('presence 同步 table.seats[].connected', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'presence', playerId: 'op', connected: false })
    expect(s.state.table!.seats[1]!.connected).toBe(false)
  })

  it('phaseChanged 更新 game.phase/deadlineAt/turn/round；paused 不清 game', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'phaseChanged', phase: 'paused', deadlineAt: null })
    expect(s.state.game).not.toBeNull()
    expect(s.state.game!.phase).toBe('paused')
    expect(s.state.game!.deadlineAt).toBeNull()
    expect(s.state.game!.you.planes).toHaveLength(1)
    s.apply({ type: 'phaseChanged', phase: 'playing', deadlineAt: 5000, turn: 'op' })
    expect(s.state.game!.phase).toBe('playing')
    expect(s.state.game!.deadlineAt).toBe(5000)
    expect(s.state.game!.turn).toBe('op')

    const m = withGame(meleeGame())
    m.apply({ type: 'phaseChanged', phase: 'playing', deadlineAt: 777, round: 2 })
    expect(m.state.game!.round).toBe(2)
    expect(m.state.game!.deadlineAt).toBe(777)
    expect(m.state.game!.turn).toBeNull()
  })

  it('state 整体替换 table 与 game', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'shotResult', by: 'me', row: 1, col: 1, result: 'miss', planeId: 'p0', nextTurn: 'op' })
    const fresh = duelGame({ turn: 'op', deadlineAt: 42 })
    s.apply({ type: 'state', table: mkTable({ roomCode: '654321', phase: 'inGame' }), game: fresh })
    expect(s.state.table!.roomCode).toBe('654321')
    expect(s.state.game!.deadlineAt).toBe(42)
    expect(s.state.game!.you.shots).toEqual([])
  })

  it('state 的 game 为 null 时清空 game', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'state', table: mkTable(), game: null })
    expect(s.state.game).toBeNull()
  })

  it('开局时 tableState 在 state 之前到来：state 覆盖，game 不被误清', () => {
    const s = createGameStore()
    s.apply({ type: 'tableState', table: mkTable({ phase: 'inGame' }) })
    s.apply({ type: 'state', table: mkTable({ phase: 'inGame' }), game: duelGame() })
    expect(s.state.game).not.toBeNull()
  })

  it('gameOver 后 game.phase = finished', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'gameOver', result: result('me') })
    expect(s.state.game!.phase).toBe('finished')
    expect(s.state.game!.deadlineAt).toBeNull()
  })

  it('对局结束后 tableState(waiting, lastResult) 保留 game 供结算页，并重置 resultDismissed', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'gameOver', result: result('me') })
    s.state.resultDismissed = true
    s.apply({ type: 'tableState', table: mkTable({ phase: 'waiting', lastResult: result('me') }) })
    expect(s.state.table!.phase).toBe('waiting')
    expect(s.state.table!.lastResult).not.toBeNull()
    expect(s.state.game!.phase).toBe('finished')
    expect(s.state.resultDismissed).toBe(false)
  })

  it('换到另一个牌桌（roomCode 不同）时丢弃旧 game', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'tableState', table: mkTable({ roomCode: '999999' }) })
    expect(s.state.game).toBeNull()
  })

  it('queueStatus 写入 queue；tableState 到来时清空 queue', () => {
    const s = createGameStore()
    s.apply({ type: 'queueStatus', capacity: 3, preset: 'standard', waiting: 2, botFillAt: null, humansNeeded: 0 })
    expect(s.state.queue).toEqual({ capacity: 3, preset: 'standard', waiting: 2, botFillAt: null, humansNeeded: 0 })
    s.apply({ type: 'tableState', table: mkTable() })
    expect(s.state.queue).toBeNull()
  })

  it('queueTimeout 置 queueTimedOut 并清空 queue', () => {
    const s = createGameStore()
    s.apply({ type: 'queueStatus', capacity: 2, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1 })
    s.apply({ type: 'queueTimeout' })
    expect(s.state.queueTimedOut).toBe(true)
    expect(s.state.queue).toBeNull()
    s.apply({ type: 'queueStatus', capacity: 2, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1 })
    expect(s.state.queueTimedOut).toBe(false)
  })

  it('roomClosed 标记；进入新牌桌时清除', () => {
    const s = createGameStore()
    s.apply({ type: 'roomClosed' })
    expect(s.state.roomClosed).toBe(true)
    s.apply({ type: 'tableState', table: mkTable() })
    expect(s.state.roomClosed).toBe(false)
  })

  it('resetToLobby 清空牌桌与对局，保留 playerId 与昵称', () => {
    const s = withGame(duelGame())
    s.resetToLobby()
    expect(s.state.table).toBeNull()
    expect(s.state.game).toBeNull()
    expect(s.state.queue).toBeNull()
    expect(s.state.playerId).toBe('me')
    expect(s.state.nickname).toBe('我')
  })

  // ---------- v3：房间列表 / 踢人 / 电脑补位 ----------

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

  it('roomList 写入 state.roomList', () => {
    const s = createGameStore()
    s.apply({ type: 'roomList', capacity: 3, entries: [entry(), entry({ tableId: 't0002' })] })
    expect(s.state.roomList).not.toBeNull()
    expect(s.state.roomList!.capacity).toBe(3)
    expect(s.state.roomList!.entries).toHaveLength(2)
    // 空数组也覆盖（服务端说没了就是没了）
    s.apply({ type: 'roomList', capacity: 3, entries: [] })
    expect(s.state.roomList!.entries).toEqual([])
  })

  it('kicked：回到大厅（table/game 为 null）并给出提示', () => {
    const s = withGame(duelGame({ phase: 'placing' }), mkTable())
    s.apply({ type: 'kicked', roomCode: '123456' })
    expect(s.state.table).toBeNull()
    expect(s.state.game).toBeNull()
    expect(s.state.kicked).toBe(true)
    expect(s.state.error).toBe('你已被房主移出房间')
    expect(s.state.playerId).toBe('me') // 身份保留，可继续玩
  })

  it('M2：playerOut 把对应对手标为出局且清除已开炮标记；随后的 roundResult.eliminated 不重复出错', () => {
    const s = withGame(meleeGame())
    s.apply({ type: 'submitted', playerId: 'b', round: 1 })
    s.apply({ type: 'playerOut', playerId: 'b', round: 1 })
    const b = s.state.game!.others.find((o) => o.playerId === 'b')!
    expect(b.alive).toBe(false)
    expect(b.submitted).toBe(false)
    // 幂等：再收一次同消息不报错
    s.apply({ type: 'playerOut', playerId: 'b', round: 1 })
    expect(b.alive).toBe(false)
    // 同轮 roundResult 再报淘汰同样安全
    s.apply({ type: 'roundResult', round: 1, shots: [], incoming: [], destroyed: [], eliminated: ['b'] })
    expect(b.alive).toBe(false)
  })

  it('M1：state 中 you.submitted=true 时 game.you.submitted 为 true（不依赖本地标记）', () => {
    const s = withGame(meleeGame({ you: { ...meleeGame().you, submitted: true } }))
    expect(s.state.game!.you.submitted).toBe(true)
  })

  it('M1：服务端把自己也广播的 submitted 写回 game.you.submitted（刷新后仍显示已开炮）', () => {
    const s = withGame(meleeGame())
    s.apply({ type: 'submitted', playerId: 'me', round: 1 })
    expect(s.state.game!.you.submitted).toBe(true)
    // 别人的 submitted 不动自己
    const s2 = withGame(meleeGame())
    s2.apply({ type: 'submitted', playerId: 'b', round: 1 })
    expect(s2.state.game!.you.submitted).toBe(false)
    expect(s2.state.game!.others.find((o) => o.playerId === 'b')!.submitted).toBe(true)
  })

  it('评审 B1：roundResult 同时清除自己的 submitted（第二轮还能开炮）', () => {
    const s = withGame(meleeGame())
    s.apply({ type: 'submitted', playerId: 'me', round: 1 })
    s.apply({ type: 'roundResult', round: 1, shots: [], incoming: [], destroyed: [], eliminated: [] })
    expect(s.state.game!.you.submitted).toBe(false)
    // phaseChanged 进入下一轮后依然可开炮
    s.apply({ type: 'phaseChanged', phase: 'playing', deadlineAt: 200, round: 2 })
    expect(s.state.game!.you.submitted).toBe(false)
    // 新一轮再提交又能立起来
    s.apply({ type: 'submitted', playerId: 'me', round: 2 })
    expect(s.state.game!.you.submitted).toBe(true)
  })

  it('queueStatus 带 botFillAt 与 humansNeeded 写入 queue', () => {
    const s = createGameStore()
    s.apply({ type: 'queueStatus', capacity: 2, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1 })
    expect(s.state.queue).toEqual({ capacity: 2, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1 })
    s.apply({ type: 'queueStatus', capacity: 2, preset: 'standard', waiting: 2, botFillAt: 5_000, humansNeeded: 0 })
    expect(s.state.queue).toEqual({ capacity: 2, preset: 'standard', waiting: 2, botFillAt: 5_000, humansNeeded: 0 })
  })

  describe('错误文案', () => {
    const err = (s: ReturnType<typeof createGameStore>, code: string) => {
      s.apply({ type: 'error', code: code as never, message: '' })
      return s.state.error
    }
    it('新增错误码映射', () => {
      const s = createGameStore()
      const cases: Record<string, string> = {
        NOT_HOST: '只有房主可以修改规则',
        ROOM_IN_GAME: '对局进行中',
        ROOM_FULL: '房间已满',
        NOT_IN_QUEUE: '你不在排队中',
        BAD_RULES: '规则不合法',
        OUT_OF_RANGE: '超出棋盘范围',
        WRONG_PHASE: '现在不能这样操作',
        NOT_IN_ROOM: '你不在房间中',
        REPEAT_SHOT: '这一格已经打过了',
        ROOM_NOT_FOUND: '房间不存在',
        TARGET_NOT_FOUND: '该玩家不在房间中',
        TARGET_READY: '对方已准备，不能移出',
        BANNED: '你已被移出该房间，不能再加入',
        STALE_RULES: '房主刚修改了规则，请确认后再准备',
      }
      for (const [code, text] of Object.entries(cases)) expect(err(s, code)).toBe(text)
      expect(err(s, 'SOMETHING_ELSE')).toBe('操作失败')
    })
    it('NOT_YOUR_TURN 按模式区分', () => {
      expect(err(withGame(duelGame()), 'NOT_YOUR_TURN')).toBe('还没轮到你')
      expect(err(withGame(meleeGame()), 'NOT_YOUR_TURN')).toBe('本轮你已开过炮')
      expect(err(createGameStore(), 'NOT_YOUR_TURN')).toBe('还没轮到你')
    })
  })
})

describe('P3 档案消息（spec §21.6）', () => {
  const profile = (over: object = {}): any => ({
    nickname: '我',
    rank: { tier: 1, stars: 2, lossStreak: 0 },
    season: 1,
    stats: { wins: 5, losses: 2, totalHits: 40, bestTier: 1, bestStars: 2, streak: 2, scoringGames: 7 },
    recent: [],
    ...over,
  })

  it('profile 写入 state.profile；rankChanged(scoring) 记 rankFlash', () => {
    const s = createGameStore()
    s.apply({ type: 'profile', profile: profile() })
    expect(s.state.profile?.rank).toEqual({ tier: 1, stars: 2, lossStreak: 0 })
    expect(s.state.rankFlash).toBeNull()
    s.apply({ type: 'rankChanged', delta: 1, rank: { tier: 1, stars: 3, lossStreak: 0 }, reason: 'scoring' })
    expect(s.state.rankFlash).toEqual({ delta: 1, tier: 1, stars: 3 })
  })

  it('rankChanged(season-reset) 不留 rankFlash', () => {
    const s = createGameStore()
    s.apply({ type: 'rankChanged', delta: 0, rank: { tier: 0, stars: 0, lossStreak: 0 }, reason: 'season-reset' })
    expect(s.state.rankFlash).toBeNull()
  })

  it('rankList 带 at 时间戳存缓存', () => {
    const s = createGameStore()
    const before = Date.now()
    s.apply({ type: 'rankList', season: 2, entries: [{ pos: 1, nickname: '甲', tier: 3, stars: 1, wins: 9 }] })
    const rl = s.state.rankList!
    expect(rl.season).toBe(2)
    expect(rl.entries[0]!.nickname).toBe('甲')
    expect(rl.at).toBeGreaterThanOrEqual(before)
  })

  it('新一局 tableState(inGame) 清除 rankFlash；档案与榜单跨桌保留', () => {
    const s = createGameStore()
    s.apply({ type: 'ready', playerId: 'me', token: 't', nickname: '我' })
    s.apply({ type: 'profile', profile: profile() })
    s.apply({ type: 'rankList', season: 1, entries: [] })
    s.apply({ type: 'rankChanged', delta: 1, rank: { tier: 1, stars: 3, lossStreak: 0 }, reason: 'scoring' })
    s.apply({ type: 'tableState', table: mkTable({ phase: 'inGame' }) })
    expect(s.state.rankFlash).toBeNull()
    expect(s.state.profile).not.toBeNull()
    expect(s.state.rankList).not.toBeNull()
    // resetToLobby 同样保留
    s.resetToLobby()
    expect(s.state.profile?.stats.wins).toBe(5)
    expect(s.state.rankList).not.toBeNull()
  })
})

describe('P4 金币消息（spec §廿二.6）', () => {
  const daily = { day: '2026-11-20', loginDone: true, gameGrants: 1, ticketPlays: 0, adGrants: 0, netGain: 55 }

  it('profile 镜像余额；coins 写快照；coinsChanged 推余额并按 reason 记 flash', () => {
    const s = createGameStore()
    s.apply({ type: 'profile', profile: { nickname: '我', rank: { tier: 0, stars: 0, lossStreak: 0 }, season: 1, stats: { wins: 0, losses: 0, totalHits: 0, bestTier: 0, bestStars: 0, streak: 0, scoringGames: 0 }, recent: [], coins: 50 } } as never)
    expect(s.state.coins).toBe(50)
    s.apply({ type: 'coins', balance: 55, ledger: [{ id: 'game:g1', at: 1, delta: 5, reason: 'game' }], daily } as never)
    expect(s.state.coins).toBe(55)
    expect(s.state.coinLedger!.entries).toHaveLength(1)
    expect(s.state.coinLedger!.daily.netGain).toBe(55)
    s.apply({ type: 'coinsChanged', delta: -50, reason: 'ticket-fee', balance: 5 } as never)
    expect(s.state.coins).toBe(5)
    expect(s.state.coinFlash).toEqual({ delta: -50, reason: 'ticket-fee' })
  })

  it('login/ad 不记 coinFlash（结算页只报对局相关的钱）', () => {
    const s = createGameStore()
    s.apply({ type: 'coinsChanged', delta: 50, reason: 'login', balance: 50 } as never)
    expect(s.state.coins).toBe(50)
    expect(s.state.coinFlash).toBeNull()
    s.apply({ type: 'coinsChanged', delta: 30, reason: 'ad', balance: 80 } as never)
    expect(s.state.coins).toBe(80)
    expect(s.state.coinFlash).toBeNull()
    s.apply({ type: 'coinsChanged', delta: 80, reason: 'ticket-win', balance: 160 } as never)
    expect(s.state.coinFlash).toEqual({ delta: 80, reason: 'ticket-win' })
  })

  it('新一局 tableState(inGame) 同时清 rankFlash 与 coinFlash', () => {
    const s = createGameStore()
    s.apply({ type: 'coinsChanged', delta: 5, reason: 'game', balance: 55 } as never)
    s.apply({ type: 'tableState', table: mkTable({ phase: 'inGame' }) })
    expect(s.state.coinFlash).toBeNull()
  })

  it('resetToLobby 保留余额与账本（回大厅不闪空白）', () => {
    const s = withGame(duelGame())
    s.apply({ type: 'coins', balance: 120, ledger: [], daily } as never)
    s.resetToLobby()
    expect(s.state.coins).toBe(120)
    expect(s.state.coinLedger!.balance).toBe(120)
  })

  it('queueStatus.ticket 只在服务端回显时写入（v4 兼容）', () => {
    const s = createGameStore()
    s.apply({ type: 'queueStatus', capacity: 2, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1 })
    expect(s.state.queue!.ticket).toBeUndefined()
    s.apply({ type: 'queueStatus', capacity: 2, preset: 'standard', waiting: 1, botFillAt: null, humansNeeded: 1, ticket: 'standard' } as never)
    expect(s.state.queue!.ticket).toBe('standard')
  })

  it('P4 错误文案', () => {
    const s = createGameStore()
    s.apply({ type: 'error', code: 'NOT_ENOUGH_COINS', message: '' })
    expect(s.state.error).toBe('金币不足，先打一局攒点吧')
    s.apply({ type: 'error', code: 'DAILY_TICKET_LIMIT', message: '' })
    expect(s.state.error).toBe('今天门票局次数已用完')
    s.apply({ type: 'error', code: 'AD_LIMIT', message: '' })
    expect(s.state.error).toBe('今天的广告奖励次数已用完')
  })
})

describe('评审回归（整枝 #7）', () => {
  it('账本页开着时 coinsChanged 同步 coinLedger.balance，页头不再与金币条矛盾', () => {
    const s = createGameStore()
    const daily = { day: '2026-11-20', loginDone: true, gameGrants: 0, ticketPlays: 0, adGrants: 0, netGain: 50 }
    s.apply({ type: 'coins', balance: 50, ledger: [], daily } as never)
    s.apply({ type: 'coinsChanged', delta: -50, reason: 'ticket-fee', balance: 0 } as never)
    expect(s.state.coins).toBe(0)
    expect(s.state.coinLedger!.balance).toBe(0)
    // 未拉过账本：不凭空创建
    const s2 = createGameStore()
    s2.apply({ type: 'coinsChanged', delta: 50, reason: 'login', balance: 50 } as never)
    expect(s2.state.coinLedger).toBeNull()
  })
})
