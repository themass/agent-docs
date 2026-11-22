/**
 * 服务端进程入口：ws 传输 + Hub（房间表、路由、匹配）。
 *
 * 注意：进程信号处理（优雅停机）在 index.ts——**生产入口必须是 index.ts**
 * （pnpm start / Dockerfile 都走它）。直接跑本文件只剩调试意义，没有 SIGTERM 处理
 * （评审 P5 #6；P4 时信号块误挂在这里导致优雅停机从未生效，见 §廿三.3）。
 */

import { createServer as createHttpServer } from 'node:http'
import { join } from 'node:path'
import { WebSocketServer, type WebSocket } from 'ws'
import type { Capacity, ServerMessage } from '@plane-duel/shared'
import { systemClock, type Clock } from './clock'
import { Hub } from './hub'
import { JsonFileProfileStore } from './profile'

export type ServerHandle = {
  close(): Promise<void>
  port: number
  /** 手动推进一帧（引擎 tick + 匹配 + 列表合并推送）；测试/单进程部署可用。 */
  tick(): void
}

export type ServerOptions = {
  port: number
  /** 默认 127.0.0.1（测试）；部署时传 0.0.0.0 */
  host?: string
  clock?: Clock
  devMode?: boolean
  /** 匹配补位倒计时；不传 = 默认 BOT_FILL_AFTER_MS，显式传 null 关闭（spec §20.5） */
  botFillMs?: number | Readonly<Record<Capacity, number>> | null
  /** 档案文件路径；传 null 用内存存储（测试），不传用 data/profiles.json（spec §21.1） */
  profileFile?: string | null
}

const rawSend = (ws: WebSocket, msg: ServerMessage) => {
  if (ws.readyState === ws.OPEN) ws.send(JSON.stringify(msg))
}

export async function createServer(opts: ServerOptions): Promise<ServerHandle> {
  const clock = opts.clock ?? systemClock
  // P3 档案（spec §21.1）：默认 JSON 文件持久化；显式传 null 用内存（测试/临时）
  const profiles =
    opts.profileFile === null ? undefined : new JsonFileProfileStore(opts.profileFile ?? join(process.cwd(), 'data', 'profiles.json'))
  const hub = new Hub({
    clock,
    devMode: opts.devMode,
    ...(opts.botFillMs !== undefined ? { botFillMs: opts.botFillMs } : {}),
    ...(profiles ? { profiles } : {}),
  })

  const httpServer = createHttpServer((req, res) => {
    // 存活探针（spec §廿三.1.2）：Docker healthcheck 用，单进程无下游依赖，200 即活
    if ((req.url ?? '').split('?')[0] === '/healthz') {
      // 查询串宽容（评审 P5 #7）：/healthz? 不该 404
      res.writeHead(200, { 'content-type': 'text/plain' })
      res.end('ok')
      return
    }
    res.writeHead(404).end()
  })
  // 单条消息上限 4KB：协议里最大的消息也不过百字节（M5，防内存型 DoS）
  const wss = new WebSocketServer({ server: httpServer, maxPayload: 4 * 1024 })
  const alive = new WeakMap<WebSocket, boolean>()

  wss.on('connection', (ws) => {
    const sessionId = `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
    hub.connect(
      sessionId,
      (msg) => rawSend(ws, msg),
      () => ws.close(4000, 'superseded'),
    )
    alive.set(ws, true)
    ws.on('pong', () => alive.set(ws, true))

    ws.on('message', (data) => {
      hub.receive(sessionId, data.toString())
    })

    ws.on('close', () => {
      hub.disconnect(sessionId)
    })

    ws.on('error', () => {
      hub.disconnect(sessionId)
    })
  })

  await new Promise<void>((resolve) => {
    httpServer.listen(opts.port, opts.host ?? '127.0.0.1', () => resolve())
  })

  const address = httpServer.address()
  const actualPort = typeof address === 'object' && address !== null ? address.port : opts.port

  // tick 循环：只在非测试场景启动（测试自己调 hub.tick 控制时间）
  const timer = opts.devMode === false ? undefined : setInterval(() => hub.tick(), 200)
  timer?.unref?.()

  // 心跳：手机切网络后旧 TCP 常处于半开状态，服务端收不到 close（I2）。
  // 15 秒没回 pong 的连接直接终止，触发 close → hub.disconnect → 房间暂停。
  const heartbeat = setInterval(() => {
    for (const ws of wss.clients) {
      if (alive.get(ws) === false) {
        ws.terminate()
        continue
      }
      alive.set(ws, false)
      ws.ping()
    }
  }, 15_000)
  heartbeat.unref?.()

  return {
    port: actualPort,
    tick: () => hub.tick(),
    // 优雅停机（spec §廿三.1.1，评审 P5 #1/#2 修正时序）：
    // 1) shutdown 同步退还在途门票（纯记账，不依赖连接）
    // 2) 主动 1001 断开全部连接——ws.close 只是发起握手，半开僵尸不 ACK，
    //    1 秒后对残留连接 terminate() 强杀：close() 有界（评审 #2），不再靠看门狗兜错误退出
    // 3) 全部连接处理完才 flush——断开会派生 hub.disconnect → 判负结算写盘（melee 引擎
    //    立即 gameOver），flush 提前的话那批金币/段位就丢盘（评审 #1）
    close: () =>
      new Promise<void>((resolve) => {
        if (timer !== undefined) clearInterval(timer)
        clearInterval(heartbeat)
        hub.shutdown()
        for (const ws of wss.clients) ws.close(1001, 'server restart')
        const enforcer = setTimeout(() => {
          for (const ws of wss.clients) ws.terminate()
        }, 1_000)
        enforcer.unref?.()
        wss.close(() => {
          httpServer.close(() => {
            profiles?.flush() // 最后一笔落盘（spec §21.1）：退款 + 断连派生的结算都在里面
            resolve()
          })
        })
      }),
  }
}
