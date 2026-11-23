import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  // 相对资源路径：H5 挂站点任意子路径（如 /plane/）都能加载（见 testserverV docs/game/deploy.md）
  base: './',
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      // dev 期把浏览器侧同源 /vvv 转到线上网关（见 net/http.ts 基址策略）
      // ws:true + upgrade 改写 Origin：本地预览面板连线上 WS，
      // 来源伪装成已放行的页面域，后端配置零改动（仅 dev server 行为）
      '/vvv': {
        target: 'https://api.ok123find.top',
        changeOrigin: true,
        ws: true,
        configure: (proxy) => {
          // http-proxy 的 WS 前置钩子是 proxyReqWs（'upgrade' 是 http server 的事件，收不到）
          proxy.on('proxyReqWs', (proxyReq) => {
            proxyReq.setHeader('origin', 'https://game.ok123find.top')
          })
        },
      },
    },
  },
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
  },
})
