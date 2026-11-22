/** Hub 测试共用夹具：假时钟、按会话收件箱、关闭记录。 */
import { Hub } from '../src/hub'
import type { HubOptions } from '../src/hub'
import type { RuleSet, ServerMessage } from '@plane-duel/shared'

export const RULES: RuleSet = { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: false }

export function mkHub(opts: Partial<HubOptions> = {}) {
  let now = 1_000_000
  // 测试夹具默认关闭补位（P1 语义）；补位行为由 hub-p2 测试显式开启
  const hub = new Hub({ clock: { now: () => now }, botFillMs: null, ...opts })
  const inbox = new Map<string, ServerMessage[]>()
  const closed = new Set<string>()
  const recv = (sid: string) => inbox.get(sid) ?? []
  const last = (sid: string, type: string) => recv(sid).filter((m) => m.type === type).at(-1) as any
  const open = (sid: string) => {
    inbox.set(sid, [])
    hub.connect(sid, (m) => inbox.get(sid)!.push(m), () => closed.add(sid))
  }
  const send = (sid: string, msg: unknown) => hub.receive(sid, JSON.stringify(msg))
  /** 新开会话并认证，返回签发的 token（被拒时 undefined）。 */
  const auth = (sid: string, playerId: string, token?: string, nickname?: string) => {
    open(sid)
    send(sid, { type: 'auth', playerId, ...(token ? { token } : {}), ...(nickname !== undefined ? { nickname } : {}) })
    return last(sid, 'ready')?.token as string | undefined
  }
  const advance = (ms: number) => {
    now += ms
    hub.tick()
  }
  /** 最近一次 tableState / state 里的牌桌视图 */
  const tableOf = (sid: string) => {
    const ms = recv(sid).filter((m) => m.type === 'tableState' || m.type === 'state')
    return (ms.at(-1) as any)?.table
  }
  const createRoom = (sid: string, capacity: 2 | 3 | 4 = 2, rules: RuleSet = RULES): string => {
    send(sid, { type: 'createRoom', capacity, rules, listed: false })
    return tableOf(sid).roomCode
  }
  /** v3：setReady 必须带当前规则版本（P1 测试里规则从不改，恒为 0）。 */
  const ready = (sid: string): void => {
    send(sid, { type: 'setReady', ready: true, rulesVersion: tableOf(sid)?.rulesVersion ?? 0 })
  }
  /**
   * 好友房 2 人对局并摆好：alice 在 s1（机头 3,7），bob 在 s2（机头 6,2）。
   */
  const startDuel = () => {
    const ta = auth('s1', 'alice')!
    const tb = auth('s2', 'bob')!
    const code = createRoom('s1')
    send('s2', { type: 'joinRoom', roomCode: code })
    ready('s1')
    ready('s2')
    send('s1', { type: 'placePlane', planes: [{ row: 3, col: 7 }] })
    send('s2', { type: 'placePlane', planes: [{ row: 6, col: 2 }] })
    return { code, ta, tb }
  }
  /** startDuel 之后：轮到谁谁打掉对方机头，对局结束。 */
  const finishDuel = (code: string) => {
    const turn = hub.getTable(code)!.engine!.view('alice').turn
    const [sid, target] = turn === 'alice' ? ['s1', { row: 6, col: 2 }] : ['s2', { row: 3, col: 7 }]
    send(sid, { type: 'fire', ...target })
  }
  return { hub, recv, last, open, auth, send, advance, closed, tableOf, createRoom, ready, startDuel, finishDuel }
}
