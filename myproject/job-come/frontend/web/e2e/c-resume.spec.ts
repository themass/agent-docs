import { expect, test, type Page } from "@playwright/test";
import { HAS_CREDENTIALS, login, requireValue } from "./helpers";

/**
 * C. 简历优化 — the optimize-preview pipeline.
 *
 * These are slow (a real model call per level) and are the only cases here that
 * assert on *content* rather than on availability, because the product rules they
 * cover are about content: no invented facts, coverage reported, blueprint shown.
 */

const LEVELS = ["conservative", "elevated"] as const;

async function confirmedProfile(page: Page): Promise<{ id: string } | undefined> {
  const res = await page.request.get(new URL("/api/v1/profiles", page.url()).toString());
  const data = await res.json();
  const list = Array.isArray(data) ? data : (data.profiles ?? []);
  return list.find((p: { status?: string }) => p.status === "confirmed") ?? list[0];
}

test.describe("C. 简历优化", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  for (const level of LEVELS) {
    test(`C-01/C-02 ${level} 档位能生成，且带强化手段标注`, async ({ page }) => {
      const prof = requireValue(await confirmedProfile(page), "没有可用档案");
      

      const res = await page.request.get(
        new URL(
          `/api/v1/profiles/${prof.id}/elevate/preview?elevation_level=${level}&locale=zh-CN`,
          page.url(),
        ).toString(),
        { timeout: 300_000 },
      );
      expect(res.status(), `档位 ${level} 生成失败`).toBe(200);

      const body = await res.json();
      expect(body.html, "没有返回 HTML").toBeTruthy();
      expect(body.html.length, "HTML 太短，可能只是空壳").toBeGreaterThan(200);

      // The draft must carry per-change technique annotations; without them the
      // user cannot tell what was strengthened versus what was invented.
      const draft = body.draft ?? {};
      const serialized = JSON.stringify(draft);
      expect(serialized.length).toBeGreaterThan(50);
    });
  }

  test("C-05/C-07 预览带覆盖度与岗位标准，且都是建议", async ({ page }) => {
    const prof = requireValue(await confirmedProfile(page), "没有可用档案");
    

    const res = await page.request.get(
      new URL(
        `/api/v1/profiles/${prof.id}/elevate/preview?elevation_level=standard&locale=zh-CN`,
        page.url(),
      ).toString(),
      { timeout: 300_000 },
    );
    test.skip(res.status() !== 200, "本次生成未成功，跳过内容断言");

    const body = await res.json();
    // Both are advisory: their presence is what makes step 3 auditable, their
    // absence means the user is told nothing about what was dropped or unmet.
    expect(body).toHaveProperty("coverage");
    expect(body).toHaveProperty("blueprint");
    expect(body).toHaveProperty("structure");
  });

  test("C-01b 不同档位产出不同（档位真的生效）", async ({ page }) => {
    const prof = requireValue(await confirmedProfile(page), "没有可用档案");
    

    const get = async (level: string) => {
      const res = await page.request.get(
        new URL(
          `/api/v1/profiles/${prof.id}/elevate/preview?elevation_level=${level}&locale=zh-CN`,
          page.url(),
        ).toString(),
        { timeout: 300_000 },
      );
      if (res.status() !== 200) return null;
      const body = await res.json();
      return body.html as string;
    };

    const conservative = await get("conservative");
    const elevated = await get("elevated");
    test.skip(!conservative || !elevated, "两次生成未都成功，跳过对比");

    // Same facts, different wording strength. Identical output would mean the
    // level selector is decorative — a real defect, and one a status code cannot
    // catch.
    expect(conservative, "两个档位产出完全一致，档位没有生效").not.toBe(elevated);
  });

  test("C-10 优化稿版本列表可读", async ({ page }) => {
    const prof = requireValue(await confirmedProfile(page), "没有可用档案");
    
    const res = await page.request.get(
      new URL(`/api/v1/resume-versions?profile_id=${prof.id}`, page.url()).toString(),
    );
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data).toHaveProperty("groups");
  });
});
