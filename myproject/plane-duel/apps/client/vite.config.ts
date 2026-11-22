import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
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
