/// <reference types="vite/client" />

declare module '*.vue' {
  import type { DefineComponent } from 'vue'
  const component: DefineComponent<object, object, unknown>
  export default component
}

interface ImportMetaEnv {
  /** WS 入口；缺省 wss://api.ok123find.top/vvv/api/game/ws（见 net/socket.ts） */
  readonly VITE_WS_URL?: string
  /** 平台 Vpn-Token 兜底（原生壳调试用）；正式来源是登录页写入的 localStorage（net/auth.ts） */
  readonly VITE_VPN_TOKEN?: string
  /** 游戏 HTTP 读接口基址覆盖；缺省见 net/http.ts defaultApiBase 策略 */
  readonly VITE_API_BASE?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
