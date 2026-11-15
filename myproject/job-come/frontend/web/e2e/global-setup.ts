import { chromium, expect, type FullConfig } from "@playwright/test";

import { EMAIL, HAS_CREDENTIALS, PASSWORD, emailInput, passwordInput } from "./helpers";

/**
 * Log in once, reuse the session everywhere.
 *
 * Every test used to drive the login form itself, which meant a 36-test run
 * performed 36 logins against a live deployment. That is both slow and a real
 * failure mode: one login timed out mid-run and the export test failed with
 * "still on /auth/login", which looks like an export bug and is not.
 *
 * Logging in here keeps the coverage where it matters — `a-auth.spec.ts` still
 * exercises the real form, and it is the file that asserts the form works.
 */
export default async function globalSetup(config: FullConfig): Promise<void> {
  if (!HAS_CREDENTIALS) return;

  const baseURL = config.projects[0]?.use?.baseURL ?? process.env.JC_BASE_URL;
  if (!baseURL) return;

  const browser = await chromium.launch();
  const page = await browser.newPage({ baseURL });
  await page.goto("/auth/login");
  await emailInput(page).fill(EMAIL);
  await passwordInput(page).fill(PASSWORD);
  await page.locator('form button[type="submit"]').first().click();
  await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 40_000 });

  await page.context().storageState({ path: "e2e/.auth/state.json" });
  await browser.close();
}
