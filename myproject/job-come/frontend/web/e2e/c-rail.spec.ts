import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, login, requireValue } from "./helpers";

/**
 * C-08: the agent rail collapses to a 44px strip — and collapsing does not end a run.
 *
 * The PRD states this explicitly, and it has never been verified in a browser. The
 * second half is the part that matters: a collapsed panel that kills the stream it
 * was carrying is worse than no collapse at all, and "the reply still arrives while
 * collapsed" cannot be checked from the API.
 */

const COLLAPSE = /收起舟卡/;
const EXPAND = /展开舟卡/;

test.describe("C-08 舟卡侧栏收起", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
    await page.goto("/resume-agent");
    await page.waitForLoadState("networkidle");
  });

  test("C-08 收起后出现竖条，且竖条能展开回去", async ({ page }) => {
    // The rail is only offered where the page has a document beside it; skip
    // honestly rather than failing on a layout this page does not use.
    const collapseBtn = page.getByTitle(COLLAPSE).first();
    const canCollapse = await collapseBtn.count();
    test.skip(canCollapse === 0, "当前版面没有收起入口（可能是统一布局）");

    await collapseBtn.click();

    // The handle is the collapsed state's own control — its presence is the proof
    // the pane actually collapsed rather than merely hiding.
    const rail = page.getByRole("button", { name: EXPAND }).first();
    await expect(rail).toBeVisible({ timeout: 10_000 });

    // 44px is the width the PRD specifies; a wider rail means the document did not
    // get back the space the collapse was for.
    const box = requireValue(await rail.boundingBox(), "竖条不可测量");
    expect(box.width, `竖条宽度 ${box.width}px，应为 44px 左右`).toBeLessThanOrEqual(60);
    expect(box.width, `竖条宽度 ${box.width}px，不像是收起状态`).toBeGreaterThan(20);

    await rail.click();
    await expect(page.getByTitle(COLLAPSE).first()).toBeVisible({ timeout: 10_000 });
  });

  test("C-08b 收起不等于结束：运行中的回合收起后仍能拿到回复", async ({ page }) => {
    const collapseBtn = page.getByTitle(COLLAPSE).first();
    test.skip((await collapseBtn.count()) === 0, "当前版面没有收起入口");

    const box = page.locator("textarea").first();
    await box.waitFor({ state: "visible", timeout: 30_000 });
    await box.fill("用一句话说明收起的侧栏会不会中断回答");
    await box.press("Enter");

    // Collapse immediately — while the turn is in flight. That is the case the PRD
    // calls out: unmounting here would kill a run the user just started.
    await page.waitForTimeout(1500);
    await collapseBtn.click();
    const rail = page.getByRole("button", { name: EXPAND }).first();
    await expect(rail).toBeVisible({ timeout: 10_000 });

    // Expand again and look for the reply. A dead stream shows nothing new.
    await rail.click();
    const before = (await page.locator("body").innerText()).length;

    await expect
      .poll(async () => (await page.locator("body").innerText()).length, {
        timeout: 120_000,
        intervals: [2000],
      })
      .toBeGreaterThan(before + 10);

    const body = await page.locator("body").innerText();
    expect(body, "收起后回合没有完成，回复丢失").not.toMatch(/舟卡没能完成这次回复/);
  });
});
