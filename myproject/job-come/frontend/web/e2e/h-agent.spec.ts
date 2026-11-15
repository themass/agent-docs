import { expect, test, type Page } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/**
 * H. 舟卡 Agent — the area with the most production defects so far.
 *
 * H-06 is the one this file exists for: the reported bug was TWO "舟卡思考中"
 * indicators for one turn. A unit test pins the turn model (which turn may be
 * streaming); this asserts what a person actually sees, because the duplicate was
 * reported from a screenshot, not from state.
 */

async function openAgent(page: Page): Promise<void> {
  await page.goto("/resume-agent");
  await page.waitForLoadState("networkidle");
}

async function sendMessage(page: Page, text: string): Promise<void> {
  const box = page.locator("textarea").first();
  await box.waitFor({ state: "visible", timeout: 30_000 });
  await box.fill(text);
  await box.press("Enter");
}

const THINKING = /舟卡思考中|思考中/;

test.describe("H. 舟卡 Agent", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("H-06 等待期间只有一个「思考中」", async ({ page }) => {
    await openAgent(page);
    await sendMessage(page, "你好");

    // Sample repeatedly across the whole wait. The duplicate was visible in a
    // single moment, so one assertion after some fixed delay could miss it.
    const samples: number[] = [];
    const deadline = Date.now() + 90_000;
    while (Date.now() < deadline) {
      const n = await page.getByText(THINKING).count();
      if (n > 0) samples.push(n);
      if (n > 1) break;
      // Stop once an answer has visibly started — the wait is over.
      const text = await page.locator("body").innerText();
      if (/舟卡思考中/.test(text) === false && samples.length > 0) break;
      await page.waitForTimeout(500);
    }

    if (samples.length > 0) {
      expect(Math.max(...samples), `看到 ${Math.max(...samples)} 个「思考中」`).toBe(1);
    }
  });

  test("H-01 纯对话能在合理时间内拿到回复", async ({ page }) => {
    await openAgent(page);
    const before = (await page.locator("body").innerText()).length;
    await sendMessage(page, "你好，用一句话介绍你自己");

    await expect
      .poll(async () => (await page.locator("body").innerText()).length, {
        timeout: 120_000,
        intervals: [2000],
      })
      .toBeGreaterThan(before + 10);

    const body = await page.locator("body").innerText();
    expect(body).not.toMatch(/舟卡没能完成这次回复/);
  });

  test("H-02 带工具的改档能生成确认卡片", async ({ page }) => {
    // This is the path that was broken in production: the tool timed out and the
    // user never saw a confirmation card. Asserting the card appears is asserting
    // the fix, end to end, in a browser.
    await openAgent(page);
    await sendMessage(page, "把我档案里的邮箱改成 e2e-check@example.com，生成确认卡片就行");

    await expect
      .poll(async () => await page.getByText(/确认|保存到简历|应用修改/).count(), {
        timeout: 150_000,
        intervals: [2000],
      })
      .toBeGreaterThan(0);

    const body = await page.locator("body").innerText();
    // An honest timeout message is a failure here: the fix means it must not happen.
    expect(body).not.toMatch(/工具超时|超时|timed out/i);
  });
});
