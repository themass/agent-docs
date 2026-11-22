/**
 * 多队列随机匹配（spec §19.7、§20.5）。
 *
 * 队列按 (人数, 档位) 分开；凑满人数即成组，按入队顺序。
 * 队列为空是新游戏常态：
 * - 真人不足 MIN_HUMANS 时可以无限等（只发"等待真人"语义的 queueStatus，不补位、不 timeout）。
 * - 真人达到 MIN_HUMANS 后，以"第 2 人的入队时刻"起算补位倒计时；到点整队成组，
 *   缺的座位由 Hub 补电脑（botSeats）。倒计时对全队可见（queueStatus.botFillAt）。
 * - 补位关闭时退回 P1 行为：等待超 enqueueWaitMs 发一次 queueTimeout，不强制出队。
 *
 * 本类不持有牌桌、不生成房间号：成组结果交给 Hub 建 match 桌并统一生成房间号。
 */

import { INITIAL_MMR, matchRelaxGate, type Capacity, type PresetId, type ServerMessage, type TicketId } from '@plane-duel/shared'

export type Outbound = { to: string; msg: ServerMessage }
/** P4：门票档进队列键（spec §廿二.3）；缺省 = free，v4 调用方不受影响 */
export type QueueKey = { capacity: Capacity; preset: PresetId; ticket?: TicketId }
/** 凑满真人时 botSeats = 0；补位成组时 = capacity − 真人数。 */
export type MatchGroup = { key: QueueKey; playerIds: string[]; botSeats: number }

/** 补位倒计时（spec §20.5 用户裁定）：2/3 人桌 30 秒，4 人桌 45 秒。 */
export const BOT_FILL_AFTER_MS: Readonly<Record<Capacity, number>> = { 2: 30_000, 3: 30_000, 4: 45_000 }
/** 少于这个真人数量就永远不补位——不能让一个真人面对三个电脑还以为匹配到了真人。 */
export const MIN_HUMANS = 2

export type MatchmakingOptions = {
  /** 等待多久后提示一次"暂时没有对手"（仅补位关闭时生效）。默认 60000 */
  enqueueWaitMs?: number
  /**
   * 补位倒计时；默认 null = 关闭补位。
   * 传 BOT_FILL_AFTER_MS（按桌型）或一个数字（全桌型同值）开启。
   */
  botFillMs?: number | Readonly<Record<Capacity, number>> | null
}

type Entry = { playerId: string; since: number; notified: boolean; mmr: number }

const keyOf = (k: QueueKey): string => `${k.capacity}:${k.preset}:${k.ticket ?? 'free'}`

export class Matchmaking {
  private readonly queues = new Map<string, { key: QueueKey; entries: Entry[] }>()
  private readonly byPlayer = new Map<string, QueueKey>()
  private readonly enqueueWaitMs: number
  private readonly botFillMs: ((capacity: Capacity) => number) | null

  constructor(opts: MatchmakingOptions) {
    this.enqueueWaitMs = opts.enqueueWaitMs ?? 60_000
    const fill = opts.botFillMs ?? null
    this.botFillMs =
      fill === null ? null : typeof fill === 'number' ? () => fill : (capacity) => BOT_FILL_AFTER_MS[capacity]
  }

  queueOf(playerId: string): QueueKey | null {
    return this.byPlayer.get(playerId) ?? null
  }

  size(key: QueueKey): number {
    return this.queues.get(keyOf(key))?.entries.length ?? 0
  }

  /** mmr 用于分桶匹配（spec §21.2）；缺省按新号初始分。 */
  join(playerId: string, key: QueueKey, now: number, mmr = INITIAL_MMR): { out: Outbound[]; group: MatchGroup | null } {
    const current = this.byPlayer.get(playerId)
    if (current && keyOf(current) === keyOf(key)) return { out: [], group: null }

    const out = this.leave(playerId, now)
    const k = keyOf(key)
    let q = this.queues.get(k)
    if (!q) {
      q = { key: { capacity: key.capacity, preset: key.preset, ticket: key.ticket }, entries: [] }
      this.queues.set(k, q)
    }
    q.entries.push({ playerId, since: now, notified: false, mmr })
    this.byPlayer.set(playerId, q.key)

    let group: MatchGroup | null = null
    if (q.entries.length >= q.key.capacity) {
      const taken = this.formGroup(q, now, q.key.capacity)
      if (taken !== null) {
        this.take(q, taken)
        group = { key: q.key, playerIds: taken.map((e) => e.playerId), botSeats: 0 }
        // 成组者不再收队列状态；新的 tableState 由 Hub 下发
        if (q.entries.length > 0) out.push(...this.status(q.key, q.entries))
      } else {
        // 满员但分桶不兼容（隔 ≥2 桶永不放行）：继续等更合适的对手，宁等不错配
        out.push(...this.status(q.key, q.entries))
      }
    } else {
      out.push(...this.status(q.key, q.entries))
    }
    if (q.entries.length === 0) this.queues.delete(k)
    return { out, group }
  }

