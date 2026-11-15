import { existsSync } from "node:fs";

import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end checks against a running deployment.
 *
 * BASE_URL points at whatever is being verified: the local dev stack, or the
 * production site behind a tunnel. These tests log in with a real account, so
 * they must never run against a database whose data matters without saying so.
 */
export default defineConfig({
  testDir: "./e2e",
  globalSetup: "./e2e/global-setup.ts",
  timeout: 180_000,
  expect: { timeout: 20_000 },
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [["list"], ["html", { open: "never", outputFolder: "e2e-report" }]],
  use: {
    baseURL: process.env.JC_BASE_URL ?? "http://127.0.0.1:3001",
    // Set by global-setup. Missing when a run has no credentials, in which case
    // the auth-dependent tests skip rather than silently starting signed out.
    storageState: existsSync("e2e/.auth/state.json") ? "e2e/.auth/state.json" : undefined,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    actionTimeout: 30_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
