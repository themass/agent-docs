import { expect, type Page } from "@playwright/test";

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
 * Log in through the real form.
 *
 * Through the UI rather than by injecting a cookie: the cookie name, the session
 * store and the CSRF behaviour are all part of what these tests are here to check.
 * A test that sets the cookie itself would pass with a broken login form.
 */
export async function login(page: Page): Promise<void> {
  await page.goto("/auth/login");
  await emailInput(page).fill(EMAIL);
  await passwordInput(page).fill(PASSWORD);
  await page.locator('form button[type="submit"]').first().click();
  await expect(page).not.toHaveURL(/\/auth\/login/, { timeout: 40_000 });
}
