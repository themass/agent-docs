import { describe, it, expect, afterAll } from 'vitest'
import WebSocket from 'ws'
import { createServer } from '../src/main'

const srv = await createServer({ port: 0 })
afterAll(() => srv.close())

function connect(port: number): Promise<WebSocket> {
  return new Promise((res, rej) => {
    const ws = new WebSocket(`ws://127.0.0.1:${port}`)
    ws.on('open', () => res(ws))
    ws.on('error', rej)
  })
}

describe('认证', () => {
  it('auth 后返回 ready 与 token', async () => {
    const ws = await connect(srv.port)
    const msg = await new Promise<any>((res) => {
      ws.on('message', (d) => res(JSON.parse(d.toString())))
      ws.send(JSON.stringify({ type: 'auth', playerId: 'p-a' }))
    })
    expect(msg.type).toBe('ready')
    expect(msg.playerId).toBe('p-a')
    expect(typeof msg.token).toBe('string')
    expect(msg.nickname).toBe('玩家')
    ws.close()
  })

  it('未认证就发 createRoom 返回 error', async () => {
    const ws = await connect(srv.port)
    const msg = await new Promise<any>((res) => {
      ws.on('message', (d) => res(JSON.parse(d.toString())))
      ws.send(
        JSON.stringify({
          type: 'createRoom',
          capacity: 2,
          listed: false,
          rules: { boardSize: 10, planeCount: 1, turnSeconds: 20, hintAllowed: false },
        }),
      )
    })
    expect(msg.type).toBe('error')
    expect(msg.code).toBe('NOT_AUTHED')
    ws.close()
  })

  it('畸形输入不断开连接', async () => {
    const ws = await connect(srv.port)
    ws.send('garbage')
    const msg = await new Promise<any>((res) => {
      ws.on('message', (d) => res(JSON.parse(d.toString())))
    })
    expect(msg.type).toBe('error')
    expect(msg.code).toBe('BAD_JSON')
    expect(ws.readyState).toBe(WebSocket.OPEN)
    ws.close()
  })
})

describe('传输层防护（M5）', () => {
  it('超过 4KB 的消息直接断开连接，服务端不崩', async () => {
    const ws = await connect(srv.port)
    const closed = new Promise<number>((res) => ws.on('close', (code) => res(code)))
    ws.send('x'.repeat(10_000))
    expect(await closed).toBe(1009) // Message Too Big
    // 服务端仍可接受新连接
    const ok = await connect(srv.port)
    ok.close()
  })
})
