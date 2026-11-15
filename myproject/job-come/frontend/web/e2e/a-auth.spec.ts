import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, emailInput, login, passwordInput } from "./helpers";

test.describe("A. 账户与鉴权", () => {
  test("A-02 登录页可访问且表单完整", async ({ page }) => {
    await page.goto("/auth/login");
    await expect(emailInput(page)).toBeVisible();
    await expect(passwordInput(page)).toBeVisible();
    await expect(page.locator('form button[type="submit"]').first()).toBeVisible();
  });

  test("A-02b 错误密码给出可读文案，而不是英文堆栈", async ({ page }) => {
    await page.goto("/auth/login");
    await emailInput(page).fill("nobody@example.invalid");
    await passwordInput(page).fill("definitely-wrong-password");
    await page.locator('form button[type="submit"]').first().click();

    // Stay on the page — that alone is not the assertion; the message is.
    await expect(page).toHaveURL(/\/auth\/login/);
    const body = await page.locator("body").innerText();
    // A raw stack trace, a bare code, or an English exception leaking to the user
    // is the defect this case exists for.
    expect(body).not.toMatch(/Traceback|Exception|Error:/);
    expect(body).not.toMatch(/\b(500|502|503)\b/);
  });

  test("A-03 未登录访问业务页会跳转登录", async ({ browser }) => {
    // This case is *about* the signed-out state, so it must not inherit the
    // storageState that global-setup produced for the other tests. Built from a
    // bare context on purpose — reusing `page` would test the signed-in path and
    // pass for the wrong reason.
    const ctx = await browser.newContext({ storageState: undefined });
    const page = await ctx.newPage();
    await page.goto("/resume-agent");
    await page.waitForLoadState("networkidle");
    const url = page.url();
    const body = await page.locator("body").innerText();
    // Either redirected to auth, or the page itself asks for login. Both are
    // acceptable; silently rendering an empty workbench is not.
    const redirected = /\/auth\/login/.test(url);
    const asksToLogin = /登录/.test(body);
    expect(redirected || asksToLogin, `url=${url} body=${body.slice(0, 200)}`).toBe(true);
    await ctx.close();
  });

  test("A-08 登录后能进入账户设置", async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
    await page.goto("/settings/account");
    await expect(page.locator("body")).toContainText(/账户|账号|设置/);
  });
});
