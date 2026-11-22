/**
 * 进程入口。与 main.ts 分开，避免测试 import main.ts 时意外起服务。
 */
import { createServer } from './main'

const port = Number(process.env.PORT ?? 8080)
const host = process.env.HOST ?? '0.0.0.0'
// 档案文件路径可注入（spec §廿三.2）：容器里指到挂载卷上的路径，默认 data/profiles.json 不变
const profileFile = process.env.PROFILES_FILE

createServer({
  port,
  host,
  devMode: process.env.NODE_ENV !== 'production',
  ...(profileFile !== undefined && profileFile !== '' ? { profileFile } : {}),
}).then((s) => {
  console.log(`plane-duel server listening on ws://${host}:${s.port}`)
  // 信号处理必须挂在真实入口上（P5 实跑发现：P4 之前挂在 main.ts 的入口块里，
  // 而生产走 index.ts 启动，那段 isEntrypoint 永远为 false——优雅停机从来没生效过）
  let closing = false
  const stop = (sig: string) => {
    if (closing) return
    closing = true
    console.log(`plane-duel server stopping (${sig})`)
    // 看门狗（§廿三.2）：close 卡住 8 秒就硬退——Docker stop 默认 10s 才 SIGKILL，留 2 秒余量，
    // 免得停机无声挂死到超时被杀、日志里看不到原因
    const watchdog = setTimeout(() => {
      console.error('[shutdown] 8s 未完成，强制退出')
      process.exit(1)
    }, 8_000)
    watchdog.unref?.()
    s.close().then(
      () => process.exit(0),
      (err) => {
        console.error('[shutdown] close 报错', err)
        process.exit(1)
      },
    )
  }
  process.on('SIGINT', () => stop('SIGINT'))
  process.on('SIGTERM', () => stop('SIGTERM'))
})
