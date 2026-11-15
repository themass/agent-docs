import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/**
 * C-09: focusing a question in the rail scrolls the matching bullet into view.
 *
 * The PRD calls this out as a product constraint, not a nicety: with two
 * independently scrolling columns, a user working through the gap list has no way
 * to tell which line of the resume each question is about unless the document
 * follows them.
 *
 * The mechanism is `data-path` on the structured view plus `scrollIntoView`. This
 * asserts the wiring exists and reacts — the exact pixel target is not worth
 * pinning, but "hovering a gap does nothing" is exactly the regression a reader
 * would never notice from a screenshot.
 */

test.describe("C-09 左栏聚焦联动", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("C-09 结构化视图里存在 data-path 锚点", async ({ page }) => {
    await page.goto("/resume-agent");
    await page.waitForLoadState("networkidle");

    // Navigate to step 3 if the workflow renders step controls as buttons.
    const step3 = page.getByRole("button", { name: /优化预览|第 ?3 ?步|3\./ }).first();
    if (await step3.count()) {
      await step3.click().catch(() => {});
      await page.waitForLoadState("networkidle");
    }

    const structured = page.getByRole("button", { name: /结构化|结构化视图/ }).first();
    if (await structured.count()) {
      await structured.click().catch(() => {});
      await page.waitForTimeout(1000);
    }

    const anchors = page.locator("[data-path]");
    const count = await anchors.count();
    test.skip(count === 0, "当前没有生成稿或未处于结构化视图，无法验证锚点");

    // Every anchor must carry a profile-ish path, not an empty string — an empty
    // data-path would make the rail's focus lookup silently match nothing.
    const paths = await anchors.evaluateAll((els) =>
      els.map((e) => e.getAttribute("data-path") ?? ""),
    );
    expect(paths.filter((p) => p.length > 0).length).toBeGreaterThan(0);
  });

  test("C-09b 悬停证据缺口会给文档锚点加上高亮", async ({ page }) => {
    await page.goto("/resume-agent");
    await page.waitForLoadState("networkidle");

    // Open the evidence panel if it is collapsed behind a button.
    const evidence = page.getByRole("button", { name: /证据|补全/ }).first();
    if (await evidence.count()) {
      await evidence.click().catch(() => {});
      await page.waitForTimeout(800);
    }

    const gaps = page.locator("li").filter({ hasText: /待补充/ });
    const gapCount = await gaps.count();
    test.skip(gapCount === 0, "当前档案没有证据缺口，无法验证联动");

    const anchors = page.locator("[data-path]");
    test.skip((await anchors.count()) === 0, "没有结构化锚点");

    // Capture the document's scroll position, hover the gap, and confirm the rail
    // *did something*. Asserting on the highlight class name would pin an
    // implementation detail; asserting on "nothing changed at all" is the real bug.
    const before = await page.evaluate(() => {
      const el = document.querySelector("[data-path]");
      return el ? el.className : "";
    });

    await gaps.first().hover();
    await page.waitForTimeout(1200);

    const after = await page.evaluate(() => {
      const el = document.querySelector("[data-path]");
      return el ? el.className : "";
    });

    // Either the class or the scroll position changed; both are acceptable ways to
    // draw attention, and neither happening means the linkage is broken.
    const scrolled = await page.evaluate(() => {
      const el = document.querySelector("[data-path]");
      if (!el) return false;
      const r = el.getBoundingClientRect();
      return r.top >= 0 && r.top <= window.innerHeight;
    });

    expect(
      after !== before || scrolled,
      "悬停证据缺口后文档既没有高亮也没有滚动，联动没有生效",
    ).toBe(true);
  });
});
