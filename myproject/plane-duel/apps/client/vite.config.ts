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
      '/vvv': { target: 'https://api.ok123find.top', changeOrigin: true },
    },
  },
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
  },
})