  leave(playerId: string, _now: number): Outbound[] {
    const key = this.byPlayer.get(playerId)
    if (!key) return []
    this.byPlayer.delete(playerId)
    const k = keyOf(key)
    const q = this.queues.get(k)
    if (!q) return []
    q.entries = q.entries.filter((e) => e.playerId !== playerId)
    if (q.entries.length === 0) {
      this.queues.delete(k)
      return []
    }
    return this.status(q.key, q.entries)
  }

  /**
   * 推进计时。补位开启且真人 ≥ MIN_HUMANS 且倒计时到点 → 整队成组（botSeats = 缺的座位数）。
   * 补位关闭时只做 P1 的 queueTimeout 提示。
   */
  tick(now: number): { out: Outbound[]; groups: MatchGroup[] } {
    const out: Outbound[] = []
    const groups: MatchGroup[] = []
    for (const q of [...this.queues.values()]) {
      if (this.botFillMs !== null) {
        // 真人满员先按分桶成组（spec §21.2）
        while (q.entries.length >= q.key.capacity) {
          const taken = this.formGroup(q, now, q.key.capacity)
          if (taken === null) break
          this.take(q, taken)
          groups.push({ key: q.key, playerIds: taken.map((e) => e.playerId), botSeats: 0 })
        }
        if (q.entries.length === 0) {
          this.queues.delete(keyOf(q.key))
          continue
        }
        // 仍满员 = 分桶闸门不放行（隔 ≥2 桶）：继续等，不硬凑成"零电脑的真人居段局"
        if (q.entries.length >= q.key.capacity) continue
        if (q.entries.length < MIN_HUMANS) continue
        const anchor = q.entries[MIN_HUMANS - 1]!
        if (now - anchor.since < this.botFillMs(q.key.capacity)) continue
        const taken = q.entries.splice(0, q.entries.length)
        for (const e of taken) this.byPlayer.delete(e.playerId)
        groups.push({ key: q.key, playerIds: taken.map((e) => e.playerId), botSeats: q.key.capacity - taken.length })
        if (q.entries.length === 0) this.queues.delete(keyOf(q.key))
        continue
      }
      // 补位关闭（P1 语义）：同样先按分桶凑满，再走 queueTimeout 提示
      while (q.entries.length >= q.key.capacity) {
        const taken = this.formGroup(q, now, q.key.capacity)
        if (taken === null) break
        this.take(q, taken)
        groups.push({ key: q.key, playerIds: taken.map((e) => e.playerId), botSeats: 0 })
      }
      if (q.entries.length === 0) {
        this.queues.delete(keyOf(q.key))
        continue
      }
      for (const e of q.entries) {
        if (!e.notified && now - e.since >= this.enqueueWaitMs) {
          e.notified = true
          out.push({ to: e.playerId, msg: { type: 'queueTimeout' } })
        }
      }
    }
    return { out, groups }
  }

  /**
   * 从队首凑 count 个互相放行（matchRelaxGate，等待时长按各自入队时刻）的人。
   * 贪心：按入队顺序取人，逐个与已选集合校验。凑不齐返回 null（不部分成组）。
   */
  private formGroup(q: { entries: Entry[] }, now: number, count: number): Entry[] | null {
    const picked: Entry[] = []
    for (const e of q.entries) {
      if (picked.length === count) break
      const waited = now - e.since
      const okWith = picked.every((p) => matchRelaxGate(p.mmr, e.mmr, Math.min(waited, now - p.since)))
      if (okWith) picked.push(e)
    }
    return picked.length === count ? picked : null
  }

  private take(q: { entries: Entry[] }, picked: Entry[]): void {
    const ids = new Set(picked.map((e) => e.playerId))
    q.entries = q.entries.filter((e) => !ids.has(e.playerId))
    for (const e of picked) this.byPlayer.delete(e.playerId)
  }

  /** 补位倒计时：以"第 MIN_HUMANS 个真人的入队时刻"起算，第 3、4 人入队不重置。 */
  private botFillAt(key: QueueKey, entries: Entry[]): number | null {
    if (this.botFillMs === null || entries.length < MIN_HUMANS) return null
    return entries[MIN_HUMANS - 1]!.since + this.botFillMs(key.capacity)
  }

  private status(key: QueueKey, entries: Entry[]): Outbound[] {
    const waiting = entries.length
    const botFillAt = this.botFillAt(key, entries)
    const humansNeeded = Math.max(0, MIN_HUMANS - waiting)
    return entries.map((e) => ({
      to: e.playerId,
      msg: { type: 'queueStatus', capacity: key.capacity, preset: key.preset, waiting, botFillAt, humansNeeded, ...(key.ticket !== undefined ? { ticket: key.ticket } : {}) },
    }))
  }
}
