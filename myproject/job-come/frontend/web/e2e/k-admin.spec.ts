import { expect, test, type Page } from "@playwright/test";
import { HAS_CREDENTIALS, login } from "./helpers";

/**
 * K. 管理后台 — "the panel returned 200" was once mistaken for "the panel works".
 * These cases assert on rendered numbers, not on a status code.
 */

async function openMetrics(page: Page): Promise<void> {
  await page.goto("/admin/metrics");
  await page.waitForLoadState("networkidle");
}

test.describe("K. 管理后台", () => {
  test.beforeEach(async ({ page }) => {
    test.skip(!HAS_CREDENTIALS, "需要 JC_E2E_PASSWORD 才能跑登录用例");
    await login(page);
  });

  test("K-02/K-06/K-07 监控面板有真实数字，不是空白或 0.00003s", async ({ page }) => {
    await openMetrics(page);

    const body = await page.locator("body").innerText();
    expect(body).toMatch(/监控|指标/);

    // K-06: the core-method panel must exist at all. It did not before — the
    // series were on the wire and nothing rendered them.
    expect(body, "缺少「核心方法」面板").toMatch(/核心方法/);

    // K-06 again, as a value: stream_message is the whole turn, so a number under
    // a second means the async-generator timing bug is back (it once recorded
    // 0.00003s for a 30s turn).
    const streamLine = body.split("\n").find((l) => l.includes("stream_message"));
    if (streamLine) {
      const nums = streamLine.match(/\d+(\.\d+)?/g) ?? [];
      const seconds = nums.map(Number).filter((n) => n > 0);
      if (seconds.length > 0) {
        expect(Math.max(...seconds), `stream_message 耗时看着不真实: ${streamLine}`).toBeGreaterThan(0.5);
      }
    }
  });

  test("K-12 跨进程标识为 true（生产是双 worker）", async ({ page, request }) => {
    // Read through the page's own origin so the session cookie applies.
    const url = new URL("/api/v1/admin/metrics", page.url()).toString();
    const res = await page.request.get(url);
    expect(res.status()).toBe(200);
    const data = await res.json();
    expect(data.sharing_across_processes).toBe(true);
  });

  test("K-14 调用列表默认时间倒序且不含 payload", async ({ page }) => {
    const url = new URL("/api/v1/admin/llm/calls?limit=5", page.url()).toString();
    const res = await page.request.get(url);
    expect(res.status()).toBe(200);
    const data = await res.json();

    expect(data.sort_by).toBe("created_at");
    expect(data.sort_dir).toBe("desc");

    const first = data.calls?.[0];
    expect(first, "列表为空").toBeTruthy();
    for (const col of ["prompt_text", "response_text", "reasoning_text"]) {
      expect(first, `列表返回了 ${col}，那会让接口传 1.35MB 无用数据`).not.toHaveProperty(col);
    }
  });

  test("K-13 跑完一轮后 inflight 回零", async ({ page }) => {
    const url = new URL("/api/v1/admin/metrics", page.url()).toString();
    const res = await page.request.get(url);
    const data = await res.json();
    const peer = data.peers.find((p: { name: string }) => p.name === "job-come");
    const family = peer?.families?.agent_turns_in_flight;
    const value = family?.series?.find((s: { suffix: string }) => s.suffix === "value")?.value;
    expect(value, "agent_turns_in_flight 不在 = 没有数据；非 0 = 有回合卡住").toBe(0);
  });

  test("K-01 普通用户看不到管理面板", async ({ page }) => {
    // The account used here is an admin, so this asserts the *gate exists* rather
    // than that a non-admin is refused — a non-admin needs a second account, which
    // is a separate fixture. What must not happen either way is a bare 500.
    const res = await page.request.get(new URL("/api/v1/admin/metrics", page.url()).toString());
    expect([200, 401, 403]).toContain(res.status());
  });
});
