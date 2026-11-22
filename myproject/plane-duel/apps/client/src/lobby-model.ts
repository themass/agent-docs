/**
 * 大厅展示模型（spec §20.6、§20.5）：把服务端消息折算成列表文案。
 * 纯函数、无状态，因此可以单测；页面只做绑定。
 */

import { BOT_ID_PREFIX } from '@plane-duel/shared'
import type { RoomListEntry, SeatView, TableView } from '@plane-duel/shared'
import { ruleSummary } from './rule-editor-model'

export type RoomListRow = {
  tableId: string
  title: string
  summary: string
  seatsText: string
  full: boolean
}

/** 列表行：顺序保持服务端给的顺序（排序是服务端的职责）。 */
export function roomListRows(entries: readonly RoomListEntry[]): RoomListRow[] {
  return entries.map((e) => ({
    tableId: e.tableId,
    title: `${e.hostNickname} 的房间`,
    summary: ruleSummary(e.rules),
    seatsText: `${e.seated}/${e.capacity}`,
    full: e.seated >= e.capacity,
  }))
}

/**
 * 匹配补位倒计时文案（spec §20.5）。
 * - 真人未达下限（humansNeeded > 0）：等待真人，不补位；
 * - botFillAt 为 null（补位关闭或还没资格）：无文案；
 * - 到点前后分别是"正在补位"和"X 秒后补位"。
 */
export function botFillText(q: { waiting: number; humansNeeded: number; botFillAt: number | null }, now: number): string | null {
  if (q.humansNeeded > 0) {
    const humans = q.waiting + q.humansNeeded
    return `等待真人 ${q.waiting}/${humans}`
  }
  if (q.botFillAt === null) return null
  const remain = q.botFillAt - now
  if (remain <= 0) return '正在由电脑补位…'
  return `${Math.ceil(remain / 1000)} 秒后由电脑补位（对局会标注 🤖）`
}

/** 座位显示名：电脑加 🤖 前缀（spec §20.4：对局里必须能看出是电脑）。 */
export function seatLabel(seat: SeatView): string {
  return seat.bot ? `🤖 ${seat.nickname}` : seat.nickname
}

/** 兼容 playerId 前缀与座位标记两种口径，取其一即算有电脑。 */
export function hasBots(table: TableView): boolean {
  return table.seats.some((s) => s !== null && (s.bot || s.playerId.startsWith(BOT_ID_PREFIX)))
}

/** 混战对手状态（M2）：出局最优先，其次本轮已提交，再次在线思考中，最后掉线。 */
export function peerStatus(o: { alive: boolean; submitted: boolean; connected: boolean }): '出局' | '✓' | '思考中' | '掉线' {
  if (!o.alive) return '出局'
  if (o.submitted) return '✓'
  return o.connected ? '思考中' : '掉线'
}

/** 房主可移出的座位：好友房、等候中、非自己、非电脑、还没准备（spec §20.6）。 */
export function canKick(table: TableView, me: string, seat: SeatView): boolean {
  return (
    table.kind === 'friend' &&
    table.hostId === me &&
    table.phase === 'waiting' &&
    seat.playerId !== me &&
    !seat.bot &&
    !seat.ready
  )
}
