import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:4177',
    headless: true,
  },
  webServer: {
    command: 'npm run demo:site',
    url: 'http://127.0.0.1:4177',
    reuseExistingServer: true,
    timeout: 60_000,
  },
})
