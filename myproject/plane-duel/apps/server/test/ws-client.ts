/** 端到端测试用的真实 WebSocket 客户端：完整消息日志 + 按条件取消息的收件箱。 */
import WebSocket from 'ws'

export type WsClient = ReturnType<typeof wsClient>

export function wsClient(port: number) {
  const ws = new WebSocket(`ws://127.0.0.1:${port}`)
  /** 收到的全部消息，按顺序，不删除 */
  const log: any[] = []
  /** 尚未被 next 取走的消息 */
  const inbox: any[] = []
  const waiters: { match: (m: any) => boolean; res: (m: any) => void }[] = []
  ws.on('message', (d) => {
    const m = JSON.parse(d.toString())
    log.push(m)
    const i = waiters.findIndex((w) => w.match(m))
    if (i >= 0) waiters.splice(i, 1)[0]!.res(m)
    else inbox.push(m)
  })
  return {
    log,
    open: () => new Promise<void>((r) => ws.on('open', () => r())),
    send: (m: unknown) => ws.send(JSON.stringify(m)),
    /** 取出第一条类型为 type 且满足 pred 的消息（之前的其它消息保留在收件箱）。
     * 默认超时放宽到 15s：全套并行时事件循环被抢，3s 偶发不够（p3.e2e 跨季用例翻出过）。 */
    next: (type: string, pred: (m: any) => boolean = () => true, timeout = 15_000) =>
      new Promise<any>((res, rej) => {
        const match = (m: any) => m.type === type && pred(m)
        const i = inbox.findIndex(match)
        if (i >= 0) return res(inbox.splice(i, 1)[0])
        const t = setTimeout(() => rej(new Error(`timeout waiting ${type}`)), timeout)
        waiters.push({ match, res: (m) => (clearTimeout(t), res(m)) })
      }),
    close: () => ws.close(),
  }
}
