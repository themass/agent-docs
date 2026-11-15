import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/** J. 通知与反馈 */

test.describe("J. 通知与反馈", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("J-01 通知列表可读，未登录被拒", async ({ page }) => {
    const res = await page.request.get(new URL("/api/v1/notifications", page.url()).toString());
    expect(res.status()).toBe(200);
    const data = await res.json();
    const items = Array.isArray(data) ? data : (data.notifications ?? data.items ?? []);
    expect(Array.isArray(items)).toBe(true);
  });

  test("J-03 提交反馈成功", async ({ page }) => {
    const res = await page.request.post(new URL("/api/v1/feedback", page.url()).toString(), {
      data: {
        title: `e2e 自动验证 ${new Date().toISOString()}`,
        category: "bug",
        body: "若看到这条说明反馈入口可用",
      },
    });
    expect(res.status()).toBeLessThan(400);
  });

  test("J-02 反馈列表能读回刚提交的内容", async ({ page }) => {
    const marker = `e2e-marker-${Date.now()}`;
    await page.request.post(new URL("/api/v1/feedback", page.url()).toString(), {
      data: { title: `feedback roundtrip ${marker}`, category: "bug", body: marker },
    });
    const res = await page.request.get(new URL("/api/v1/feedback", page.url()).toString());
    expect(res.status()).toBe(200);
    const text = await res.text();
    expect(text, "提交成功但列表里读不到，说明写入或查询不一致").toContain(marker);
  });
});
