/**
 * 游戏 HTTP 读接口（/api/game/v1/**，鉴权同 WS：Vpn-Token）。
 *
 * WS 的 profile.now 刻意不带 recent（对局历史见 api.md），档案页的近期战绩
 * 从这里拉：GET /matches/recent → GameResponse<List<MatchBrief>>（服务端
 * GameProfileService.MatchBrief），映射成 shared 的 GameSummary 喂 ProfileSheet。
 */

import type { Capacity, GameSummary, Mode, PresetId } from '@plane-duel/shared'
import { defaultWsUrl } from './socket'

/**
 * 基址策略：
 * - VITE_API_BASE 显式覆盖优先；
 * - 原生壳（Capacitor，origin 是 capacitor://localhost）：从 WS 地址推导绝对地址
 *   （wss://host/vvv/api/game/ws → https://host/vvv/api/game/v1）；原生 fetch 无 CORS；
 * - 浏览器：同源相对 /vvv/api/game/v1——H5 与 API 同一 nginx 部署（自定义头
 *   Vpn-Token 跨域会被 CORS 预检拦，同源最省事）；dev 由 vite proxy 转发（vite.config.ts）。
 */
export function defaultApiBase(): string {
  if (import.meta.env.VITE_API_BASE) return import.meta.env.VITE_API_BASE
  if (typeof location !== 'undefined' && !/^https?:$/.test(location.protocol)) {
    const u = new URL(defaultWsUrl())
    return `${u.protocol === 'wss:' ? 'https:' : 'http:'}//${u.host}${u.pathname.replace(/\/ws$/, '/v1')}`
  }
  return '/vvv/api/game/v1'
}

type MatchBrief = {
  matchId: string
  mode: string
  preset: string
  capacity: number
  startedAtMs: number
  endedAtMs: number
  finalRank: number
  hits: number
  deltaStar: number
  win: number
  scoring: number
}

type GameResponse<T> = { errno: number; data: T | null; error: string | null }

/** 拉近期战绩（只含 finished=1 的局）；失败抛错由调用方静默处理（档案页有空态兜底）。 */
export async function fetchRecent(token: string, limit = 10): Promise<GameSummary[]> {
  const res = await fetch(`${defaultApiBase()}/matches/recent?limit=${limit}`, {
    headers: { 'Vpn-Token': token },
  })
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  const body = (await res.json()) as GameResponse<MatchBrief[]>
  if (body.errno !== 0 || body.data === null) throw new Error(body.error ?? 'errno ' + body.errno)
  return body.data.map((m): GameSummary => ({
    id: m.matchId,
    at: m.startedAtMs,
    mode: m.mode as Mode,
    preset: m.preset as PresetId,
    capacity: m.capacity as Capacity,
    rank: m.finalRank,
    // 服务端 scoring=0 ⇔ 有电脑参与（人机/练习局）
    withBots: m.scoring === 0,
    win: m.win === 1,
    hits: m.hits,
    delta: m.deltaStar,
  }))
}
