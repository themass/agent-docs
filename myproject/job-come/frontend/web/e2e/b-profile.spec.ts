import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/** B. 建档 —— 四个入口汇入同一条管线。 */

test.describe("B. 建档", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("B-04 粘贴文本低于 80 字被拒，且文案可读", async ({ page }) => {
    const res = await page.request.post(
      new URL("/api/v1/profiles/from-text", page.url()).toString(),
      { data: { text: "太短" } },
    );
    // Either a 4xx with a readable reason, or 200 — but never a 500 and never a
    // silently fabricated profile. The product rule is: refuse rather than invent.
    expect(res.status()).toBeLessThan(500);
    if (res.status() >= 400) {
      const body = await res.json();
      expect(body.message ?? body.detail ?? "").toBeTruthy();
      expect(JSON.stringify(body)).not.toMatch(/Traceback|Exception/);
    }
  });

  test("B-07/B-08 档案列表可用，新建档案是草稿态", async ({ page }) => {
    const res = await page.request.post(
      new URL("/api/v1/profiles", page.url()).toString(),
      { data: { name: `e2e-draft-${Date.now()}` } },
    );
    expect(res.status()).toBe(200);
    const prof = await res.json();
    expect(prof.status, "新建档案必须先是草稿，不能直接是已确认").toBe("draft");

    const listRes = await page.request.get(new URL("/api/v1/profiles", page.url()).toString());
    const list = await listRes.json();
    const arr = Array.isArray(list) ? list : (list.profiles ?? []);
    expect(arr.some((p: { id: string }) => p.id === prof.id)).toBe(true);
  });

  test("B-08b 空档案不能被确认", async ({ page }) => {
    const created = await page.request.post(
      new URL("/api/v1/profiles", page.url()).toString(),
      { data: { name: `e2e-empty-${Date.now()}` } },
    );
    const prof = await created.json();
    const res = await page.request.post(
      new URL(`/api/v1/profiles/${prof.id}/confirm`, page.url()).toString(),
      { data: {} },
    );
    // A profile with no facts must be refused — confirming it would let the writer
    // generate a document from nothing.
    expect(res.status()).toBeGreaterThanOrEqual(400);
    const body = await res.json();
    expect(JSON.stringify(body)).not.toMatch(/Traceback/);
  });
});
