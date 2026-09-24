import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './tests/live',
  testMatch: '**/*.spec.ts',
  outputDir: './test-results/live',
  timeout: 75_000,
  expect: { timeout: 10_000 },
  retries: 1,
  workers: 1,
  reporter: [
    ['list'],
    ['html', { outputFolder: 'playwright-report/live', open: 'never' }],
    ['json', { outputFile: 'test-results/live/results.json' }],
  ],
  use: {
    headless: false,
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    video: 'retain-on-failure',
  },
})
