import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['test/**/*.test.ts'],
    environment: 'node',
    // WebSocket 测试需要真实网络往返，给足时间
    testTimeout: 15000,
  },
})
