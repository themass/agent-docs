#!/usr/bin/env node
/**
 * 部署冒烟（spec §廿三.3）：真实 WS 打一条最小链路。从仓库根跑（要能解析 ws 依赖）：
 *
 *   node deploy/smoke.mjs queue  [playerId] [url]   # 认证 → 付标准场门票进队列，停住不退（模拟"排队中被停机"）
 *   node deploy/smoke.mjs check  [playerId] [url]   # 重连查档案余额（停机退款后应回到 50）
 *   node deploy/smoke.mjs play   [playerId] [url]   # 认证 → 免费场排队等匹配 → 摆好即报 READY
 *
 * 默认 url ws://127.0.0.1:8080。登录礼 50，标准场票 50：付票后余额 0，退款后回到 50。
 */
import { createRequire } from 'node:module'
// ws 依赖在 apps/server 的 node_modules 里（pnpm 不提升到仓库根）：从那里解析
const require = createRequire(new URL('../apps/server/package.json', import.meta.url))
const WebSocket = require('ws')

const mode = process.argv[2] ?? 'check'
const playerId = process.argv[3] ?? `smoke-${mode}`
const url = process.argv[4] ?? 'ws://127.0.0.1:8080'

const ws = new WebSocket(url)
let coins = null
ws.on('open', () => ws.send(JSON.stringify({ type: 'auth', playerId, nickname: `冒烟${mode}` })))
ws.on('message', (d) => {
  const m = JSON.parse(d.toString())
  if (m.type === 'profile') coins = m.profile.coins
  if (mode === 'queue' && m.type === 'ready') {
    ws.send(JSON.stringify({ type: 'queueJoin', capacity: 4, preset: 'standard', ticket: 'standard' }))
  }
  if (mode === 'queue' && m.type === 'coinsChanged' && m.reason === 'ticket-fee') {
    console.log(`已付门票，余额 ${m.balance}。Ctrl-C 断客户端，或直接 docker compose stop server 看退款。`)
  }
  if (mode === 'play' && m.type === 'tableState' && m.table?.kind === 'match') {
    ws.send(JSON.stringify({ type: 'placePlane', planes: [{ row: 3, col: 7 }] }))
    console.log('已入座摆好，等待对手/补位。')
  }
})
ws.on('close', (code) => console.log(`closed ${code}`))
ws.on('error', (e) => {
  console.error(`连接失败：${e.message}（服务起来了？端口对吗？）`)
  process.exit(1)
})

if (mode === 'check') {
  setTimeout(() => {
    if (coins === null) {
      console.error('没收到 profile')
      process.exit(1)
    }
    console.log(`档案余额: ${coins}`)
    process.exit(0)
  }, 1500)
}
