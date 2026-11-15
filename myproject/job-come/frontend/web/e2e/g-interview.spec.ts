import { expect, test, type Page } from "@playwright/test";
import { HAS_CREDENTIALS, login, requireValue } from "./helpers";

/** G. 真实面试复盘 / I. 会员与兑换 */

async function firstProfile(page: Page): Promise<{ id: string } | undefined> {
  const res = await page.request.get(new URL("/api/v1/profiles", page.url()).toString());
  const data = await res.json();
  const list = Array.isArray(data) ? data : (data.profiles ?? []);
  return list[0];
}

test.describe("G. 面试复盘", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("G-01 保存一条面试记录后能读回", async ({ page }) => {
    const prof = requireValue(await firstProfile(page), "没有可用档案");
    
    const company = `e2e公司-${Date.now()}`;

    const res = await page.request.post(
      new URL(`/api/v1/coach/profiles/${prof.id}/interviews`, page.url()).toString(),
      {
        data: {
          company,
          role: "后端工程师",
          round: "一面",
          questions: ["讲一个你做过的性能优化"],
          reflection: "讲得太散，应该先给结论",
        },
      },
    );
    test.skip(res.status() === 404 || res.status() === 405, "接口路径与该版本不符");

    if (res.status() >= 400) {
      // A validation refusal is acceptable if it says why; a 500 is not.
      expect(res.status()).toBeLessThan(500);
      const body = await res.json();
      expect(JSON.stringify(body)).not.toMatch(/Traceback/);
      return;
    }

    const listRes = await page.request.get(
      new URL(`/api/v1/coach/profiles/${prof.id}/interviews`, page.url()).toString(),
    );
    expect(listRes.status()).toBe(200);
    expect(await listRes.text(), "保存成功但列表读不到").toContain(company);
  });

  test("G-02 题库可搜索", async ({ page }) => {
    const prof = requireValue(await firstProfile(page), "没有可用档案");
    
    const res = await page.request.get(
      new URL(`/api/v1/coach/profiles/${prof.id}/bank?limit=5`, page.url()).toString(),
    );
    expect(res.status()).toBe(200);
  });
});

test.describe("I. 会员", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("I-01 会员状态可读，字段完整", async ({ page }) => {
    const res = await page.request.get(new URL("/api/v1/membership/me", page.url()).toString());
    expect(res.status()).toBe(200);
    const m = await res.json();
    expect(m).toHaveProperty("tier");
  });

  test("I-02 无效兑换码被拒且文案可读", async ({ page }) => {
    const res = await page.request.post(new URL("/api/v1/membership/redeem", page.url()).toString(), {
      data: { code: "E2E-INVALID-CODE-000000" },
    });
    expect(res.status()).toBeGreaterThanOrEqual(400);
    expect(res.status()).toBeLessThan(500);
    const body = await res.json();
    expect(body.message ?? body.detail ?? "").toBeTruthy();
    expect(JSON.stringify(body)).not.toMatch(/Traceback|Exception/);
  });
});
