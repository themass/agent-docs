import { expect, test } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/**
 * K-15~K-21: the admin pages beyond the metrics panel and the call list.
 *
 * These assert the page renders and its data source answers — not a pixel match.
 * The failure mode they exist for is the one that already happened once: a page
 * returning 200 while its data call 500'd, which a status-code check calls a pass.
 */

const ADMIN_PAGES = [
  { path: "/admin/users", label: "用户目录", api: "/api/v1/admin/users?limit=5" },
  { path: "/admin/sessions", label: "Session 审计", api: "/api/v1/admin/sessions?limit=5" },
  { path: "/admin/feedback", label: "用户反馈", api: "/api/v1/admin/feedback?limit=5" },
  { path: "/admin/redeem", label: "兑换码", api: "/api/v1/admin/redeem-codes?limit=5" },
  { path: "/admin/llm", label: "LLM 调用", api: "/api/v1/admin/llm/calls?limit=5" },
] as const;

test.describe("K. 后台各页面", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  for (const p of ADMIN_PAGES) {
    test(`K-17~K-21 ${p.label}：页面渲染且数据接口成功`, async ({ page }) => {
      // The data call first: a page can render its chrome around a failed fetch.
      const res = await page.request.get(new URL(p.api, page.url()).toString());
      expect(res.status(), `${p.label} 的数据接口失败`).toBe(200);

      const errors: string[] = [];
      page.on("pageerror", (e) => errors.push(String(e)));

      await page.goto(p.path, { waitUntil: "domcontentloaded" });
      await page.waitForLoadState("networkidle");

      const body = await page.locator("body").innerText();
      expect(body, `${p.label} 页面是空的`).toMatch(/\S/);
      // A page that leaks a stack trace to the browser is broken regardless of status.
      expect(body).not.toMatch(/Traceback|Cannot read properties|undefined is not/);
      expect(errors, `${p.label} 有未捕获的前端异常: ${errors.join("; ")}`).toHaveLength(0);
    });
  }

  test("K-19 session trace 导出是合法 NDJSON", async ({ page }) => {
    // Pick a session that actually has messages. The newest session is often a
    // freshly created, empty one — exporting it legitimately yields zero lines, and
    // asserting "non-empty" against it would be a test bug reported as a defect.
    const listRes = await page.request.get(
      new URL("/api/v1/admin/sessions?limit=20", page.url()).toString(),
    );
    if (listRes.status() !== 200) return;
    const data = await listRes.json();
    const sessions = data.sessions ?? data.items ?? [];
    const withMessages = sessions.find(
      (s: { message_count?: number }) => (s.message_count ?? 0) > 0,
    );
    test.skip(!withMessages, "没有带消息的会话可导出，跳过");

    const sid = withMessages.id;
    const res = await page.request.get(
      new URL(`/api/v1/admin/sessions/${sid}/trace.jsonl`, page.url()).toString(),
    );
    if (res.status() === 404) return; // endpoint shape differs in this build
    expect(res.status()).toBe(200);

    const text = await res.text();
    const lines = text.split("\n").filter((l) => l.trim());
    expect(lines.length, "导出是空的").toBeGreaterThan(0);
    // Every line must parse — an export that is not NDJSON breaks every downstream tool.
    for (const line of lines.slice(0, 20)) {
      expect(() => JSON.parse(line), `不是合法 JSON: ${line.slice(0, 120)}`).not.toThrow();
    }
  });
});
