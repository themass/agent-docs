import { defineConfig, mergeConfig } from 'vitest/config';
import viteConfig from './vite.config';

// 测试配置独立成文件，生产构建(vite build)不会加载 vitest。
export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      setupFiles: ['./src/test/setup.ts'],
      include: ['src/**/*.test.{ts,tsx}'],
      restoreMocks: true,
      css: false,
    },
  }),
);
