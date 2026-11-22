import type { CapacitorConfig } from '@capacitor/cli'

/**
 * Android / iOS 原生壳（Capacitor）。把 vite 构建出的 H5（dist/）装进原生 WebView。
 *
 * 调试：CAP_DEV=1 时允许明文 ws:// 连局域网开发服务器。
 * 正式：服务端必须是 wss://（HTTPS 页面下 WebView 禁止混合内容），构建时注入 VITE_WS_URL。
 */
const dev = process.env.CAP_DEV === '1'

const config: CapacitorConfig = {
  appId: 'com.planeduel.app',
  appName: '飞机对决',
  webDir: 'dist',
  server: dev ? { androidScheme: 'http', cleartext: true } : { androidScheme: 'https' },
  backgroundColor: '#0e1a2b',
}

export default config
