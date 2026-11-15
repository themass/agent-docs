import { expect, test, type Page } from "@playwright/test";

export const EMAIL = process.env.JC_E2E_EMAIL ?? "metrics-probe-20261114@example.com";
export const PASSWORD = process.env.JC_E2E_PASSWORD ?? "";

export const HAS_CREDENTIALS = PASSWORD.length > 0;

/** The password field, not the "show password" button that also matches 密码. */
export function passwordInput(page: Page) {
  return page.locator('input[type="password"]').first();
}

export function emailInput(page: Page) {
  // The email field is the first text-ish input on the form; labelling is
  // inconsistent between the login and register pages.
  return page.locator('input[type="email"], input[autocomplete="username"]').first();
}

/**
 * Return `value`, or skip the test when it is absent.
 *
 * `test.skip(cond, why)` returns void, so TypeScript cannot narrow anything after
 * it and every call site needs an assertion. Putting it here keeps the claim in
 * one place ("after this line it exists") instead of eight.
 */
export function requireValue<T>(value: T | undefined | null, reason: string): T {
  if (value === undefined || value === null) test.skip(true, reason);
  return value as T;
}

/**
 * Ensure the page has a signed-in session.
 *
 * Normally `global-setup.ts` already logged in and its `storageState` is loaded,
 * so this only has to confirm it. That matters: with 36 tests each driving the
 * form, one login timed out mid-run and the export test failed with "still on
 * /auth/login" — an export failure that was really a login flake.
 *
 * The form path stays, and `a-auth.spec.ts` still exercises it for real: that is
 * the suite which asserts the form works. Logging in by injecting a cookie for
 * every test would make a broken login form invisible everywhere else.
 */
export async function login(page: Page): Promise<void> {
  await page.goto("/auth/account");
  const url = page.url();
  const body = await page.locator("body").innerText();

  // Already signed in: the account page rendered instead of redirecting away.
  if (!/\/auth\/login/.test(url) && !/请先登录|登录后可/.test(body)) return;

  await page.goto("/auth/login");
  await emailInput(page).fill(EMAIL);
  await passwordInput(page).fill(PASSWORD);
  await page.locator('form button[type="submit"]').first().click();
  await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 40_000 });
}
